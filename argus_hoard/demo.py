"""Synthetic demo photo library: 80 generated images with EXIF dates and
GPS spread over three years and three cities, plus exact and near
duplicates, so the grid, duplicates, timeline and places screens are
populated without any personal data.

Every image gets a little sensor-like grain: flat synthetic gradients
compress below the 8 KB "not a photo" floor the scanner applies, which
silently dropped whole scenes from the demo before."""
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


CAMERAS = [("Argus Demo Camera", "ArgusCam Mk1", "Demo 35mm F2"), ("Demo Phone Co", "Pocket 12", None)]


def _exif_bytes(taken_at: dt.datetime, gps: tuple[float, float] | None, camera: int = 0) -> bytes:
    """Standard layout: camera identity in IFD0, capture data in the Exif
    sub-IFD, position in the GPS IFD -- the way real cameras write it."""
    make, model, lens = CAMERAS[camera % len(CAMERAS)]
    exif = Image.Exif()
    exif[_TAG_ID["DateTime"]] = taken_at.strftime("%Y:%m:%d %H:%M:%S")
    exif[_TAG_ID["Make"]] = make
    exif[_TAG_ID["Model"]] = model
    sub = {
        _TAG_ID["DateTimeOriginal"]: taken_at.strftime("%Y:%m:%d %H:%M:%S"),
        _TAG_ID["OffsetTimeOriginal"]: "+01:00",
        _TAG_ID["FNumber"]: IFDRational(20 + 8 * camera, 10),
        _TAG_ID["ExposureTime"]: IFDRational(1, 250 if camera == 0 else 120),
        _TAG_ID["ISOSpeedRatings"]: 100 * (1 + camera),
        _TAG_ID["FocalLength"]: IFDRational(35 if camera == 0 else 26, 1),
    }
    if lens:
        sub[_TAG_ID["LensModel"]] = lens
    exif[0x8769] = sub
    if gps:
        lat, lon = gps
        exif[_TAG_ID["GPSInfo"]] = {
            _GPS_TAG_ID["GPSLatitudeRef"]: "N" if lat >= 0 else "S",
            _GPS_TAG_ID["GPSLatitude"]: _dms(lat),
            _GPS_TAG_ID["GPSLongitudeRef"]: "E" if lon >= 0 else "W",
            _GPS_TAG_ID["GPSLongitude"]: _dms(lon),
        }
    return exif.tobytes()


def _grain(img: Image.Image, seed: int) -> Image.Image:
    import numpy as np

    arr = np.asarray(img, dtype=np.int16)
    noise = np.random.default_rng(seed).integers(-9, 10, size=arr.shape)
    return Image.fromarray(np.clip(arr + noise, 0, 255).astype("uint8"), "RGB")


def _draw_scene(scene: str, rng: random.Random, portrait: bool = False) -> Image.Image:
    size = (480, 640) if portrait else (640, 480)
    img = Image.new("RGB", size, (0, 0, 0))
    draw = ImageDraw.Draw(img)
    if scene == "sunset":
        top = (255, rng.randint(120, 180), rng.randint(40, 90))
        bottom = (rng.randint(200, 255), rng.randint(60, 120), rng.randint(10, 40))
        for y in range(size[1]):
            t = y / size[1]
            color = tuple(int(top[i] * (1 - t) + bottom[i] * t) for i in range(3))
            draw.line([(0, y), (size[0], y)], fill=color)
        cx, cy = size[0] // 2, int(size[1] * 0.58)
        draw.ellipse([cx - 100, cy - 100, cx + 100, cy + 100], fill=(255, 220, 140))
    elif scene == "sea":
        for y in range(size[1]):
            t = y / size[1]
            color = (int(20 + 20 * t), int(80 + 60 * t), int(160 + 60 * t))
            draw.line([(0, y), (size[0], y)], fill=color)
        draw.rectangle([0, int(size[1] * 0.67), size[0], size[1]], fill=(230, 220, 180))
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
            draw.line([(40, y), (size[0] - 40, y)], fill=(60, 60, 60), width=3)
        draw.text((50, 20), "ARGUS DEMO NOTES", fill=(30, 30, 30))
        draw.rectangle([size[0] - 180, 90, size[0] - 60, 170], outline=(200, 40, 40), width=4)
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
        gps = CITIES[city_names[(i // 4) % len(city_names)]] if i % 5 != 4 else None
        portrait = i % 9 == 3
        img = _grain(_draw_scene(scene, rng, portrait=portrait), seed + i)
        folder = dest_dir / f"{taken_at.year}" / f"{taken_at.month:02d}"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{scene}_{i:03d}.jpg"
        img.save(path, format="JPEG", quality=90, exif=_exif_bytes(taken_at, gps, camera=i % 3 == 2))
        created.append(path)

    # A handful of exact duplicates (byte-identical copies in another folder).
    backup = dest_dir / "backup"
    backup.mkdir(exist_ok=True)
    for i in range(3):
        src = created[i * 7]
        dup = backup / (src.stem + "_copy" + src.suffix)
        dup.write_bytes(src.read_bytes())
        created.append(dup)

    # A handful of near-duplicates (downscaled and re-encoded "shared" copies).
    shared = dest_dir / "shared"
    shared.mkdir(exist_ok=True)
    for i in range(4):
        src = created[i * 11 + 1]
        with Image.open(src) as im:
            resized = im.resize((im.width * 3 // 4, im.height * 3 // 4), Image.LANCZOS)
            near = shared / (src.stem + "_small" + src.suffix)
            resized.save(near, format="JPEG", quality=72)
            created.append(near)

    return created
