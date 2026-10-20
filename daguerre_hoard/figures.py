"""Complete portable diagram captures; no native engine or network dependency."""
import base64
import hashlib
import io
import json
import re
from urllib.parse import urlsplit

from PIL import Image


def encoded(figure):
    return json.dumps(figure, sort_keys=True, ensure_ascii=False, allow_nan=False).encode('utf-8')


def validate(value):
    try:
        value = json.loads(encoded(value))
    except (TypeError, ValueError) as error:
        raise ValueError('Choose a complete JSON .vfigure capture.') from error
    if not isinstance(value, dict) or value.get('format') != 'vitruvius.figure/1':
        raise ValueError('Expected a vitruvius.figure/1 capture.')
    if not isinstance(value.get('document_id'), str) or not re.fullmatch(r'[0-9a-f]{12}', value['document_id']):
        raise ValueError('The figure needs its 12-character source document ID.')
    if type(value.get('revision')) is not int or value['revision'] < 1:
        raise ValueError('The figure needs a positive integer revision.')
    content = value.get('content')
    diagram = content.get('diagram') if isinstance(content, dict) else None
    if not isinstance(diagram, dict) or not isinstance(diagram.get('nodes'), list):
        raise ValueError('Retain the complete native diagram source.')
    page, state = value.get('page_id'), value.get('state_id')
    if page is not None:
        view = content.get('view')
        pages = view.get('pages') if isinstance(view, dict) else None
        if not isinstance(page, str) or not isinstance(pages, list) or not any(isinstance(p, dict) and p.get('id') == page for p in pages):
            raise ValueError('The captured page must exist in the retained source.')
    if state is not None:
        mechanism = content.get('mechanism')
        states = mechanism.get('states') if isinstance(mechanism, dict) else None
        if page is not None or not isinstance(state, str) or not 1 <= len(state) <= 60 or diagram.get('type') != 'isometric' or not isinstance(states, list) or not any(
            isinstance(item, dict) and item.get('id') == state for item in states
        ):
            raise ValueError('The captured state must exist in the retained isometric source, without a page selection.')
    origin = value.get('origin', {})
    if not isinstance(origin, dict):
        raise ValueError('Figure origins must be HTTP(S) links.')
    for link in origin.values():
        if not isinstance(link, str):
            raise ValueError('Figure origins must be HTTP(S) links.')
        address = urlsplit(link)
        if address.scheme not in ('http', 'https') or not address.netloc or address.username or address.password:
            raise ValueError('Figure origins must be HTTP(S) links without credentials.')
    preview = value.get('preview')
    if not isinstance(preview, dict) or preview.get('mime') != 'image/png' or not isinstance(preview.get('data'), str):
        raise ValueError('The figure needs its base64 PNG preview.')
    try:
        png = base64.b64decode(preview['data'], validate=True)
        with Image.open(io.BytesIO(png)) as probe:
            if probe.format != 'PNG':
                raise ValueError('The figure preview must be PNG.')
            size = probe.size
            probe.verify()
        with Image.open(io.BytesIO(png)) as decoded:
            decoded.load()
    except (ValueError, OSError, SyntaxError, Image.DecompressionBombError) as error:
        raise ValueError(f'Invalid figure PNG: {error}') from error
    return value, png, size


def identity(figure):
    return hashlib.sha256(encoded(figure)).hexdigest()
