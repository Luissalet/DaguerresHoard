"""One transcoded interval, retained as a derived export, never an original edit."""
from __future__ import annotations

import io
import math
import subprocess
import uuid
from pathlib import Path

from PIL import Image

from .hoard_link.atomic import write_json_atomic
from .video_frames import FRAME_TIMEOUT_S, FfmpegExtractor


def create(library, video_id: str, start_s: float, end_s: float) -> dict:
    from .library import ValidationError

    if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
               for v in (start_s, end_s)) or not 0 <= start_s < end_s:
        raise ValidationError("start_s and end_s must be finite seconds with 0 <= start_s < end_s")
    source = library.video_file(video_id)
    extractor = FfmpegExtractor()
    if not extractor.available:
        raise ValidationError("FFmpeg is unavailable. Configure DAGUERRE_FFMPEG or install FFmpeg, then retry.")
    info = extractor.probe(source)
    if info.duration is None or not math.isfinite(info.duration) or info.duration <= 0:
        raise ValidationError("The video's duration could not be read; the interval cannot be exported.")
    if end_s > info.duration:
        raise ValidationError(f"end_s must not exceed the video's measured duration ({info.duration} seconds)")

    export_id = uuid.uuid4().hex
    folder = library.settings.data_dir / "exports" / export_id
    folder.mkdir(parents=True)
    partial = folder / "clip.partial.mp4"
    output = folder / "clip.mp4"
    try:
        proc = extractor._run([
            extractor.ffmpeg, "-hide_banner", "-nostdin", "-v", "error",
            "-ss", str(start_s), "-i", str(source), "-t", str(end_s - start_s),
            "-map", "0:v:0", "-map", "0:a:0?", "-sn", "-dn",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-map_metadata", "-1", "-movflags", "+faststart", str(partial),
        ], FRAME_TIMEOUT_S)
        if proc.returncode or not partial.is_file() or not partial.stat().st_size:
            detail = proc.stderr.decode("utf-8", "replace").strip()[-1000:]
            raise ValidationError(f"FFmpeg could not export the interval: {detail or 'no video output'}")
        measured = extractor.probe(partial)
        # Decode a real output frame as well as probing the container. An empty or
        # unreadable video must not become a successful download receipt.
        frame = extractor._run([
            extractor.ffmpeg, "-hide_banner", "-nostdin", "-v", "error", "-i", str(partial),
            "-map", "0:v:0", "-frames:v", "1", "-f", "image2pipe", "-c:v", "png", "-",
        ], FRAME_TIMEOUT_S)
        if frame.returncode or measured.duration is None or not math.isfinite(measured.duration) or measured.duration <= 0:
            raise ValidationError("FFmpeg produced no readable video interval; no export was accepted.")
        try:
            with Image.open(io.BytesIO(frame.stdout)) as image:
                image.load()
                width, height = image.size
        except (OSError, ValueError) as exc:
            raise ValidationError("The exported video frame could not be decoded; no export was accepted.") from exc

        receipt = {
            "id": export_id, "video_id": video_id, "source_name": source.name,
            "requested": {"start_s": start_s, "end_s": end_s, "duration_s": end_s - start_s},
            "measured": {"duration_s": measured.duration, "width": width, "height": height},
            "format": {"container": "mp4", "video_codec": "h264", "audio_policy": "first_if_present"},
            "bytes": partial.stat().st_size,
            "video_url": f"/api/exports/{export_id}/clip.mp4",
            "manifest_url": f"/api/exports/{export_id}/manifest.json",
        }
        write_json_atomic(folder / "manifest.json", receipt)
        partial.replace(output)
        return receipt
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValidationError(f"FFmpeg could not export the interval: {exc}") from exc
    finally:
        # Only this invocation's unfinished file is removed, never a source or
        # another export. Successful outputs and their receipt remain retained.
        partial.unlink(missing_ok=True)
