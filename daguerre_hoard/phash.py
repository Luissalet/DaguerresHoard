"""Perceptual hashing and near-duplicate grouping.

Near-duplicate lookup is a multi-index hash over four 16-bit chunks of the
64-bit pHash. Pigeonhole: if two hashes differ in at most `t` bits, at
least one of the four chunks differs in at most `t // 4` bits (for the
default t = 6: at most 1 bit). So probing every chunk with its exact value
*and* every value within `t // 4` flipped bits finds every true neighbour
-- the index is exact, with no brute-force fallback -- and each candidate
is then confirmed by a real Hamming-distance check.
"""
from __future__ import annotations

from collections import defaultdict
from itertools import combinations

import imagehash
from PIL import Image, ImageOps

HASH_BITS = 64
CHUNKS = 4
CHUNK_BITS = HASH_BITS // CHUNKS  # 16
DEFAULT_THRESHOLD = 6


def compute_phash(path_or_image) -> int:
    """Perceptual hash (64-bit int) of an image path or an already-opened,
    orientation-corrected PIL Image."""
    if isinstance(path_or_image, Image.Image):
        img = path_or_image
    else:
        with Image.open(path_or_image) as opened:
            img = ImageOps.exif_transpose(opened).convert("RGB")
            return int(str(imagehash.phash(img)), 16)
    return int(str(imagehash.phash(img)), 16)


def hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def chunks_of(value: int) -> list[int]:
    mask = (1 << CHUNK_BITS) - 1
    return [(value >> (CHUNK_BITS * i)) & mask for i in range(CHUNKS)]


def _within_radius(chunk: int, radius: int):
    """Every CHUNK_BITS-bit value within `radius` flipped bits of `chunk`."""
    yield chunk
    for r in range(1, radius + 1):
        for bits in combinations(range(CHUNK_BITS), r):
            v = chunk
            for b in bits:
                v ^= 1 << b
            yield v


class ChunkIndex:
    """Buckets 64-bit hashes by their four 16-bit chunks so a near-duplicate
    query only compares against plausible candidates instead of every photo.
    Exact for any threshold (see the module docstring)."""

    def __init__(self) -> None:
        self._buckets: list[dict[int, set[str]]] = [defaultdict(set) for _ in range(CHUNKS)]
        self._hashes: dict[str, int] = {}

    def add(self, item_id: str, value: int) -> None:
        self._hashes[item_id] = value
        for i, c in enumerate(chunks_of(value)):
            self._buckets[i][c].add(item_id)

    def find(self, value: int, threshold: int = DEFAULT_THRESHOLD, exclude: str | None = None) -> list[tuple[str, int]]:
        radius = threshold // CHUNKS
        candidates: set[str] = set()
        for i, c in enumerate(chunks_of(value)):
            bucket = self._buckets[i]
            for probe in _within_radius(c, radius):
                hit = bucket.get(probe)
                if hit:
                    candidates |= hit
        results = []
        for cid in candidates:
            if cid == exclude:
                continue
            dist = hamming(value, self._hashes[cid])
            if dist <= threshold:
                results.append((cid, dist))
        return sorted(results, key=lambda t: (t[1], t[0]))

    def __len__(self) -> int:
        return len(self._hashes)


class UnionFind:
    def __init__(self) -> None:
        self._parent: dict[str, str] = {}

    def find(self, x: str) -> str:
        self._parent.setdefault(x, x)
        while self._parent[x] != x:
            self._parent[x] = self._parent[self._parent[x]]
            x = self._parent[x]
        return x

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self._parent[ra] = rb

    def groups(self) -> dict[str, list[str]]:
        out: dict[str, list[str]] = defaultdict(list)
        for x in self._parent:
            out[self.find(x)].append(x)
        return out
