import json
import time
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from daguerre_hoard.library import ValidationError
from daguerre_hoard.reference_matching import encoded


def series(library, tmp_path):
    folder = tmp_path / 'originals'
    folder.mkdir()
    rng = np.random.default_rng(17)
    original = rng.uniform(.08, .5, (200, 240, 3))
    reference = encoded(original)
    target = encoded(original * [.45, .6, .8])
    paths = [folder / 'reference.png', folder / 'target.png']
    for path, pixels in zip(paths, [reference, target]):
        image = Image.fromarray(pixels, 'RGB').convert('RGBA')
        alpha = np.full((200, 240), 255, dtype=np.uint8)
        alpha[:10] = 0
        image.putalpha(Image.fromarray(alpha))
        image.save(path)
    root = library.add_root(str(folder))
    job = library.start_scan(root['id'])
    until = time.monotonic() + 10
    while library.jobs.get(job)['status'] not in ('done', 'error') and time.monotonic() < until:
        time.sleep(.01)
    assert library.jobs.get(job)['status'] == 'done'
    ids = [library.conn.execute('SELECT id FROM photos WHERE path=?', (str(p.resolve()),)).fetchone()[0] for p in paths]
    return paths, ids, reference, target


def test_known_exposure_and_colour_cast_improve_real_pixels_and_preserve_source(library, tmp_path):
    paths, ids, reference, target = series(library, tmp_path)
    before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in paths}
    library.set_edits(ids[1], {'recipe': {'exposure': .7, 'contrast': 15}, 'rating': 4}, write=False)
    edits = library.get_edits(ids[1])
    out = library.match_photos(ids[0], [ids[1]])
    folder = library.settings.data_dir / 'reference-matches' / out['id']
    with Image.open(folder / '1.png') as image:
        result = np.asarray(image)
    initial_error = np.mean(np.abs(target.astype(float) - reference))
    final_error = np.mean(np.abs(result[10:, :, :3].astype(float) - reference[10:]))
    assert final_error < 2 and final_error < initial_error / 10
    assert np.all(result[:10, :, 3] == 0) and np.all(result[10:, :, 3] == 255)
    assert out['complete'] and out['original_modified'] is False
    assert out['input'] == 'original' and out['stored_edits_applied'] is False
    manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    assert manifest['photos'][0]['parameters']['channel_gains'] == out['photos'][0]['parameters']['channel_gains']
    assert library.get_edits(ids[1]) == edits
    assert all((p.read_bytes(), p.stat().st_mtime_ns) == before[p] for p in paths)


def test_strength_zero_preserves_pixels_and_batch_reports_missing(library, tmp_path):
    paths, ids, _, target = series(library, tmp_path)
    out = library.match_photos(ids[0], ['0' * 32, ids[1]], strength=0)
    assert not out['complete'] and out['omitted'][0]['n'] == 1
    assert out['photos'][0]['filename'] == '2.png'
    with Image.open(library.settings.data_dir / 'reference-matches' / out['id'] / '2.png') as image:
        assert np.array_equal(np.asarray(image)[:, :, :3], target)
    repeat = library.match_photos(ids[0], [ids[1]], strength=0)
    assert repeat['id'] != out['id']


@pytest.mark.parametrize('kwargs', [{'strength': float('nan')}, {'strength': 1.1}, {'long_edge': 0}, {'ids': []}])
def test_invalid_matching_parameters(library, kwargs):
    with pytest.raises(ValidationError):
        library.match_photos('0' * 32, **({'ids': ['0' * 32]} | kwargs))


def test_dark_or_transparent_reference_reports_failure(library, tmp_path):
    paths, ids, _, _ = series(library, tmp_path)
    Image.new('RGBA', (240, 200), (0, 0, 0, 0)).save(paths[0])
    with pytest.raises(ValidationError, match='visible midtones'):
        library.match_photos(ids[0], [ids[1]])


def test_embedded_lab_profile_and_exif_orientation_are_rendered_before_matching(library, tmp_path):
    from PIL import ImageCms
    from daguerre_hoard.reference_matching import read
    paths, ids, _, _ = series(library, tmp_path)
    with Image.open(paths[1]) as image:
        rgb = image.convert('RGB')
    lab_profile = ImageCms.ImageCmsProfile(ImageCms.createProfile('LAB'))
    lab = ImageCms.profileToProfile(rgb, ImageCms.createProfile('sRGB'), lab_profile, outputMode='LAB')
    path = tmp_path / 'lab.tif'
    orientation = Image.Exif()
    orientation[274] = 6
    lab.save(path, icc_profile=lab_profile.tobytes(), exif=orientation)
    library.conn.execute('UPDATE photos SET path=? WHERE id=?', (str(path), ids[1]))
    library.conn.commit()
    result, _ = read(library, ids[1], 1600)
    assert result.size == (200, 240)  # original 240x200, EXIF rotation applied
    expected = np.rot90(np.asarray(rgb), -1)
    assert np.mean(np.abs(np.asarray(result)[:, :, :3].astype(float) - expected)) < 3
