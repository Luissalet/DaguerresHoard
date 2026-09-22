import datetime as dt

from daguerre_hoard.metadata import extract_metadata
from tests.conftest import make_image


def test_gps_decimal_conversion_signs(tmp_path):
    # Madrid: N, W
    p = make_image(tmp_path / "madrid.jpg", gps=(40.4168, -3.7038))
    meta = extract_metadata(p)
    assert meta.gps_lat is not None and meta.gps_lon is not None
    assert abs(meta.gps_lat - 40.4168) < 0.01
    assert abs(meta.gps_lon - (-3.7038)) < 0.01

    # Southern/Eastern hemisphere signs
    p2 = make_image(tmp_path / "sydney.jpg", gps=(-33.8688, 151.2093))
    meta2 = extract_metadata(p2)
    assert meta2.gps_lat < 0
    assert meta2.gps_lon > 0


def test_taken_at_from_exif_and_fallback(tmp_path):
    when = dt.datetime(2022, 6, 15, 10, 30, 0)
    p = make_image(tmp_path / "dated.jpg", taken_at=when)
    meta = extract_metadata(p)
    assert meta.date_source == "exif"
    assert meta.taken_at.startswith("2022-06-15")

    p2 = make_image(tmp_path / "undated.jpg")
    meta2 = extract_metadata(p2)
    assert meta2.date_source == "file_mtime"
    assert meta2.taken_at is not None


def test_orientation_extracted(tmp_path):
    p = make_image(tmp_path / "rotated.jpg", orientation=6)
    meta = extract_metadata(p)
    assert meta.orientation == 6
