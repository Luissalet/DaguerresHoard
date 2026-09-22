"""Synthetic demo photo library: ~80 generated images with EXIF dates and
GPS spread over three years and three cities, plus exact and near
duplicates, so the grid, duplicates, timeline and places screens are
populated without any personal data."""
from __future__ import annotations

import datetime as dt
import random
from pathlib import Path

from PIL import ExifTags, Image, ImageDraw
from PIL.TiffImagePlugin import IFDRational

_TAG_ID = {v: k for k, v in ExifTags.TAGS.items()}
_GPS_TAG_ID = {v: k for k, v in ExifTags.GPSTAGS.items()}

CITIES = {
    "Madrid": (40.4168, -3.7038),
    "Lisbon": (38.7223, -9.1393),
    "Paris": (48.8566, 2.3522),
}

SCENES = ["sunset", "sea", "forest", "whiteboard"]


def _dms(value: float) -> tuple:
    value = abs(value)
    degrees = int(value)
    minutes_float = (value - degrees) * 60
    minutes = int(minutes_float)
    seconds = round((minutes_float - minutes) * 60, 4)
    return (IFDRational(degrees, 1), IFDRational(minutes, 1), IFDRational(int(seconds * 100), 100))


def _exif_bytes(taken_at: dt.datetime, gps: tuple[float, float] | None) -> bytes:
    exif = Image.Exif()
    exif[_TAG_ID["DateTimeOriginal"]] = taken_at.strftime("%Y:%m:%d %H:%M:%S")
    exif[_TAG_ID["DateTime"]] = taken_at.strftime("%Y:%m:%d %H:%M:%S")
    exif[_TAG_ID["Make"]] = "Argus Demo Camera"
    exif[_TAG_ID["Model"]] = "ArgusCam Mk1"
    if gps:
        lat, lon = gps
        exif[_TAG_ID["GPSInfo"]] = {
            _GPS_TAG_ID["GPSLatitudeRef"]: "N" if lat >= 0 else "S",
            _GPS_TAG_ID["GPSLatitude"]: _dms(lat),
            _GPS_TAG_ID["GPSLongitudeRef"]: "E" if lon >= 0 else "W",
            _GPS_TAG_ID["GPSLongitude"]: _dms(lon),
        }
    return exif.tobytes()


def _draw_scene(scene: str, rng: random.Random) -> Image.Image:
    size = (640, 480)
    img = Image.new("RGB", size, (0, 0, 0))
    draw = ImageDraw.Draw(img)
    if scene == "sunset":
        top = (255, rng.randint(120, 180), rng.randint(40, 90))
        bottom = (rng.randint(200, 255), rng.randint(60, 120), rng.randint(10, 40))
        for y in range(size[1]):
            t = y / size[1]
            color = tuple(int(top[i] * (1 - t) + bottom[i] * t) for i in range(3))
            draw.line([(0, y), (size[0], y)], fill=color)
        draw.ellipse([220, 180, 420, 380], fill=(255, 220, 140))
    elif scene == "sea":
        for y in range(size[1]):
            t = y / size[1]
            color = (int(20 + 20 * t), int(80 + 60 * t), int(160 + 60 * t))
            draw.line([(0, y), (size[0], y)], fill=color)
        draw.rectangle([0, 320, size[0], size[1]], fill=(230, 220, 180))
    elif scene == "forest":
        draw.rectangle([0, 0, size[0], size[1]], fill=(30, 70, 40))
        for _ in range(30):
            x = rng.randint(0, size[0])
            y = rng.randint(100, size[1])
            h = rng.randint(60, 160)
            draw.polygon([(x, y), (x - 30, y + h), (x + 30, y + h)], fill=(20, 90 + rng.randint(-10, 20), 30))
    else:  # whiteboard
        draw.rectangle([0, 0, size[0], size[1]], fill=(250, 250, 245))
        for i in range(6):
            y = 60 + i * 60
            draw.line([(40, y), (600, y)], fill=(60, 60, 60), width=3)
        draw.text((50, 20), "ARGUS DEMO NOTES", fill=(30, 30, 30))
    return img


def generate_demo_photos(dest_dir: Path, count: int = 80, seed: int = 7) -> list[Path]:
    """Idempotent: does nothing if dest_dir already has images."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    existing = list(dest_dir.rglob("*.jpg"))
    if len(existing) >= count:
        return existing

    rng = random.Random(seed)
    start = dt.datetime(2023, 1, 1)
    created: list[Path] = []
    city_names = list(CITIES)

    for i in range(count):
        scene = SCENES[i % len(SCENES)]
        taken_at = start + dt.timedelta(days=rng.randint(0, 900), hours=rng.randint(0, 23))
        gps = CITIES[city_names[i % len(city_names)]] if i % 3 != 2 else None
        img = _draw_scene(scene, rng)
        folder = dest_dir / f"{taken_at.year}" / f"{taken_at.month:02d}"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{scene}_{i:03d}.jpg"
        img.save(path, format="JPEG", quality=90, exif=_exif_bytes(taken_at, gps))
        created.append(path)

    # A handful of exact duplicates (byte-identical copies).
    for i in range(3):
        src = created[i * 7]
        dup = src.with_name(src.stem + "_copy" + src.suffix)
        dup.write_bytes(src.read_bytes())
        created.append(dup)

    # A handful of near-duplicates (re-encoded / resized).
    for i in range(3):
        src = created[i * 11 + 1]
        with Image.open(src) as im:
            resized = im.resize((im.width // 2, im.height // 2))
            near = src.with_name(src.stem + "_resized" + src.suffix)
            resized.save(near, format="JPEG", quality=75)
            created.append(near)

    return created
