from PIL import Image

from daguerre_hoard.contact_sheet import ContactSheetItem, render_contact_sheet, MAX_BYTES


def test_contact_sheet_dimensions_and_size_cap(tmp_path):
    thumbs = []
    for i in range(7):
        p = tmp_path / f"t{i}.jpg"
        Image.new("RGB", (200, 200), (i * 30 % 255, 50, 100)).save(p)
        thumbs.append(p)

    items = [ContactSheetItem(thumb_path=t, index=i + 1, caption=f"2020-01-0{i+1}") for i, t in enumerate(thumbs)]
    jpeg = render_contact_sheet(items, cols=5, cell=150)
    assert len(jpeg) <= MAX_BYTES

    import io

    img = Image.open(io.BytesIO(jpeg))
    expected_rows = (7 + 5 - 1) // 5
    assert img.size == (5 * 150, expected_rows * (150 + 34))
