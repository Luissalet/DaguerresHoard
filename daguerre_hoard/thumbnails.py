"""Thumbnail generation: EXIF-orientation honoured, fast reduced JPEG decode,
512px long side, WebP q80, stored under data/thumbs/<id[:2]>/<id>.webp."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageOps

THUMB_LONG_SIDE = 512
THUMB_QUALITY = 80


def thumb_path(thumbs_dir: Path, photo_id: str) -> Path:
    return thumbs_dir / photo_id[:2] / f"{photo_id}.webp"


def make_thumbnail(src: Path, dest: Path) -> tuple[int, int]:
    """Write a WebP thumbnail for `src` at `dest`. Returns the *original*
    image's (width, height) as read during decode (post fast-draft downscale
    the reported size may differ slightly from the true file size on JPEGs;
    callers should still prefer metadata.extract_metadata for stored dims)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as img:
        try:
            # Fast reduced decoding for large JPEGs.
            img.draft("RGB", (THUMB_LONG_SIDE, THUMB_LONG_SIDE))
        except Exception:
            pass
        img = ImageOps.exif_transpose(img)
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        w, h = img.size
        scale = THUMB_LONG_SIDE / max(w, h) if max(w, h) > THUMB_LONG_SIDE else 1.0
        if scale < 1.0:
            img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)
        img.save(dest, format="WEBP", quality=THUMB_QUALITY, method=4)
        return w, h
