"""Key-frame extraction for videos in the library roots.

Frames are picked at scene changes (ffmpeg's ``scene`` score), plus a frame every N seconds as a fallback for
static footage, capped per video. Each frame becomes a JPEG under ``data/frames/<video id>/`` (derived data; the
original video is only ever read). ffmpeg/ffprobe are looked up on PATH (or ``DAGUERRE_FFMPEG`` /
``DAGUERRE_FFPROBE``); when ffmpeg is missing the extractor reports ``available = False`` and the library degrades
to listing the video without frames instead of failing the scan.

The ``Extractor`` protocol is what ``Library`` talks to, so tests can swap in a fake one.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)

DEFAULT_MAX_FRAMES = 48
DEFAULT_INTERVAL_S = 30.0
SCENE_THRESHOLD = 0.3
MIN_GAP_S = 2.0
FRAME_LONG_SIDE = 1280
SCENE_TIMEOUT_S = 240
FRAME_TIMEOUT_S = 60
_PTS_RE = re.compile(r"pts_time:\s*([0-9]+(?:\.[0-9]+)?)")
_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")


@dataclass
class VideoInfo:
    duration: float | None = None
    width: int | None = None
    height: int | None = None
    created: str | None = None  # ISO timestamp from the container tags, when present


@dataclass
class ExtractedFrame:
    ts: float
    path: Path


@dataclass
class Extraction:
    info: VideoInfo
    frames: list[ExtractedFrame] = field(default_factory=list)


def format_ts(seconds: float | None) -> str:
    """``83.4`` -> ``01:23``; one hour or more -> ``1:02:03``."""
    s = int(max(0.0, float(seconds or 0.0)))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m:02d}:{sec:02d}"


def _evenly(items: list[float], count: int) -> list[float]:
    """``count`` items spread evenly over a sorted list (first and last kept)."""
    if count <= 0:
        return []
    if len(items) <= count:
        return list(items)
    if count == 1:
        return [items[0]]
    return [items[round(i * (len(items) - 1) / (count - 1))] for i in range(count)]


def plan_times(
    duration: float | None,
    scenes: list[float],
    interval_s: float = DEFAULT_INTERVAL_S,
    max_frames: int = DEFAULT_MAX_FRAMES,
    min_gap_s: float = MIN_GAP_S,
) -> list[float]:
    """Pick the timestamps to extract: scene changes first, then a grid frame every ``interval_s`` seconds where no
    scene frame is within ``min_gap_s``, then the opening frame; never more than ``max_frames``. Pure function."""
    max_frames = max(1, int(max_frames))
    interval_s = max(1.0, float(interval_s))
    if not duration or duration <= 0:
        return [0.0]
    last = max(0.0, duration - 0.25)
    scene_times = sorted({round(min(max(0.0, float(s)), last), 3) for s in scenes})
    chosen = _evenly(scene_times, max_frames)
    grid: list[float] = [min(0.5, last)]
    t = interval_s
    while t < duration - 0.5:
        grid.append(t)
        t += interval_s
    extras = [g for g in grid if all(abs(g - c) >= min_gap_s for c in chosen)]
    slots = max_frames - len(chosen)
    if slots > 0 and extras:
        chosen = chosen + _evenly(extras, slots)  # keeps the opening frame (first extra) whenever a slot is left
    return sorted(set(chosen))[:max_frames]


class FfmpegExtractor:
    """Extractor backed by the ffmpeg/ffprobe executables."""

    name = "ffmpeg"

    def __init__(self, ffmpeg: str | None = None, ffprobe: str | None = None):
        self.ffmpeg = ffmpeg or self._find("DAGUERRE_FFMPEG", "ffmpeg")
        self.ffprobe = ffprobe or self._find("DAGUERRE_FFPROBE", "ffprobe")

    @staticmethod
    def _find(env: str, exe: str) -> str | None:
        given = os.environ.get(env, "").strip()
        if given and Path(given).is_file():
            return given
        return shutil.which(exe)

    @property
    def available(self) -> bool:
        return bool(self.ffmpeg)

    # -- subprocess helper: no console window on Windows, never a shell ------- #
    def _run(self, args: list[str], timeout: float) -> subprocess.CompletedProcess:
        kwargs: dict = {}
        if sys.platform == "win32":
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        return subprocess.run(args, capture_output=True, timeout=timeout, stdin=subprocess.DEVNULL, **kwargs)

    def probe(self, path: Path) -> VideoInfo:
        info = VideoInfo()
        if self.ffprobe:
            try:
                proc = self._run(
                    [self.ffprobe, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
                    30,
                )
                data = json.loads(proc.stdout.decode("utf-8", "replace") or "{}")
                fmt = data.get("format", {})
                if fmt.get("duration"):
                    info.duration = float(fmt["duration"])
                for stream in data.get("streams", []):
                    if stream.get("codec_type") == "video":
                        info.width, info.height = stream.get("width"), stream.get("height")
                        if info.duration is None and stream.get("duration"):
                            info.duration = float(stream["duration"])
                        break
                info.created = _parse_created((fmt.get("tags") or {}).get("creation_time"))
                return info
            except (OSError, ValueError, subprocess.SubprocessError):
                log.debug("ffprobe failed for %s", path, exc_info=True)
        # no ffprobe: read the duration from `ffmpeg -i`'s banner
        try:
            proc = self._run([self.ffmpeg, "-hide_banner", "-nostdin", "-i", str(path)], 30)
            m = _DURATION_RE.search(proc.stderr.decode("utf-8", "replace"))
            if m:
                info.duration = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
        except (OSError, subprocess.SubprocessError):
            pass
        return info

    def scene_times(self, path: Path, threshold: float = SCENE_THRESHOLD) -> list[float]:
        """Timestamps of scene changes; an empty list when detection fails or times out (the grid still applies)."""
        flt = f"scale=320:-2,select='gt(scene,{threshold})',showinfo"
        try:
            proc = self._run(
                [self.ffmpeg, "-hide_banner", "-nostdin", "-i", str(path), "-an", "-sn", "-vf", flt, "-f", "null", "-"],
                SCENE_TIMEOUT_S,
            )
        except (OSError, subprocess.SubprocessError):
            return []
        return [float(x) for x in _PTS_RE.findall(proc.stderr.decode("utf-8", "replace"))]

    def extract_frame(self, path: Path, ts: float, dest: Path) -> bool:
        dest.parent.mkdir(parents=True, exist_ok=True)
        scale = f"scale='min({FRAME_LONG_SIDE},iw)':-2"
        try:
            self._run(
                [self.ffmpeg, "-hide_banner", "-nostdin", "-y", "-ss", f"{ts:.3f}", "-i", str(path),
                 "-frames:v", "1", "-vf", scale, "-q:v", "3", str(dest)],
                FRAME_TIMEOUT_S,
            )
        except (OSError, subprocess.SubprocessError):
            return False
        return dest.is_file() and dest.stat().st_size > 0

    def extract(
        self,
        path: Path,
        out_dir: Path,
        max_frames: int = DEFAULT_MAX_FRAMES,
        interval_s: float = DEFAULT_INTERVAL_S,
    ) -> Extraction:
        info = self.probe(path)
        scenes = self.scene_times(path) if info.duration else []
        times = plan_times(info.duration, scenes, interval_s, max_frames)
        frames: list[ExtractedFrame] = []
        for i, ts in enumerate(times):
            dest = out_dir / f"{i:03d}_{int(round(ts * 1000))}.jpg"
            if self.extract_frame(path, ts, dest):
                frames.append(ExtractedFrame(ts=ts, path=dest))
        return Extraction(info=info, frames=frames)


def _parse_created(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.year < 1990:  # 1970/1904 epoch placeholders written by some muxers
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.isoformat()
