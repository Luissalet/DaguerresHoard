"""EXIF as real cameras write it: capture data lives in the Exif sub-IFD,
some tags are tuples, and some dates are zeroed placeholders."""
from __future__ import annotations

import datetime as dt

import numpy as np
import pytest
from PIL import ExifTags, Image
from PIL.TiffImagePlugin import IFDRational

from daguerre_hoard.metadata import extract_metadata


def test_exif_sub_ifd_tags_are_read(tmp_path):
    """Cameras store DateTimeOriginal, FNumber, ISO... in the Exif sub-IFD,
    not in IFD0. Reading only IFD0 silently loses them on real photos."""
    img = Image.fromarray(np.random.default_rng(1).integers(0, 255, (240, 320, 3), dtype=np.uint8))
    exif = Image.Exif()
    exif[ExifTags.Base.Make] = "Canon"
    exif[ExifTags.Base.Model] = "EOS R6"
    exif[ExifTags.Base.DateTime] = "2024:05:05 10:00:00"  # IFD0 = last-modified time
    exif[ExifTags.IFD.Exif] = {
        ExifTags.Base.DateTimeOriginal: "2021:07:14 18:30:05",
        ExifTags.Base.OffsetTimeOriginal: "+02:00",
        ExifTags.Base.FNumber: IFDRational(28, 10),
        ExifTags.Base.ExposureTime: IFDRational(1, 250),
        ExifTags.Base.ISOSpeedRatings: 400,
        ExifTags.Base.FocalLength: IFDRational(50, 1),
        ExifTags.Base.LensModel: "RF 50mm F1.8",
    }
    path = tmp_path / "camera.jpg"
    img.save(path, exif=exif.tobytes())

    meta = extract_metadata(path)
    assert meta.taken_at == "2021-07-14T18:30:05+02:00"
    assert meta.date_source == "exif"
    assert meta.f_number == pytest.approx(2.8)
    assert meta.exposure_time == "1/250"
    assert meta.iso == 400
    assert meta.focal_length == pytest.approx(50.0)
    assert meta.lens == "RF 50mm F1.8"
    assert meta.make == "Canon"


def test_iso_stored_as_a_tuple_does_not_crash(tmp_path):
    img = Image.fromarray(np.random.default_rng(2).integers(0, 255, (100, 100, 3), dtype=np.uint8))
    exif = Image.Exif()
    exif[ExifTags.IFD.Exif] = {ExifTags.Base.ISOSpeedRatings: (800, 0)}
    path = tmp_path / "iso.jpg"
    img.save(path, exif=exif.tobytes())
    assert extract_metadata(path).iso == 800


def test_garbage_exif_date_falls_back_to_file_time(tmp_path):
    img = Image.fromarray(np.random.default_rng(3).integers(0, 255, (100, 100, 3), dtype=np.uint8))
    exif = Image.Exif()
    exif[ExifTags.IFD.Exif] = {ExifTags.Base.DateTimeOriginal: "0000:00:00 00:00:00"}
    path = tmp_path / "zero.jpg"
    img.save(path, exif=exif.tobytes())
    meta = extract_metadata(path)
    assert meta.date_source == "file_mtime"
    assert meta.taken_at.startswith(str(dt.date.today().year))
