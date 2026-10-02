"""Optional image-format plugins. Imported once by the core modules so every Pillow `Image.open` in the process can
decode HEIC/HEIF when the optional `pillow-heif` package is installed (registration is the shared
``hoard_link.docs.imaging.register_heif``)."""
from __future__ import annotations

from .config import SUPPORTED_EXTENSIONS
from .hoard_link.docs.imaging import register_heif

HEIF_EXTENSIONS = {".heic", ".heif"}

HEIF_AVAILABLE = register_heif()


def indexable_extensions() -> set[str]:
    """Extensions the walker should pick up in this environment."""
    if HEIF_AVAILABLE:
        return set(SUPPORTED_EXTENSIONS)
    return set(SUPPORTED_EXTENSIONS) - HEIF_EXTENSIONS
