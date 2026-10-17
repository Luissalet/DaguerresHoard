"""Reference exposure/colour matching on owned derivatives of indexed originals.

Independent implementation using robust log-linear RGB statistics. Best suited
to comparable scenes; it does not infer subject, masks or a photographic look.
"""
from __future__ import annotations

import io
import math
import uuid
from pathlib import Path

import numpy as np
from PIL import Image, ImageCms, ImageOps

from .hashing import content_hash
from .hoard_link.atomic import write_bytes_atomic, write_json_atomic
from .scanning import stat_signature


def linear(rgb):
    a = np.asarray(rgb, dtype=np.float32) / 255
    return np.where(a <= .04045, a / 12.92, ((a + .055) / 1.055) ** 2.4)


def encoded(a):
    a = np.clip(a, 0, 1)
    return np.rint(np.clip(np.where(a <= .0031308, a * 12.92, 1.055 * a ** (1 / 2.4) - .055), 0, 1) * 255).astype(np.uint8)


def statistics(image):
    sample = image.copy()
    sample.thumbnail((512, 512))
    a = linear(sample.convert('RGB'))
    y = a @ np.array([.2126, .7152, .0722])
    valid = (y > .005) & (y < .95) & (np.asarray(sample.getchannel('A')) > 127)
    if np.count_nonzero(valid) < 16:
        raise ValueError('Not enough visible midtones to match this photo.')
    pixels = a[valid]
    # Trim luminance extremes; avoid black pixels dominating a logarithm.
    luminance = y[valid]
    lo, hi = np.quantile(luminance, [.1, .9])
    pixels = pixels[(luminance >= lo) & (luminance <= hi)]
    rgb = np.exp(np.mean(np.log(np.maximum(pixels, .0001)), axis=0))
    return {'rgb': rgb.tolist(), 'luminance': float(rgb @ [.2126, .7152, .0722])}


def read(library, photo_id, edge):
    from .library import NotFoundError, ValidationError
    row = library._resolve_photo(photo_id, None)
    if row['video_id']:
        raise ValidationError('Use indexed photo files, not video frames.')
    path = Path(row['path'])
    if not path.is_file():
        raise NotFoundError('The original photo is not reachable.')
    signature = stat_signature(path)
    fingerprint = content_hash(path)
    with Image.open(path) as source:
        source = ImageOps.exif_transpose(source)
        alpha = source.convert('RGBA').getchannel('A') if source.mode != 'LAB' else Image.new('L', source.size, 255)
        profile = source.info.get('icc_profile')
        if profile:
            colour = source if source.mode in ('CMYK', 'LAB') else source.convert('RGB')
            source = ImageCms.profileToProfile(colour, ImageCms.ImageCmsProfile(io.BytesIO(profile)), ImageCms.createProfile('sRGB'), outputMode='RGB')
        image = source.convert('RGBA')
        image.putalpha(alpha)
        image.thumbnail((edge, edge), Image.Resampling.LANCZOS)
    if stat_signature(path) != signature:
        raise ValidationError('The original changed while being read; try again.')
    return image, {'id': row['id'], 'path': str(path), 'content_hash': fingerprint,
                   'indexed_metadata_stale': fingerprint != row['content_hash']}


def create(library, reference_id, ids, strength=1.0, long_edge=1600):
    from .library import ValidationError, NotFoundError
    if not isinstance(ids, list) or not 1 <= len(ids) <= 20:
        raise ValidationError('ids must contain 1-20 indexed photo ids.')
    try:
        strength = float(strength)
        long_edge = int(long_edge)
    except (TypeError, ValueError, OverflowError):
        raise ValidationError('strength must be 0-1 and long_edge 256-4096.') from None
    if not math.isfinite(strength) or not 0 <= strength <= 1 or not 256 <= long_edge <= 4096:
        raise ValidationError('strength must be 0-1 and long_edge 256-4096.')
    try:
        reference, ref = read(library, reference_id, long_edge)
        ref_stats = statistics(reference)
    except (OSError, ValueError, ImageCms.PyCMSError) as exc:
        raise ValidationError('Reference cannot be matched: ' + str(exc)) from exc
    photos, omitted, files = [], [], []
    for n, photo_id in enumerate(ids, 1):
        try:
            image, original = read(library, photo_id, long_edge)
            before = statistics(image)
            stops = np.log2(np.asarray(ref_stats['rgb']) / np.asarray(before['rgb']))
            stops = np.clip(stops, -3, 3) * strength
            gains = 2 ** stops
            rgb = encoded(linear(image.convert('RGB')) * gains)
            matched = Image.fromarray(rgb, 'RGB').convert('RGBA')
            matched.putalpha(image.getchannel('A'))
            after = statistics(matched)
            buf = io.BytesIO()
            matched.save(buf, format='PNG')
            ev = float(np.log2(ref_stats['luminance'] / before['luminance']))
            photos.append({**original, 'n': n, 'filename': f'{n}.png', 'before': before, 'after': after,
                           'parameters': {'channel_gains': gains.tolist(), 'exposure_difference_ev': ev,
                                          'limited': bool(np.any(np.abs(np.log2(np.asarray(ref_stats['rgb']) / np.asarray(before['rgb']))) > 3))},
                           'width': matched.width, 'height': matched.height})
            files.append((f'{n}.png', buf.getvalue()))
        except (OSError, ValueError, ImageCms.PyCMSError, NotFoundError, ValidationError) as exc:
            omitted.append({'n': n, 'id': str(photo_id), 'reason': str(exc)})
    if not photos:
        raise ValidationError('No photos could be matched: ' + '; '.join(x['reason'] for x in omitted))
    ident = uuid.uuid4().hex
    base = f'/api/reference-matches/{ident}'
    for photo in photos:
        photo['output_url'] = base + '/' + photo['filename']
    result = {'id': ident, 'reference': {**ref, 'statistics': ref_stats}, 'photos': photos, 'omitted': omitted,
              'complete': not omitted, 'strength': strength, 'long_edge': long_edge,
              'method': 'trimmed-log-linear-rgb-v1', 'input': 'original', 'stored_edits_applied': False,
              'original_modified': False, 'manifest_url': base + '/manifest.json',
              'note': 'Global exposure and colour matching for comparable scenes. Existing retouch recipes stay separate; no semantic or local-tone matching.'}
    folder = library.settings.data_dir / 'reference-matches' / ident
    folder.mkdir(parents=True, exist_ok=True)
    for filename, payload in files:
        write_bytes_atomic(folder / filename, payload)
    write_json_atomic(folder / 'manifest.json', result)
    return result
