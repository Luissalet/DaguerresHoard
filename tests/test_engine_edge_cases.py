"""Edge cases of the indexing engine found in review. Each test pins a bug
that was reproduced before it was fixed."""
from __future__ import annotations

import datetime as dt
import os
import time
from pathlib import Path

import pytest

from argus_hoard.config import Settings
from argus_hoard.embeddings import FakeEmbedder
from argus_hoard.library import Library, ValidationError
from tests.conftest import make_image

def _wait(library, job_id, timeout=20.0):
    start = time.time()
    while time.time() - start < timeout:
        job = library.jobs.get(job_id)
        if job and job["status"] not in ("running", "queued"):
            return job
        time.sleep(0.02)
    raise TimeoutError(library.jobs.get(job_id))


def _index(library, root_path):
    root = library.add_root(str(root_path))
    job = _wait(library, library.start_scan(root["id"]))
    assert job["status"] == "done", job
    return root


# --------------------------------------------------------------------- #
# Indexing robustness
# --------------------------------------------------------------------- #
def test_one_corrupt_file_does_not_abort_the_whole_scan(library, tmp_path):
    photos = tmp_path / "photos"
    make_image(photos / "a_good.jpg", color=(200, 30, 30))
    (photos / "b_broken.jpg").write_bytes(os.urandom(20_000))
    make_image(photos / "c_good.jpg", color=(30, 30, 200))
    root = library.add_root(str(photos))
    job = _wait(library, library.start_scan(root["id"]))
    assert job["status"] == "done", job
    assert library.library_status()["photo_count"] == 2
    assert job["stats"]["errors"] == 1
    assert "b_broken.jpg" in job["stats"]["error_samples"][0]


def test_concurrent_scans_are_serialised(library, tmp_path):
    photos = tmp_path / "photos"
    for i in range(12):
        make_image(photos / f"p{i:02d}.jpg", color=(20 * i % 255, 80, 160))
    root = library.add_root(str(photos))
    jobs = [library.start_scan(root["id"]) for _ in range(3)]
    results = [_wait(library, j) for j in jobs]
    assert [r["status"] for r in results] == ["done"] * 3, results
    assert library.library_status()["photo_count"] == 12
    rows = library.conn.execute("SELECT embed_row FROM photos").fetchall()
    assert len({r["embed_row"] for r in rows}) == 12
    assert library.vectors.count == 12


def test_data_dir_inside_a_root_is_never_indexed(tmp_path):
    root_dir = tmp_path / "home"
    make_image(root_dir / "Pictures" / "a.jpg")
    settings = Settings(data_dir=root_dir / "argus-data")
    lib = Library(settings, embedder=FakeEmbedder())
    _index(lib, root_dir)
    # rescan: the first scan wrote thumbnails under the data dir
    _wait(lib, lib.start_scan())
    paths = [r["path"] for r in lib.list_photos()["results"]]
    assert len(paths) == 1 and paths[0].endswith("a.jpg")


def test_remove_root_with_album_photos_does_not_crash(library, tmp_path):
    photos = tmp_path / "photos"
    make_image(photos / "a.jpg")
    root = _index(library, photos)
    pid = library.list_photos()["results"][0]["id"]
    library.album("Keep", [pid])
    library.remove_root(root["id"])
    assert library.library_status()["photo_count"] == 0
    assert library.list_albums()[0]["photo_count"] == 0
    assert photos.joinpath("a.jpg").exists()  # originals untouched


def test_changed_content_drops_the_stale_caption(library, tmp_path):
    photos = tmp_path / "photos"
    p = make_image(photos / "a.jpg", color=(200, 20, 20))
    _index(library, photos)
    pid = library.list_photos()["results"][0]["id"]
    library.conn.execute("UPDATE photos SET caption = 'a red wall' WHERE id = ?", (pid,))
    library.conn.commit()
    make_image(p, color=(20, 20, 200), size=(400, 300))
    os.utime(p, ns=(time.time_ns(), time.time_ns() + 10_000_000))
    _wait(library, library.start_scan())
    row = library.conn.execute("SELECT id, caption FROM photos").fetchone()
    assert row["id"] == pid
    assert row["caption"] is None


def test_interrupted_jobs_are_not_left_running_after_restart(tmp_settings):
    lib = Library(tmp_settings, embedder=FakeEmbedder())
    lib.conn.execute(
        "INSERT INTO jobs(id, kind, status, progress, message, started_at) VALUES ('x', 'index', 'running', 0.3, '', '2020')"
    )
    lib.conn.commit()
    lib2 = Library(tmp_settings, embedder=FakeEmbedder())
    assert lib2.jobs.get("x")["status"] == "interrupted"


class _OtherEmbedder(FakeEmbedder):
    name = "other-embedder"


def test_switching_embedder_reembeds_existing_photos(tmp_settings, tmp_path):
    photos = tmp_path / "photos"
    make_image(photos / "red.jpg", color=(220, 20, 20))
    lib = Library(tmp_settings, embedder=FakeEmbedder())
    _index(lib, photos)
    assert lib.library_status()["embedder"]["stale_photos"] == 0

    lib2 = Library(tmp_settings, embedder=_OtherEmbedder())
    status = lib2.library_status()
    assert status["embedder"]["stale_photos"] == 1
    # search must not mix vectors from two different embedding spaces
    assert lib2.search("red")["results"] == []
    _wait(lib2, lib2.start_scan())
    assert lib2.library_status()["embedder"]["stale_photos"] == 0
    assert lib2.search("red")["results"][0]["path"].endswith("red.jpg")


# --------------------------------------------------------------------- #
# Search / filters / agent-facing shapes
# --------------------------------------------------------------------- #
def _dated_library(library, tmp_path):
    photos = tmp_path / "photos"
    make_image(photos / "march31.jpg", color=(220, 20, 20), taken_at=dt.datetime(2024, 3, 31, 18, 0))
    make_image(photos / "april1.jpg", color=(20, 20, 220), taken_at=dt.datetime(2024, 4, 1, 9, 0))
    make_image(photos / "march1.jpg", color=(20, 220, 20), taken_at=dt.datetime(2024, 3, 1, 9, 0))
    _index(library, photos)


def test_taken_before_with_a_plain_date_includes_that_whole_day(library, tmp_path):
    _dated_library(library, tmp_path)
    got = library.list_photos({"taken_before": "2024-03-31"})["results"]
    assert sorted(Path(r["path"]).name for r in got) == ["march1.jpg", "march31.jpg"]
    got = library.list_photos({"taken_after": "2024-03-31", "taken_before": "2024-03-31"})["results"]
    assert [Path(r["path"]).name for r in got] == ["march31.jpg"]


def test_bad_filter_values_are_validation_errors(library, tmp_path):
    _dated_library(library, tmp_path)
    for bad in ({"month": 13}, {"orientation": "square"}, {"taken_after": "last summer"}, {"year": "abc"}):
        with pytest.raises(ValidationError):
            library.search("red", bad)


def test_search_scores_are_real_cosines_and_items_carry_sheet_numbers(library, tmp_path):
    _dated_library(library, tmp_path)
    res = library.search("red", limit=2)
    assert [r["n"] for r in res["results"]] == [1, 2]
    assert res["results"][0]["path"].endswith("march31.jpg")
    assert 0 < res["results"][0]["score"] < 1.0  # a cosine, not a min-max rank
    assert res["count"] == 3 and res["has_more"] is True
    assert res["embedder"] == "fake-colorhist-v1"
    assert "colour" in res["note"]  # the model is told what the fallback can do


def test_search_limit_is_clamped(library, tmp_path):
    _dated_library(library, tmp_path)
    res = library.search("red", limit=10_000)
    assert len(res["results"]) == 3
    with pytest.raises(ValidationError):
        library.search("red", limit=0)


def test_show_reports_unknown_ids_and_caps_image_bytes(library, tmp_path):
    photos = tmp_path / "photos"
    make_image(photos / "big.jpg", size=(3000, 2000))
    _index(library, photos)
    pid = library.list_photos()["results"][0]["id"]
    out = library.show([pid, "0" * 32], size=100_000)
    assert [i["id"] for i in out["images"]] == [pid]
    assert out["not_found"] == ["0" * 32]
    import base64

    assert len(base64.b64decode(out["images"][0]["jpeg_base64"])) <= 200 * 1024


def test_duplicates_rejects_unknown_kind(library):
    with pytest.raises(ValidationError):
        library.duplicates(kind="similar")


def test_album_rejects_blank_names_and_reports_unknown_ids(library, tmp_path):
    photos = tmp_path / "photos"
    make_image(photos / "a.jpg")
    _index(library, photos)
    pid = library.list_photos()["results"][0]["id"]
    with pytest.raises(ValidationError):
        library.album("   ", [pid])
    res = library.album("Trip", [pid, "f" * 32])
    assert res["added"] == 1
    assert res["unknown_ids"] == ["f" * 32]


def test_list_photos_pages_in_sql_order(library, tmp_path):
    photos = tmp_path / "photos"
    for i in range(7):
        make_image(photos / f"p{i}.jpg", taken_at=dt.datetime(2020, 1, 1 + i))
    _index(library, photos)
    first = library.list_photos(limit=3)
    second = library.list_photos(limit=3, offset=first["next_offset"])
    third = library.list_photos(limit=3, offset=second["next_offset"])
    names = [Path(r["path"]).name for page in (first, second, third) for r in page["results"]]
    assert names == [f"p{i}.jpg" for i in range(6, -1, -1)]
    assert third["next_offset"] is None and first["count"] == 7


# --------------------------------------------------------------------- #
# Determinism and the near-duplicate index
# --------------------------------------------------------------------- #
def test_stored_captions_feed_hybrid_search(library, tmp_path, monkeypatch):
    """Captions go into the FTS table and lift matching photos (hybrid =
    0.8 cosine_norm + 0.2 bm25_norm). Two near-identical grey photos: only
    the captioned one matches the words, so it must rank above its twin."""
    from argus_hoard.captions import CaptionResult

    photos = tmp_path / "photos"
    make_image(photos / "red.jpg", color=(220, 20, 20))
    make_image(photos / "grey_a.jpg", color=(128, 128, 128))
    make_image(photos / "grey_b.jpg", color=(128, 128, 128))
    _index(library, photos)
    by_name = {Path(r["path"]).name: r["id"] for r in library.list_photos()["results"]}

    class StubCaptioner:
        def caption(self, path):
            return CaptionResult(ok=True, caption="a whiteboard with meeting notes")

    monkeypatch.setattr(library, "_captioner", lambda: StubCaptioner())
    captioned = by_name["grey_b.jpg"]
    assert library.describe(captioned, caption=True)["caption"] == "a whiteboard with meeting notes"
    # re-captioning must replace, not fail on, the FTS row that now exists
    library.conn.execute("UPDATE photos SET caption = NULL WHERE id = ?", (captioned,))
    library.conn.commit()
    library.describe(captioned, caption=True)
    assert library.conn.execute("SELECT COUNT(*) c FROM photos_fts").fetchone()["c"] == 1

    for query in ("whiteboard notes", "grey whiteboard"):
        ids = [r["id"] for r in library.search(query)["results"]]
        assert ids.index(captioned) < ids.index(by_name["grey_a.jpg"]), query
    hit = next(r for r in library.search("whiteboard")["results"] if r["id"] == captioned)
    assert hit["caption_match"] is True


def test_every_supported_format_is_indexed_and_previewed(library, tmp_path):
    from argus_hoard.formats import HEIF_AVAILABLE

    photos = tmp_path / "photos"
    formats = {"a.png": "PNG", "b.webp": "WEBP", "c.gif": "GIF", "d.tif": "TIFF", "e.bmp": "BMP", "f.jpeg": "JPEG"}
    if HEIF_AVAILABLE:
        formats["g.heic"] = "HEIF"
    for name, fmt in formats.items():
        make_image(photos / name, size=(320, 240), fmt=fmt)
    root = library.add_root(str(photos))
    job = _wait(library, library.start_scan(root["id"]))
    assert job["stats"]["errors"] == 0, job["stats"]
    rows = library.list_photos()["results"]
    assert sorted(Path(r["path"]).name for r in rows) == sorted(formats)
    for r in rows:
        assert r["width"] == 320 and r["height"] == 240
        assert library.render_preview(r["id"], size=200)[:2] == b"\xff\xd8"  # browsers get a JPEG


def test_search_says_when_photos_are_not_embedded_with_the_current_model(tmp_settings, tmp_path):
    photos = tmp_path / "photos"
    make_image(photos / "red.jpg", color=(220, 20, 20))
    make_image(photos / "blue.jpg", color=(20, 20, 220))
    lib = Library(tmp_settings, embedder=FakeEmbedder())
    _index(lib, photos)

    class SemanticStub:  # not a FakeEmbedder: behaves like a real model
        name = "semantic-stub"
        dim = FakeEmbedder.dim

        def __init__(self):
            self._inner = FakeEmbedder()

        def embed_images(self, paths):
            return self._inner.embed_images(paths)

        def embed_text(self, text):
            return self._inner.embed_text(text)

    lib2 = Library(tmp_settings, embedder=SemanticStub())
    res = lib2.search("red")
    assert res["results"] == []
    assert "2 photos are not analysed" in res["note"]
