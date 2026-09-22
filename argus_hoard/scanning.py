"""Filesystem walking and change detection for the indexing pipeline."""
from __future__ import annotations

import fnmatch
import os
from pathlib import Path

from .config import MIN_FILE_SIZE_BYTES, SUPPORTED_EXTENSIONS

HIDDEN_PREFIXES = (".",)
SYSTEM_DIR_NAMES = {"$RECYCLE.BIN", "System Volume Information", "__pycache__", "node_modules"}


def _is_excluded(name: str, excluded_globs: list[str]) -> bool:
    return any(fnmatch.fnmatch(name, pattern) for pattern in excluded_globs)


def walk_images(root: Path, excluded_globs: list[str] | None = None):
    """Yield image file paths under root, skipping hidden/system folders and
    anything matching excluded_globs (matched against the relative path)."""
    excluded_globs = excluded_globs or []
    root = Path(root)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d for d in dirnames
            if not d.startswith(HIDDEN_PREFIXES) and d not in SYSTEM_DIR_NAMES
        ]
        for filename in filenames:
            if filename.startswith(HIDDEN_PREFIXES):
                continue
            ext = Path(filename).suffix.lower()
            if ext not in SUPPORTED_EXTENSIONS:
                continue
            full = Path(dirpath) / filename
            rel = full.relative_to(root).as_posix()
            if _is_excluded(rel, excluded_globs) or _is_excluded(filename, excluded_globs):
                continue
            try:
                if full.stat().st_size < MIN_FILE_SIZE_BYTES:
                    continue
            except OSError:
                continue
            yield full


def stat_signature(path: Path) -> tuple[int, int]:
    st = path.stat()
    return st.st_size, st.st_mtime_ns
