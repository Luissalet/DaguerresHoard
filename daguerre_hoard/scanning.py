"""Filesystem walking and change detection for the indexing pipeline."""
from __future__ import annotations

import fnmatch
import os
import stat as stat_mod
import sys
from pathlib import Path
from typing import Iterable, Iterator

from .config import MIN_FILE_SIZE_BYTES
from .formats import indexable_extensions

HIDDEN_PREFIXES = (".",)
SYSTEM_DIR_NAMES = {"$RECYCLE.BIN", "System Volume Information", "__pycache__", "node_modules"}
_WIN_HIDDEN_OR_SYSTEM = getattr(stat_mod, "FILE_ATTRIBUTE_HIDDEN", 2) | getattr(stat_mod, "FILE_ATTRIBUTE_SYSTEM", 4)


def _is_excluded(name: str, excluded_globs: list[str]) -> bool:
    return any(fnmatch.fnmatch(name, pattern) for pattern in excluded_globs)


def _norm(path: str | os.PathLike) -> str:
    return os.path.normcase(os.path.abspath(path))


def _hidden_on_windows(entry: os.DirEntry) -> bool:
    if sys.platform != "win32":
        return False
    try:
        return bool(entry.stat(follow_symlinks=False).st_file_attributes & _WIN_HIDDEN_OR_SYSTEM)
    except (OSError, AttributeError):
        return False


def walk_images(
    root: Path,
    excluded_globs: list[str] | None = None,
    skip_dirs: Iterable[Path] = (),
) -> Iterator[Path]:
    """Yield image file paths under root, in a stable order.

    Skips hidden folders (dot-names, and the Hidden/System attribute on
    Windows), known system folders, symlinked folders and junctions (no
    loops), unreadable folders, files under 8 KB, anything matching
    `excluded_globs` (matched against the path relative to the root and
    against the bare name), and every folder in `skip_dirs` -- Daguerre's own
    data folders, so a root that contains the data dir never indexes its
    own thumbnails."""
    excluded_globs = excluded_globs or []
    extensions = indexable_extensions()
    root = Path(root)
    skip = {_norm(p) for p in skip_dirs}
    stack = [str(root)]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as it:
                entries = sorted(it, key=lambda e: e.name)
        except OSError:
            continue
        subdirs = []
        for entry in entries:
            name = entry.name
            if name.startswith(HIDDEN_PREFIXES):
                continue
            try:
                if entry.is_dir(follow_symlinks=False):
                    if name in SYSTEM_DIR_NAMES or entry.is_symlink():
                        continue
                    if getattr(entry, "is_junction", lambda: False)():
                        continue
                    if _hidden_on_windows(entry) or _norm(entry.path) in skip:
                        continue
                    rel_dir = Path(entry.path).relative_to(root).as_posix()
                    if _is_excluded(rel_dir, excluded_globs) or _is_excluded(name, excluded_globs):
                        continue
                    subdirs.append(entry.path)
                    continue
                if not entry.is_file(follow_symlinks=True):
                    continue
            except OSError:
                continue
            if Path(name).suffix.lower() not in extensions:
                continue
            full = Path(entry.path)
            rel = full.relative_to(root).as_posix()
            if _is_excluded(rel, excluded_globs) or _is_excluded(name, excluded_globs):
                continue
            try:
                if entry.stat().st_size < MIN_FILE_SIZE_BYTES:
                    continue
            except OSError:
                continue
            yield full
        # reversed so the stack pops sub-folders in alphabetical order
        stack.extend(reversed(subdirs))


def stat_signature(path: Path) -> tuple[int, int]:
    st = path.stat()
    return st.st_size, st.st_mtime_ns
