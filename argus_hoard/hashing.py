"""Streamed content hashing, used for exact-duplicate detection and to follow
a moved/renamed file (same hash, new path)."""
from __future__ import annotations

import hashlib
from pathlib import Path

CHUNK_SIZE = 1024 * 1024


def content_hash(path: Path) -> str:
    """BLAKE2b hex digest of the file, read in streamed chunks (no full load)."""
    h = hashlib.blake2b(digest_size=32)
    with open(path, "rb") as f:
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()
