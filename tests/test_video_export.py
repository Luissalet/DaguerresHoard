"""Real CPU media through the same Library/UI operation, using invented clips."""
import io
import json
import shutil
import subprocess

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from daguerre_hoard.api import create_app
from daguerre_hoard.library import ValidationError
from tests.test_library import _index_sync


def make_clip(path, audio=True):
    path.parent.mkdir(parents=True, exist_ok=True)
    graph = "".join(f"color=c={color}:s=160x120:r=20:d=1,noise=alls=12:allf=t[v{i}];"
                    for i, color in enumerate(("red", "green", "blue", "yellow")))
    graph += "[v0][v1][v2][v3]concat=n=4:v=1:a=0[v]"
    args = ["ffmpeg", "-hide_banner", "-nostdin", "-v", "error"]
    if audio:
        args += ["-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=4"]
    args += ["-filter_complex", graph, "-map", "[v]", "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p"]
    if audio:
        args += ["-map", "0:a:0", "-c:a", "aac"]
    subprocess.run([*args, str(path)], capture_output=True, check=True)
    return path


def pixel(path, at):
    raw = subprocess.check_output(["ffmpeg", "-v", "error", "-ss", str(at), "-i", str(path),
                                   "-frames:v", "1", "-f", "image2pipe", "-c:v", "png", "-"])
    with Image.open(io.BytesIO(raw)) as image:
        return image.convert("RGB").getpixel((80, 60))


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="optional FFmpeg/ffprobe missing")
def test_real_interval_api_download_audio_and_source_preservation(library, tmp_path):
    source = make_clip(tmp_path / "originals" / "invented.mp4")
    _index_sync(library, source.parent)
    video = library.list_videos()["results"][0]
    before = source.read_bytes(), source.stat().st_mtime_ns
    rows = [tuple(row) for row in library.conn.execute("SELECT * FROM videos ORDER BY id")]
    app = create_app(library.settings.data_dir, port=18865, automatic=False)
    with TestClient(app, base_url="http://127.0.0.1:18865") as client:
        result = client.post(f"/api/videos/{video['id']}/export", json={"video_id": video["id"], "start_s": 1.25, "end_s": 3.25})
        assert result.status_code == 200, result.text
        receipt = result.json()
        assert receipt["requested"] == {"start_s": 1.25, "end_s": 3.25, "duration_s": 2.0}
        assert 1.95 <= receipt["measured"]["duration_s"] <= 2.10  # 20fps + AAC/container timing
        output = library.settings.data_dir / "exports" / receipt["id"] / "clip.mp4"
        downloaded = client.get(receipt["video_url"])
        assert downloaded.status_code == 200 and downloaded.content == output.read_bytes()
        assert client.get(receipt["manifest_url"]).json() == receipt
        streams = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(output)]))["streams"]
        assert [s["codec_name"] for s in streams] == ["h264", "aac"]
        green, blue, yellow = (pixel(output, at) for at in (0.2, 1.0, 1.9))
        assert green[1] > green[0] + 40 and green[1] > green[2] + 40
        assert blue[2] > blue[0] + 80 and blue[2] > blue[1] + 80
        assert yellow[0] > yellow[2] + 80 and yellow[1] > yellow[2] + 80
    assert (source.read_bytes(), source.stat().st_mtime_ns) == before
    assert [tuple(row) for row in library.conn.execute("SELECT * FROM videos ORDER BY id")] == rows


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="optional FFmpeg missing")
def test_silent_interval_and_invalid_bounds_do_not_edit_source(library, tmp_path, monkeypatch):
    from daguerre_hoard.video_frames import FfmpegExtractor

    source = make_clip(tmp_path / "originals" / "silent.mp4", audio=False)
    _index_sync(library, source.parent)
    video = library.list_videos()["results"][0]
    before = source.read_bytes(), source.stat().st_mtime_ns
    for start, end in [(2, 1), (-1, 2), (0, 5), (float("nan"), 2), (0, float("inf"))]:
        with pytest.raises(ValidationError):
            library.export_video_clip(video["id"], start, end)
    receipt = library.export_video_clip(video["id"], 1.25, 3.25)
    assert receipt["measured"]["width"] == 160 and receipt["bytes"] > 0
    monkeypatch.setattr(FfmpegExtractor, "_find", staticmethod(lambda *args: None))
    with pytest.raises(ValidationError, match="FFmpeg is unavailable"):
        library.export_video_clip(video["id"], 0, 1)
    assert (source.read_bytes(), source.stat().st_mtime_ns) == before
