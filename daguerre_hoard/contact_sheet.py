"""Render a numbered contact-sheet JPEG so a vision model can look at several
candidate photos for the price of one image."""
from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

MAX_BYTES = 200 * 1024


@dataclass
class ContactSheetItem:
    thumb_path: Path
    index: int
    caption: str = ""


# Bold sans fonts that exist on a stock Windows / Linux / macOS install;
# Pillow searches the system font folders for bare file names.
_FONT_CANDIDATES = ("segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf", "Arial Bold.ttf", "LiberationSans-Bold.ttf")
MAX_ITEMS = 20


def _load_font(size: int) -> ImageFont.ImageFont:
    for name in _FONT_CANDIDATES:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=size)  # scalable built-in font (Pillow >= 10.1)
    except TypeError:
        return ImageFont.load_default()


def render_contact_sheet(items: list[ContactSheetItem], cols: int = 5, cell: int = 220) -> bytes:
    """Returns JPEG bytes, at most MAX_ITEMS cells; quality (then size) is
    reduced as needed to stay under MAX_BYTES."""
    if not items:
        raise ValueError("no items for contact sheet")
    items = items[:MAX_ITEMS]
    cols = max(1, min(cols, len(items)))
    rows = (len(items) + cols - 1) // cols
    label_h = 34
    sheet = Image.new("RGB", (cols * cell, rows * (cell + label_h)), (24, 24, 28))
    draw = ImageDraw.Draw(sheet)
    font_num = _load_font(22)
    font_cap = _load_font(13)

    for i, item in enumerate(items):
        col, row = i % cols, i // cols
        x0, y0 = col * cell, row * (cell + label_h)
        try:
            with Image.open(item.thumb_path) as thumb:
                thumb = thumb.convert("RGB")
                thumb.thumbnail((cell - 8, cell - 8))
                px = x0 + (cell - thumb.width) // 2
                py = y0 + (cell - thumb.height) // 2
                sheet.paste(thumb, (px, py))
        except OSError:
            draw.rectangle([x0, y0, x0 + cell, y0 + cell], fill=(60, 60, 64))

        badge_r = 16
        bx, by = x0 + 6, y0 + 6
        draw.ellipse([bx, by, bx + badge_r * 2, by + badge_r * 2], fill=(18, 164, 168))
        draw.text((bx + badge_r, by + badge_r), str(item.index), font=font_num, fill="white", anchor="mm")

        if item.caption:
            draw.text((x0 + 6, y0 + cell + 8), item.caption[:40], font=font_cap, fill=(210, 210, 215))

    return encode_jpeg_under(sheet, MAX_BYTES)


def encode_jpeg_under(img: Image.Image, max_bytes: int, quality: int = 85) -> bytes:
    """JPEG-encode `img`, lowering quality and then resolution until the
    result fits in `max_bytes` (vision-model context is the budget)."""
    img = img.convert("RGB")
    while True:
        for q in range(quality, 29, -10):
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=q, optimize=True)
            data = buf.getvalue()
            if len(data) <= max_bytes:
                return data
        if max(img.size) <= 64:
            return data
        img = img.resize((max(1, int(img.width * 0.8)), max(1, int(img.height * 0.8))), Image.LANCZOS)
