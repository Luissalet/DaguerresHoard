"""Thumbnail generation, on top of the shared imaging module (``hoard_link.docs.imaging``): EXIF orientation honoured,
fast reduced JPEG decode, 512px long side, WebP q80, stored under data/thumbs/<id[:2]>/<id>.webp (written atomically,
so the UI never serves a half-written file)."""
from __future__ import annotations

from pathlib import Path

from .hoard_link.atomic import write_bytes_atomic
from .hoard_link.docs import imaging

THUMB_LONG_SIDE = 512
THUMB_QUALITY = 80


def thumb_path(thumbs_dir: Path, photo_id: str) -> Path:
    return thumbs_dir / photo_id[:2] / f"{photo_id}.webp"


def make_thumbnail(src: Path, dest: Path) -> None:
    """Write a WebP thumbnail for `src` at `dest` (parent folders are created). Raises ValueError when `src` is not a
    readable image."""
    data = imaging.thumbnail(src, size=THUMB_LONG_SIDE, fmt="webp", quality=THUMB_QUALITY)
    write_bytes_atomic(dest, data, fsync=False)
