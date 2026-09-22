from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import datetime as dt
from pathlib import Path

import pytest
from PIL import ExifTags, Image
from PIL.TiffImagePlugin import IFDRational

from argus_hoard.config import Settings
from argus_hoard.embeddings import FakeEmbedder
from argus_hoard.library import Library

_TAG_ID = {v: k for k, v in ExifTags.TAGS.items()}
_GPS_TAG_ID = {v: k for k, v in ExifTags.GPSTAGS.items()}


def _dms(value: float) -> tuple:
    value = abs(value)
    degrees = int(value)
    minutes_float = (value - degrees) * 60
    minutes = int(minutes_float)
    seconds = round((minutes_float - minutes) * 60, 4)
    return (
        IFDRational(degrees, 1),
        IFDRational(minutes, 1),
        IFDRational(int(seconds * 100), 100),
    )


def make_image(
    path: Path,
    color=(200, 60, 60),
    size=(320, 240),
    taken_at: dt.datetime | None = None,
    gps: tuple[float, float] | None = None,
    orientation: int = 1,
    fmt: str = "JPEG",
):
    # A flat-color JPEG compresses to well under Argus's 8KB minimum file
    # size, so add deterministic noise around the target color: keeps the
    # dominant hue (what FakeEmbedder keys on) while pushing the file past
    # the size floor like a real photo would be.
    import numpy as np

    import hashlib

    seed = hashlib.blake2b(f"{path.name}{color}".encode(), digest_size=8).digest()
    rng = np.random.default_rng(int.from_bytes(seed, "little"))  # stable across runs
    base = np.array(color, dtype=np.int16)
    noise = rng.integers(-35, 35, size=(size[1], size[0], 3))
    arr = np.clip(base + noise, 0, 255).astype(np.uint8)
    img = Image.fromarray(arr, "RGB")
    path.parent.mkdir(parents=True, exist_ok=True)
    exif = Image.Exif()
    if taken_at:
        stamp = taken_at.strftime("%Y:%m:%d %H:%M:%S")
        exif[_TAG_ID["DateTimeOriginal"]] = stamp
        exif[_TAG_ID["DateTime"]] = stamp
    if orientation != 1:
        exif[_TAG_ID["Orientation"]] = orientation
    if gps:
        lat, lon = gps
        gps_ifd = {
            _GPS_TAG_ID["GPSLatitudeRef"]: "N" if lat >= 0 else "S",
            _GPS_TAG_ID["GPSLatitude"]: _dms(lat),
            _GPS_TAG_ID["GPSLongitudeRef"]: "E" if lon >= 0 else "W",
            _GPS_TAG_ID["GPSLongitude"]: _dms(lon),
        }
        exif[_TAG_ID["GPSInfo"]] = gps_ifd
    if taken_at or gps or orientation != 1:
        img.save(path, format=fmt, exif=exif.tobytes())
    else:
        img.save(path, format=fmt)
    return path


@pytest.fixture()
def tmp_settings(tmp_path):
    return Settings(data_dir=tmp_path / "data")


@pytest.fixture()
def library(tmp_settings):
    lib = Library(tmp_settings, embedder=FakeEmbedder())
    return lib
