"""EXIF and file metadata extraction with Pillow."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import ExifTags, Image

_TAG_BY_NAME = {v: k for k, v in ExifTags.TAGS.items()}
_GPS_TAG_BY_NAME = {v: k for k, v in ExifTags.GPSTAGS.items()}


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


def _ratio_to_float(value: Any) -> float | None:
    try:
        if hasattr(value, "numerator"):
            return float(value.numerator) / float(value.denominator or 1)
        return float(value)
    except (TypeError, ZeroDivisionError, ValueError):
        return None


def _dms_to_decimal(dms: Any, ref: str | None) -> float | None:
    try:
        degrees, minutes, seconds = (_ratio_to_float(v) for v in dms)
        if degrees is None or minutes is None or seconds is None:
            return None
        value = degrees + minutes / 60.0 + seconds / 3600.0
        if ref in ("S", "W"):
            value = -value
        return round(value, 6)
    except (TypeError, ValueError):
        return None


def _parse_exif_datetime(raw: str | None, offset: str | None) -> str | None:
    if not raw:
        return None
    try:
        parsed = dt.datetime.strptime(raw, "%Y:%m:%d %H:%M:%S")
    except ValueError:
        return None
    iso = parsed.isoformat()
    if offset:
        try:
            sign = 1 if offset[0] == "+" else -1
            hh, mm = offset[1:].split(":")
            delta = dt.timedelta(hours=int(hh), minutes=int(mm)) * sign
            tz = dt.timezone(delta)
            iso = parsed.replace(tzinfo=tz).isoformat()
        except (ValueError, IndexError):
            pass
    return iso


def extract_metadata(path: Path) -> PhotoMetadata:
    with Image.open(path) as img:
        width, height = img.size
        exif = {}
        gps: dict[str, Any] = {}
        try:
            raw_exif = img.getexif()
            for tag_id, value in raw_exif.items():
                name = ExifTags.TAGS.get(tag_id, tag_id)
                exif[name] = value
            gps_ifd = raw_exif.get_ifd(ExifTags.IFD.GPSInfo) if raw_exif else {}
            for tag_id, value in (gps_ifd or {}).items():
                name = ExifTags.GPSTAGS.get(tag_id, tag_id)
                gps[name] = value
        except Exception:
            pass

        orientation = int(exif.get("Orientation") or 1)
        taken_raw = exif.get("DateTimeOriginal") or exif.get("DateTime")
        offset = exif.get("OffsetTimeOriginal") or exif.get("OffsetTime")
        taken_at = _parse_exif_datetime(
            taken_raw if isinstance(taken_raw, str) else None,
            offset if isinstance(offset, str) else None,
        )
        date_source = "exif" if taken_at else "file_mtime"
        if not taken_at:
            mtime = path.stat().st_mtime
            taken_at = dt.datetime.fromtimestamp(mtime, tz=dt.timezone.utc).isoformat()

        lat = lon = None
        if gps.get("GPSLatitude") and gps.get("GPSLongitude"):
            lat = _dms_to_decimal(gps["GPSLatitude"], gps.get("GPSLatitudeRef"))
            lon = _dms_to_decimal(gps["GPSLongitude"], gps.get("GPSLongitudeRef"))

        return PhotoMetadata(
            width=width,
            height=height,
            taken_at=taken_at,
            date_source=date_source,
            make=str(exif["Make"]).strip() if exif.get("Make") else None,
            model=str(exif["Model"]).strip() if exif.get("Model") else None,
            lens=str(exif["LensModel"]).strip() if exif.get("LensModel") else None,
            f_number=_ratio_to_float(exif.get("FNumber")),
            exposure_time=(
                str(exif.get("ExposureTime")) if exif.get("ExposureTime") is not None else None
            ),
            iso=(
                int(exif["ISOSpeedRatings"])
                if exif.get("ISOSpeedRatings") is not None
                else (int(exif["PhotographicSensitivity"]) if exif.get("PhotographicSensitivity") is not None else None)
            ),
            focal_length=_ratio_to_float(exif.get("FocalLength")),
            orientation=orientation,
            gps_lat=lat,
            gps_lon=lon,
        )
