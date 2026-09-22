from __future__ import annotations

import datetime as dt
import os
import shutil
import time

from tests.conftest import make_image


def _wait_job(library, job_id, timeout=10.0):
    start = time.time()
    while time.time() - start < timeout:
        job = library.jobs.get(job_id)
        if job and job["status"] in ("done", "error"):
            return job
        time.sleep(0.02)
    raise TimeoutError(f"job {job_id} did not finish in time: {library.jobs.get(job_id)}")


def _index_sync(library, root_path):
    root = library.add_root(str(root_path))
    job_id = library.start_scan(root["id"])
    job = _wait_job(library, job_id)
    assert job["status"] == "done", job
    return root


def test_full_index_preserves_original_files(library, tmp_path):
    photos_dir = tmp_path / "photos"
    p1 = make_image(photos_dir / "a.jpg", color=(200, 20, 20))
    p2 = make_image(photos_dir / "b.jpg", color=(20, 200, 20))

    before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in (p1, p2)}
    _index_sync(library, photos_dir)

    # Exercise duplicates + album on top of the freshly indexed library.
    library.duplicates(kind="exact")
    photo_ids = [r["id"] for r in library.list_photos()["results"]]
    library.album("Test album", photo_ids)

    for p, (data, mtime) in before.items():
        assert p.read_bytes() == data
        assert p.stat().st_mtime_ns == mtime


def test_incremental_rescan_skips_unchanged_files(library, tmp_path, monkeypatch):
    photos_dir = tmp_path / "photos"
    make_image(photos_dir / "a.jpg")
    make_image(photos_dir / "b.jpg")
    root = _index_sync(library, photos_dir)

    calls = []
    from argus_hoard import hashing

    original = hashing.content_hash

    def spy(path):
        calls.append(path)
        return original(path)

    monkeypatch.setattr(hashing, "content_hash", spy)
    # library._index_one references the module-level function directly via
    # `from .hashing import content_hash`, so patch that binding too.
    import argus_hoard.library as library_mod

    monkeypatch.setattr(library_mod, "content_hash", spy)

    job_id = library.start_scan(root["id"])
    _wait_job(library, job_id)
    assert calls == []  # nothing changed since the first scan: no re-hashing


def test_moved_file_keeps_its_id(library, tmp_path):
    photos_dir = tmp_path / "photos"
    p = make_image(photos_dir / "sub" / "a.jpg", color=(50, 60, 70))
    root = _index_sync(library, photos_dir)

    before = library.list_photos()["results"]
    assert len(before) == 1
    old_id = before[0]["id"]

    new_path = photos_dir / "sub" / "renamed.jpg"
    shutil.move(str(p), str(new_path))

    job_id = library.start_scan(root["id"])
    _wait_job(library, job_id)

    after = library.list_photos()["results"]
    assert len(after) == 1
    assert after[0]["id"] == old_id
    assert after[0]["path"] == str(new_path)


def test_search_and_similar_use_fake_embedder(library, tmp_path):
    photos_dir = tmp_path / "photos"
    make_image(photos_dir / "red.jpg", color=(220, 20, 20))
    make_image(photos_dir / "green.jpg", color=(20, 200, 20))
    _index_sync(library, photos_dir)

    result = library.search("a red square", limit=5, contact_sheet=True)
    assert result["count"] >= 1
    assert result["results"][0]["path"].endswith("red.jpg")
    assert result["contact_sheet_jpeg_base64"] is not None

    red_id = result["results"][0]["id"]
    similar = library.similar(photo_id=red_id, limit=5)
    assert all(r["id"] != red_id for r in similar["results"])
