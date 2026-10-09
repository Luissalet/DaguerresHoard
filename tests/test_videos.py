from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from daguerre_hoard.api import create_app
from daguerre_hoard.embeddings import FakeEmbedder
from daguerre_hoard.video_frames import FfmpegExtractor, format_ts, plan_times
from tests.conftest import agent_headers, make_image
from tests.test_library import _index_sync, _wait_job
from tests.video_fakes import FakeExtractor, make_fake_video

PORT = 18851


# --------------------------------------------------------------------------- #
# Frame planning (pure)
# --------------------------------------------------------------------------- #
def test_format_ts():
    assert format_ts(83.4) == "01:23"
    assert format_ts(0) == "00:00"
    assert format_ts(3723) == "1:02:03"
    assert format_ts(None) == "00:00"


def test_plan_times_scenes_then_grid_fallback():
    # a static 100 s clip with no scene change still gets a frame every ~30 s
    times = plan_times(100.0, [], interval_s=30.0, max_frames=48)
    assert times[0] == 0.5 and 30.0 in times and 60.0 in times and 90.0 in times
    # scene changes are kept; a grid frame within 2 s of a scene frame is dropped
    times = plan_times(100.0, [31.0, 70.0], interval_s=30.0, max_frames=48)
    assert 31.0 in times and 70.0 in times and 30.0 not in times and 60.0 in times


def test_plan_times_cap_and_edges():
    scenes = [float(i) for i in range(5, 500, 3)]
    times = plan_times(600.0, scenes, interval_s=10.0, max_frames=10)
    assert len(times) <= 10 and times == sorted(times)
    assert plan_times(None, [1.0]) == [0.0]
    assert plan_times(0.0, []) == [0.0]
    assert plan_times(5.0, [99.0], max_frames=3)[-1] < 5.0  # scene past the end is clamped inside the video
    assert len(plan_times(600.0, [], interval_s=10.0, max_frames=1)) == 1


# --------------------------------------------------------------------------- #
# Indexing with a fake extractor
# --------------------------------------------------------------------------- #
@pytest.fixture()
def vlib(library):
    library.frame_extractor = FakeExtractor()
    return library


def _setup(vlib, tmp_path):
    root_dir = tmp_path / "media"
    make_image(root_dir / "photo.jpg", color=(220, 20, 20))
    video = make_fake_video(root_dir / "trips" / "Beach_Day-2024.mp4")
    root = _index_sync(vlib, root_dir)
    return root, root_dir, video


def test_scan_indexes_frames_linked_to_the_video(vlib, tmp_path):
    root, _, video = _setup(vlib, tmp_path)
    videos = vlib.list_videos()
    assert videos["count"] == 1
    v = videos["results"][0]
    assert v["name"] == "Beach_Day-2024.mp4" and v["frame_count"] == 2 and v["status"] == "ok"
    assert v["duration"] == 20.0 and v["duration_label"] == "00:20" and v["thumbnail_url"]
    detail = vlib.get_video(v["id"])
    assert [f["timestamp"] for f in detail["frames"]] == ["00:00", "00:12"]
    assert [f["ts"] for f in detail["frames"]] == [0.5, 12.5]
    # frames use the photo pipeline: thumbnail + embedding exist
    for f in detail["frames"]:
        assert (vlib.settings.thumbs_dir / f["id"][:2] / f"{f['id']}.webp").exists()
        row = vlib.conn.execute("SELECT embed_row, embed_model, phash, video_id FROM photos WHERE id = ?", (f["id"],)).fetchone()
        assert row["embed_row"] is not None and row["embed_model"] == vlib.embedder.name and row["phash"]
        assert row["video_id"] == v["id"]
    assert vlib.get_video(v["id"], frames_limit=1)["has_more_frames"] is True


def test_frames_are_hidden_from_photo_views_but_found_by_search(vlib, tmp_path):
    root, _, video = _setup(vlib, tmp_path)
    assert vlib.list_photos()["count"] == 1  # the grid shows photos only
    assert vlib.library_status()["photo_count"] == 1
    status = vlib.library_status()
    assert status["video_count"] == 1 and status["frame_count"] == 2
    assert vlib.list_roots()[0]["photo_count"] == 1 and vlib.list_roots()[0]["video_count"] == 1
    assert vlib.duplicates("exact")["total_groups"] == 0
    assert sum(vlib.timeline()["years"].values()) == 1
    # a text search ranks frames among photos and says where they come from
    res = vlib.search("blue", limit=5)["results"]
    top = res[0]
    assert top["timestamp"] == "00:00" and top["frame_ts"] == 0.5 and top["video_name"] == "Beach_Day-2024.mp4"
    assert top["path"] == str(video) and top["video_id"]
    # the frame filter
    only = vlib.search("blue", {"frames": "only"})["results"]
    assert only and all("video_id" in r for r in only)
    excl = vlib.search("blue", {"frames": "exclude"})["results"]
    assert len(excl) == 1 and "video_id" not in excl[0]
    assert vlib.list_photos({"frames": "only"})["count"] == 2
    with pytest.raises(Exception):
        vlib.validate_filters({"frames": "nope"})
    # frames are searchable by the video's file name even before any caption
    named = vlib.search("beach", {"frames": "only"})["results"]
    assert named and named[0].get("caption_match") is True
    # similar works from a frame and finds other frames/photos; describe carries the timestamp
    fid = top["id"]
    assert vlib.similar(photo_id=fid)["results"]
    d = vlib.describe(fid)
    assert d["timestamp"] == "00:00" and d["video_id"]
    # frames can be filed in albums like photos
    assert vlib.album("From video", [fid])["added"] == 1


def test_rescan_is_incremental_and_follows_changes(vlib, tmp_path):
    root, root_dir, video = _setup(vlib, tmp_path)
    fx = vlib.frame_extractor
    assert len(fx.calls) == 1
    _wait_job(vlib, vlib.start_scan(root["id"]))
    assert len(fx.calls) == 1  # unchanged video is not touched again
    vid = vlib.list_videos()["results"][0]["id"]

    # same bytes with a new mtime: still no extraction
    st = video.stat()
    import os
    os.utime(video, ns=(st.st_atime_ns, st.st_mtime_ns + 5_000_000_000))
    _wait_job(vlib, vlib.start_scan(root["id"]))
    assert len(fx.calls) == 1

    # new content: frames are rebuilt (old frame rows are gone, album memberships with them)
    old = {f["id"] for f in vlib.get_video(vid)["frames"]}
    make_fake_video(video, seed=7, size=50_000)
    fx.frames = [(1.0, (200, 200, 20)), (5.0, (20, 200, 200)), (9.0, (200, 20, 200))]
    _wait_job(vlib, vlib.start_scan(root["id"]))
    assert len(fx.calls) == 2
    new = vlib.get_video(vid)
    assert new["frame_count"] == 3 and not old & {f["id"] for f in new["frames"]}
    assert vlib.conn.execute("SELECT COUNT(*) c FROM photos WHERE video_id = ?", (vid,)).fetchone()["c"] == 3

    # changed extraction settings re-extract (and are honoured)
    vlib.set_video_settings(max_frames=2, interval_s=10)
    _wait_job(vlib, vlib.start_scan(root["id"]))
    assert len(fx.calls) == 3 and fx.last_args == (2, 10.0)
    assert vlib.get_video(vid)["frame_count"] == 2


def test_missing_and_moved_videos(vlib, tmp_path):
    root, root_dir, video = _setup(vlib, tmp_path)
    fx = vlib.frame_extractor
    vid = vlib.list_videos()["results"][0]["id"]
    # moved: same bytes under a new name keeps the id and the frames, no extraction
    moved = root_dir / "renamed.mp4"
    shutil.move(str(video), str(moved))
    _wait_job(vlib, vlib.start_scan(root["id"]))
    assert len(fx.calls) == 1
    got = vlib.get_video(vid)
    assert got["path"] == str(moved) and got["frame_count"] == 2
    # deleted: hidden from the lists and from search, never destroyed
    moved.unlink()
    _wait_job(vlib, vlib.start_scan(root["id"]))
    assert vlib.list_videos()["count"] == 0
    assert vlib.search("blue", {"frames": "only"})["results"] == []
    assert vlib.conn.execute("SELECT COUNT(*) c FROM videos WHERE id = ?", (vid,)).fetchone()["c"] == 1


def test_without_ffmpeg_the_video_is_listed_and_retried_later(vlib, tmp_path):
    fx = vlib.frame_extractor
    fx.available = False
    root, _, _ = _setup(vlib, tmp_path)
    listing = vlib.list_videos()
    assert listing["count"] == 1 and "ffmpeg" in listing["note"]
    v = listing["results"][0]
    assert v["status"] == "no_extractor" and v["frame_count"] == 0 and v["thumbnail_url"] is None
    assert vlib.library_status()["video_frames"]["extractor"] is None
    assert fx.calls == []
    fx.available = True  # ffmpeg shows up: the next scan picks the video up without a file change
    _wait_job(vlib, vlib.start_scan(root["id"]))
    assert vlib.list_videos()["results"][0]["frame_count"] == 2


def test_disabled_and_failed_extraction(vlib, tmp_path):
    vlib.set_video_settings(enabled=False)
    root, root_dir, _ = _setup(vlib, tmp_path)
    assert vlib.list_videos()["count"] == 0
    vlib.set_video_settings(enabled=True)
    vlib.frame_extractor.frames = []  # extractor runs but yields nothing
    _wait_job(vlib, vlib.start_scan(root["id"]))
    v = vlib.list_videos()["results"][0]
    assert v["status"] == "error" and v["error"]
    with pytest.raises(Exception):
        vlib.set_video_settings(max_frames=0)
    with pytest.raises(Exception):
        vlib.set_video_settings(interval_s=0.1)


def test_remove_root_forgets_frames(vlib, tmp_path):
    root, _, _ = _setup(vlib, tmp_path)
    vid = vlib.list_videos()["results"][0]["id"]
    assert (vlib.settings.frames_dir / vid).is_dir()
    vlib.remove_root(root["id"])
    assert not (vlib.settings.frames_dir / vid).exists()
    assert vlib.conn.execute("SELECT COUNT(*) c FROM videos").fetchone()["c"] == 0
    assert vlib.conn.execute("SELECT COUNT(*) c FROM photos").fetchone()["c"] == 0


# --------------------------------------------------------------------------- #
# HTTP API (UI routes and agent routes)
# --------------------------------------------------------------------------- #
@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr("daguerre_hoard.library.select_embedder", lambda settings: FakeEmbedder())
    app = create_app(data_dir=tmp_path / "data", static_dir=None, port=PORT)
    lib = app.state.library
    lib.frame_extractor = FakeExtractor()
    root_dir = tmp_path / "media"
    make_image(root_dir / "photo.jpg", color=(220, 20, 20))
    make_fake_video(root_dir / "clip.mp4")
    root = lib.add_root(str(root_dir))
    _wait_job(lib, lib.start_scan(root["id"]))
    with TestClient(app, base_url=f"http://127.0.0.1:{PORT}", headers=agent_headers(app)) as c:
        yield c


def test_video_routes(client):
    listing = client.get("/api/videos").json()
    assert listing["count"] == 1
    v = listing["results"][0]
    assert v["stream_url"].endswith("/stream") and v["thumbnail_url"].startswith("/api/photos/")
    detail = client.get(f"/api/videos/{v['id']}").json()
    assert [f["timestamp"] for f in detail["frames"]] == ["00:00", "00:12"]
    assert client.get(detail["frames"][0]["thumbnail_url"]).status_code == 200
    assert client.get(f"/api/photos/{detail['frames'][0]['id']}/preview").status_code == 200
    # the player streams the original with Range support, so it can seek
    full = client.get(v["stream_url"])
    assert full.status_code == 200 and len(full.content) > 30_000
    part = client.get(v["stream_url"], headers={"Range": "bytes=10-19"})
    assert part.status_code == 206 and len(part.content) == 10
    assert client.get("/api/videos/" + "0" * 32).status_code == 404
    assert client.get("/api/videos/not-an-id").status_code == 404
    assert client.get("/api/videos/" + "0" * 32 + "/stream").status_code == 404
    # frames are not in the photo grid unless asked
    assert client.get("/api/photos").json()["count"] == 1
    assert client.get("/api/photos?frames=only").json()["count"] == 2
    assert client.get("/api/photos?frames=bad").status_code == 400
    # the UI search result carries what the card needs
    res = client.post("/api/search", json={"query": "blue", "filters": {}, "limit": 3}).json()["results"][0]
    assert res["timestamp"] == "00:00" and res["video_id"] == v["id"] and res["thumbnail_url"]
    health = client.get("/api/health").json()
    assert health["photo_count"] == 1 and health["video_count"] == 1
    s = client.post("/api/video-settings", json={"max_frames": 10, "interval_s": 5}).json()
    assert s["max_frames"] == 10 and s["interval_s"] == 5.0 and s["extractor"] == "fake"
    assert client.post("/api/video-settings", json={"max_frames": 9999}).status_code == 400


def test_open_in_explorer_targets_the_video_for_a_frame(client, monkeypatch):
    seen = []
    monkeypatch.setattr("daguerre_hoard.api.proc.reveal_in_file_manager", lambda p: seen.append(p) or True)
    v = client.get("/api/videos").json()["results"][0]
    fid = client.get(f"/api/videos/{v['id']}").json()["frames"][0]["id"]
    assert client.post(f"/api/photos/{fid}/open").json() == {"ok": True}
    assert seen[0].name == "clip.mp4"


def test_agent_video_tools_are_authenticated_audited_and_urlless(client):
    bare = TestClient(client.app, base_url=f"http://127.0.0.1:{PORT}")
    assert bare.post("/api/agent/videos_list", json={}).status_code == 401
    assert bare.post("/api/agent/videos_describe", json={"video_id": "x"}).status_code == 401
    names = {t["name"] for t in bare.get("/api/agent/tools").json()["tools"]}
    assert {"videos_list", "videos_describe"} <= names

    lst = client.post("/api/agent/videos_list", json={}).json()
    assert lst["count"] == 1 and "thumbnail_url" not in lst["results"][0] and "stream_url" not in lst["results"][0]
    vid = lst["results"][0]["id"]
    det = client.post("/api/agent/videos_describe", json={"video_id": vid}).json()
    assert [f["timestamp"] for f in det["frames"]] == ["00:00", "00:12"] and "thumbnail_url" not in det["frames"][0]
    short = client.post("/api/agent/videos_describe", json={"video_id": vid, "frames_limit": 1}).json()
    assert len(short["frames"]) == 1 and short["has_more_frames"]
    bad = client.post("/api/agent/videos_describe", json={"video_id": "0" * 32})
    assert bad.status_code == 404 and "videos_list" in bad.json()["message"]
    assert client.post("/api/agent/videos_list", json={"folder": "nomatch"}).json()["count"] == 0

    s = client.post("/api/agent/photos_search", json={"query": "blue", "limit": 3}).json()["results"][0]
    assert s["timestamp"] == "00:00" and s["video_id"] == vid and "thumbnail_url" not in s
    only = client.post("/api/agent/photos_search", json={"query": "blue", "filters": {"frames": "exclude"}}).json()
    assert all("video_id" not in r for r in only["results"])
    calls = {c["tool"] for c in client.get("/api/agent-calls").json()}
    assert {"videos_list", "videos_describe"} <= calls


# --------------------------------------------------------------------------- #
# Real ffmpeg on a tiny generated video
# --------------------------------------------------------------------------- #
HAVE_FFMPEG = bool(shutil.which("ffmpeg"))


def _make_video(path: Path) -> None:
    """Three 3-second noisy colour blocks (red, yellow, blue; far apart in brightness so the cuts score high):\n    two hard scene changes, 9 s total."""
    parts = "".join(
        f"color=c={c}:s=320x240:r=10:d=3,noise=alls=20:allf=t,format=yuv420p[v{i}];"
        for i, c in enumerate(("red", "yellow", "blue"))
    )
    graph = parts + "[v0][v1][v2]concat=n=3:v=1:a=0[out]"
    path.parent.mkdir(parents=True, exist_ok=True)
    for codec in ("libx264", "mpeg4"):
        proc = subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-filter_complex", graph, "-map", "[out]",
             "-c:v", codec, str(path)],
            capture_output=True,
        )
        if proc.returncode == 0:
            return
    raise RuntimeError(proc.stderr.decode("utf-8", "replace"))


@pytest.mark.skipif(not HAVE_FFMPEG, reason="ffmpeg is not installed")
def test_real_ffmpeg_extracts_scene_frames(tmp_path):
    video = tmp_path / "blocks.mp4"
    _make_video(video)
    ex = FfmpegExtractor()
    assert ex.available
    result = ex.extract(video, tmp_path / "out", max_frames=12, interval_s=30)
    assert result.info.duration and 8.5 < result.info.duration < 9.5
    assert result.info.width == 320 and result.info.height == 240
    times = [f.ts for f in result.frames]
    assert len(times) >= 3
    assert any(2.5 <= t <= 3.5 for t in times) and any(5.5 <= t <= 6.5 for t in times)  # the two cuts
    assert all(f.path.is_file() and f.path.stat().st_size > 1000 for f in result.frames)


@pytest.mark.skipif(not HAVE_FFMPEG, reason="ffmpeg is not installed")
def test_real_ffmpeg_end_to_end_scan_and_search(library, tmp_path):
    root_dir = tmp_path / "media"
    _make_video(root_dir / "blocks.mp4")
    assert library.frame_extractor.available
    _index_sync(library, root_dir)
    v = library.list_videos()["results"][0]
    assert v["status"] == "ok" and v["frame_count"] >= 3 and v["width"] == 320
    assert library.list_photos()["count"] == 0
    # (the colour-histogram test embedder is too coarse to rank noisy video frames by colour, so check coverage)
    hits = library.search("blue", {"frames": "only"}, limit=20)["results"]
    stamps = sorted(h["frame_ts"] for h in hits)
    assert len(stamps) == v["frame_count"] and stamps[0] < 3.0 and stamps[-1] >= 5.5
    assert {h["video_id"] for h in hits} == {v["id"]} and all(h["timestamp"] for h in hits)
