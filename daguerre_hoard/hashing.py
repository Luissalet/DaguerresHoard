"""Streamed content hashing, used for exact-duplicate detection and to follow a moved/renamed file (same hash, new
path). The implementation is the shared one (BLAKE2b-256 in 1 MB pieces); the name stays for the callers of this app."""
from __future__ import annotations

from .hoard_link.docs.imaging import content_hash

__all__ = ["content_hash"]
