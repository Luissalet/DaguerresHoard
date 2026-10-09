"""Test helpers for the video key-frame feature: a fake extractor (no ffmpeg needed) and a stand-in video file."""
from __future__ import annotations

import os
from pathlib import Path

from daguerre_hoard.video_frames import ExtractedFrame, Extraction, VideoInfo
from tests.conftest import make_image


class FakeExtractor:
    """Writes one noisy JPEG per (timestamp, colour) pair; counts how often it is asked to extract."""

    name = "fake"

    def __init__(self, frames=((0.5, (20, 20, 220)), (12.5, (20, 200, 20))), duration=20.0, available=True,
                 created="2024-05-04T10:00:00+00:00"):
        self.frames = list(frames)
        self.duration = duration
        self.available = available
        self.created = created
        self.calls: list[Path] = []
        self.last_args: tuple | None = None

    def extract(self, path, out_dir, max_frames=48, interval_s=30.0):
        self.calls.append(Path(path))
        self.last_args = (max_frames, interval_s)
        info = VideoInfo(duration=self.duration, width=320, height=240, created=self.created)
        out = []
        for i, (ts, color) in enumerate(self.frames[:max_frames]):
            dest = out_dir / f"{i:03d}_{int(ts * 1000)}.jpg"
            make_image(dest, color=color)
            out.append(ExtractedFrame(ts=ts, path=dest))
        return Extraction(info=info, frames=out)


def make_fake_video(path: Path, seed: int = 1, size: int = 40_000) -> Path:
    """A file with a video extension and some bytes: enough for the walker and the quick hash (the fake never decodes)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(os.urandom(8) + bytes([seed % 256]) * size)
    return path
