"""EXIF and file metadata extraction, on top of the shared ``hoard_link.docs.imaging.read_exif`` (this module adds
the file-modification-time fallback for photos without a capture date and keeps the ``PhotoMetadata`` record the
library stores)."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path

from .hoard_link.docs import imaging


@dataclass
class PhotoMetadata:
    width: int
    height: int
    taken_at: str | None
    date_source: str
    make: str | None
    model: str | None
    lens: str | None
    f_number: float | None
    exposure_time: str | None
    iso: int | None
    focal_length: float | None
    orientation: int
    gps_lat: float | None
    gps_lon: float | None


def extract_metadata(path: Path) -> PhotoMetadata:
    exif = imaging.read_exif(path)
    taken_at = exif["date"]
    date_source = "exif" if taken_at else "file_mtime"
    if not taken_at:
        mtime = Path(path).stat().st_mtime
        taken_at = dt.datetime.fromtimestamp(mtime, tz=dt.timezone.utc).isoformat()
    return PhotoMetadata(
        width=exif["width"],
        height=exif["height"],
        taken_at=taken_at,
        date_source=date_source,
        make=exif["make"],
        model=exif["model"],
        lens=exif["lens"],
        f_number=exif["f_number"],
        exposure_time=exif["exposure"],
        iso=exif["iso"],
        focal_length=exif["focal_length"],
        orientation=exif["orientation"],
        gps_lat=exif["lat"],
        gps_lon=exif["lon"],
    )
