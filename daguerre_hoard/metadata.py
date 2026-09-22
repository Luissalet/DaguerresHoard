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
    raw = raw.strip().rstrip("\x00")
    try:
        parsed = dt.datetime.strptime(raw[:19], "%Y:%m:%d %H:%M:%S")
    except ValueError:
        return None  # includes the "0000:00:00 00:00:00" some cameras write
    if parsed.year < 1850:
        return None
    iso = parsed.isoformat()
    if offset:
        try:
            offset = offset.strip().rstrip("\x00")
            sign = 1 if offset[0] == "+" else -1
            hh, mm = offset[1:].split(":")
            delta = dt.timedelta(hours=int(hh), minutes=int(mm)) * sign
            tz = dt.timezone(delta)
            iso = parsed.replace(tzinfo=tz).isoformat()
        except (ValueError, IndexError):
            pass
    return iso


def _first(value: Any) -> Any:
    """Some tags (ISO on many cameras) are stored as a tuple of values."""
    if isinstance(value, (tuple, list)):
        return value[0] if value else None
    return value


def _to_int(value: Any) -> int | None:
    value = _first(value)
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _clean_str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    text = str(value).replace("\x00", "").strip()
    return text[:120] or None


def _format_exposure(value: Any) -> str | None:
    seconds = _ratio_to_float(_first(value))
    if seconds is None or seconds <= 0:
        return None
    if seconds < 1:
        return f"1/{round(1 / seconds)}"
    return f"{seconds:g}s" if seconds != int(seconds) else f"{int(seconds)}s"


def extract_metadata(path: Path) -> PhotoMetadata:
    with Image.open(path) as img:
        width, height = img.size
        exif: dict[Any, Any] = {}
        gps: dict[str, Any] = {}
        try:
            raw_exif = img.getexif()
            # IFD0 holds Make/Model/Orientation/DateTime; cameras put
            # DateTimeOriginal, exposure and lens data in the Exif sub-IFD.
            for tag_id, value in raw_exif.items():
                exif[ExifTags.TAGS.get(tag_id, tag_id)] = value
            try:
                for tag_id, value in raw_exif.get_ifd(ExifTags.IFD.Exif).items():
                    exif[ExifTags.TAGS.get(tag_id, tag_id)] = value
            except Exception:  # noqa: BLE001 - a broken sub-IFD must not lose IFD0
                pass
            try:
                for tag_id, value in (raw_exif.get_ifd(ExifTags.IFD.GPSInfo) or {}).items():
                    gps[ExifTags.GPSTAGS.get(tag_id, tag_id)] = value
            except Exception:  # noqa: BLE001
                pass
        except Exception:  # noqa: BLE001 - unreadable EXIF is common, not fatal
            pass

        orientation = _to_int(exif.get("Orientation")) or 1
        if orientation not in range(1, 9):
            orientation = 1
        taken_at = None
        for date_tag, offset_tag in (
            ("DateTimeOriginal", "OffsetTimeOriginal"),
            ("DateTimeDigitized", "OffsetTimeDigitized"),
            ("DateTime", "OffsetTime"),
        ):
            raw = exif.get(date_tag)
            offset = exif.get(offset_tag) or exif.get("OffsetTime")
            taken_at = _parse_exif_datetime(
                raw if isinstance(raw, str) else None,
                offset if isinstance(offset, str) else None,
            )
            if taken_at:
                break
        date_source = "exif" if taken_at else "file_mtime"
        if not taken_at:
            mtime = path.stat().st_mtime
            taken_at = dt.datetime.fromtimestamp(mtime, tz=dt.timezone.utc).isoformat()

        lat = lon = None
        if gps.get("GPSLatitude") and gps.get("GPSLongitude"):
            lat = _dms_to_decimal(gps["GPSLatitude"], _clean_str(gps.get("GPSLatitudeRef")))
            lon = _dms_to_decimal(gps["GPSLongitude"], _clean_str(gps.get("GPSLongitudeRef")))
            if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180) or (lat == 0 and lon == 0):
                lat = lon = None  # 0,0 is the "no fix" value many phones write

        iso = _to_int(exif.get("ISOSpeedRatings"))
        if iso is None:
            iso = _to_int(exif.get("PhotographicSensitivity"))

        return PhotoMetadata(
            width=width,
            height=height,
            taken_at=taken_at,
            date_source=date_source,
            make=_clean_str(exif.get("Make")),
            model=_clean_str(exif.get("Model")),
            lens=_clean_str(exif.get("LensModel")),
            f_number=_ratio_to_float(_first(exif.get("FNumber"))),
            exposure_time=_format_exposure(exif.get("ExposureTime")),
            iso=iso,
            focal_length=_ratio_to_float(_first(exif.get("FocalLength"))),
            orientation=orientation,
            gps_lat=lat,
            gps_lon=lon,
        )
