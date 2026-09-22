from PIL import Image

from daguerre_hoard.thumbnails import make_thumbnail
from tests.conftest import make_image


def test_thumbnail_honours_orientation(tmp_path):
    # A wide image tagged as needing a 90-degree rotation (orientation=6):
    # after exif_transpose the on-disk thumbnail should be tall, not wide.
    src = make_image(tmp_path / "src.jpg", size=(400, 200), orientation=6)
    dest = tmp_path / "thumb.webp"
    make_thumbnail(src, dest)
    with Image.open(dest) as out:
        assert out.height > out.width


def test_thumbnail_long_side_capped(tmp_path):
    src = make_image(tmp_path / "big.jpg", size=(2000, 1000))
    dest = tmp_path / "thumb.webp"
    make_thumbnail(src, dest)
    with Image.open(dest) as out:
        assert max(out.size) <= 512
