"""The image helpers now come from hoard_link.docs.imaging: the stored perceptual hashes must stay valid, and the
thin wrappers must keep the behaviour the library relies on."""
from __future__ import annotations

from PIL import Image, ImageDraw

from daguerre_hoard.hashing import content_hash
from daguerre_hoard.metadata import extract_metadata
from daguerre_hoard.phash import compute_phash, hamming
from daguerre_hoard.thumbnails import make_thumbnail
from tests.conftest import make_image


def _scene() -> Image.Image:
    im = Image.new("RGB", (640, 480), (10, 20, 30))
    d = ImageDraw.Draw(im)
    d.ellipse((100, 80, 400, 380), fill=(220, 40, 40))
    d.rectangle((300, 200, 600, 440), fill=(30, 200, 90))
    return im


def _ramp() -> Image.Image:
    im = Image.new("L", (300, 900))
    px = im.load()
    for y in range(900):
        for x in range(300):
            px[x, y] = (x * 255 // 299 + (y // 30) * 17) % 256
    return im


def _triangle() -> Image.Image:
    im = Image.new("RGBA", (500, 500), (0, 0, 0, 0))
    ImageDraw.Draw(im).polygon([(50, 450), (250, 30), (450, 450)], fill=(255, 255, 0, 255))
    return im


# Values produced by imagehash.phash 4.3.1 for these images (the library stored these in every user's database).
GOLDEN = {
    "scene": (_scene, 0x956E7A9570994A99),
    "ramp": (_ramp, 0xE085E315BDE0BAA5),
    "triangle": (_triangle, 0x997961867E857E81),
}


def test_phash_is_bit_identical_to_the_one_already_stored(tmp_path):
    for name, (make, expected) in GOLDEN.items():
        path = tmp_path / f"{name}.png"
        make().save(path)
        assert compute_phash(path) == expected, name
        with Image.open(path) as opened:
            assert compute_phash(opened) == expected, name       # an already-opened image is hashed as it is


def test_phash_of_a_path_is_orientation_corrected(tmp_path):
    upright = make_image(tmp_path / "a.jpg", size=(400, 200), orientation=1)
    rotated = make_image(tmp_path / "b.jpg", size=(400, 200), orientation=6)
    # same pixels, but one is tagged as needing a quarter turn: they must hash differently once oriented
    assert hamming(compute_phash(upright), compute_phash(rotated)) > 0
    with Image.open(rotated) as raw:   # ... and the same file hashed without the rotation is what the old path never did
        assert compute_phash(raw) != compute_phash(rotated)


def test_content_hash_is_blake2b_256_of_the_bytes(tmp_path):
    import hashlib

    p = tmp_path / "x.bin"
    p.write_bytes(b"hello" * 100_000)
    assert content_hash(p) == hashlib.blake2b(p.read_bytes(), digest_size=32).hexdigest()


def test_thumbnail_keeps_transparency_and_leaves_no_temp_files(tmp_path):
    src = tmp_path / "logo.png"
    _triangle().save(src)
    dest = tmp_path / "thumbs" / "ab" / "abcdef.webp"
    make_thumbnail(src, dest)
    with Image.open(dest) as out:
        assert out.size == (500, 500) or max(out.size) <= 512
        assert out.mode in ("RGBA", "LA")           # the old converter turned transparency into black
    assert [p.name for p in dest.parent.iterdir()] == ["abcdef.webp"]


def test_thumbnail_of_a_broken_file_raises_value_error(tmp_path):
    bad = tmp_path / "bad.jpg"
    bad.write_bytes(b"not an image at all")
    try:
        make_thumbnail(bad, tmp_path / "t.webp")
    except ValueError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected ValueError")
    assert not (tmp_path / "t.webp").exists()


def test_metadata_wrapper_keeps_the_record_the_library_stores(tmp_path):
    import datetime as dt

    p = make_image(tmp_path / "x.jpg", taken_at=dt.datetime(2021, 8, 3, 9, 15, 0), gps=(40.4168, -3.7038), orientation=6)
    meta = extract_metadata(p)
    assert (meta.width, meta.height) == (320, 240)           # stored size, before orientation
    assert meta.orientation == 6
    assert meta.date_source == "exif" and meta.taken_at.startswith("2021-08-03T09:15")
    assert abs(meta.gps_lat - 40.4168) < 0.01 and abs(meta.gps_lon + 3.7038) < 0.01
