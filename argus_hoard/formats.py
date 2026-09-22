"""Optional image-format plugins. Imported once by the core modules so every
Pillow `Image.open` in the process can decode HEIC/HEIF when the optional
`pillow-heif` package is installed."""
from __future__ import annotations

from .config import SUPPORTED_EXTENSIONS

HEIF_EXTENSIONS = {".heic", ".heif"}

try:  # pragma: no cover - depends on the optional wheel
    import pillow_heif

    pillow_heif.register_heif_opener()
    HEIF_AVAILABLE = True
except Exception:  # noqa: BLE001 - missing or broken wheel: report, do not crash
    HEIF_AVAILABLE = False


def indexable_extensions() -> set[str]:
    """Extensions the walker should pick up in this environment."""
    if HEIF_AVAILABLE:
        return set(SUPPORTED_EXTENSIONS)
    return set(SUPPORTED_EXTENSIONS) - HEIF_EXTENSIONS
