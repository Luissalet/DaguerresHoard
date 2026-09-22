"""Image/text embedding backends and the on-disk vector store.

`Embedder` is the interface the indexing pipeline and search use. Two
implementations exist:

- `FakeEmbedder`: a deterministic colour-histogram embedding. Used by
  default in tests and whenever the real model is not downloaded, so tests
  never hit the network. A "red" text query finds a red image because the
  text embedder maps colour-name keywords onto the same histogram axes.
- `ClipEmbedder`: real CLIP (ViT-B/32) via `fastembed` + ONNX Runtime, no
  PyTorch. Downloads ~350MB from Hugging Face on first use into
  `data/models`; the caller is responsible for surfacing that to the user.

Both embed into the same `EMBED_DIM`-dimensional, L2-normalised space so
cosine similarity == dot product.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, Protocol

import numpy as np
from PIL import Image

from .config import EMBED_DIM

_COLOR_WORDS = {
    "red": (0, 60), "orange": (20, 60), "yellow": (50, 60), "green": (100, 60),
    "cyan": (180, 60), "blue": (220, 60), "purple": (280, 60), "pink": (320, 60),
    "white": (0, 5), "black": (0, 5), "grey": (0, 5), "gray": (0, 5),
}


class Embedder(Protocol):
    name: str
    dim: int

    def embed_images(self, paths: list[Path]) -> np.ndarray: ...

    def embed_text(self, text: str) -> np.ndarray: ...


def _l2_normalize(vecs: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vecs, axis=-1, keepdims=True)
    norms[norms == 0] = 1.0
    return vecs / norms


class FakeEmbedder:
    """Deterministic, offline colour-histogram embedder used for tests and
    as a functional fallback before the real model is downloaded."""

    name = "fake-colorhist-v1"
    dim = EMBED_DIM

    def embed_images(self, paths: list[Path]) -> np.ndarray:
        out = np.zeros((len(paths), self.dim), dtype=np.float32)
        for i, p in enumerate(paths):
            out[i] = self._embed_one(p)
        return _l2_normalize(out)

    def _embed_one(self, path: Path) -> np.ndarray:
        with Image.open(path) as img:
            img = img.convert("RGB").resize((64, 64))
            arr = np.asarray(img, dtype=np.float32) / 255.0
        hsv = _rgb_to_hsv(arr)
        hue = hsv[..., 0].flatten()
        sat = hsv[..., 1].flatten()
        val = hsv[..., 2].flatten()
        hue_hist, _ = np.histogram(hue, bins=self.dim - 32, range=(0.0, 1.0), weights=sat + 0.05)
        val_hist, _ = np.histogram(val, bins=32, range=(0.0, 1.0))
        vec = np.concatenate([hue_hist, val_hist]).astype(np.float32)
        return vec

    def embed_text(self, text: str) -> np.ndarray:
        vec = np.zeros(self.dim, dtype=np.float32)
        words = re.findall(r"[a-zA-Z]+", text.lower())
        hit = False
        for w in words:
            for name, (hue_deg, bin_span) in _COLOR_WORDS.items():
                if w == name or w.rstrip("s") == name:
                    hit = True
                    hue_bins = self.dim - 32
                    center = int((hue_deg / 360.0) * hue_bins)
                    for offset in range(-2, 3):
                        idx = (center + offset) % hue_bins
                        vec[idx] += max(0.0, 1.0 - abs(offset) * 0.3)
        if not hit:
            # Fall back to a stable hash-based pseudo-embedding so unrelated
            # text queries still return a deterministic (if not meaningful)
            # ranking instead of an error.
            rng = np.random.default_rng(abs(hash(" ".join(sorted(words)))) % (2**32))
            vec = rng.random(self.dim).astype(np.float32)
        return _l2_normalize(vec[None, :])[0]


def _rgb_to_hsv(arr: np.ndarray) -> np.ndarray:
    maxc = arr.max(axis=-1)
    minc = arr.min(axis=-1)
    v = maxc
    delta = maxc - minc
    s = np.where(maxc == 0, 0, delta / np.where(maxc == 0, 1, maxc))
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    delta_safe = np.where(delta == 0, 1, delta)
    rc = (maxc - r) / delta_safe
    gc = (maxc - g) / delta_safe
    bc = (maxc - b) / delta_safe
    h = np.zeros_like(maxc)
    h = np.where(maxc == r, bc - gc, h)
    h = np.where(maxc == g, 2.0 + rc - bc, h)
    h = np.where(maxc == b, 4.0 + gc - rc, h)
    h = (h / 6.0) % 1.0
    h = np.where(delta == 0, 0, h)
    return np.stack([h, s, v], axis=-1)


_CLIP_SINGLETON: dict[str, object] = {}


class ClipEmbedder:
    """Real CLIP embeddings via fastembed (ONNX Runtime, no PyTorch)."""

    name = "clip-vit-b32"
    dim = EMBED_DIM

    def __init__(self, cache_dir: Path):
        from fastembed import ImageEmbedding, TextEmbedding  # local import: optional dep

        cache_dir.mkdir(parents=True, exist_ok=True)
        key = str(cache_dir)
        if key not in _CLIP_SINGLETON:
            _CLIP_SINGLETON[key] = (
                ImageEmbedding("Qdrant/clip-ViT-B-32-vision", cache_dir=str(cache_dir)),
                TextEmbedding("Qdrant/clip-ViT-B-32-text", cache_dir=str(cache_dir)),
            )
        self._image_model, self._text_model = _CLIP_SINGLETON[key]

    def embed_images(self, paths: list[Path]) -> np.ndarray:
        vecs = list(self._image_model.embed([str(p) for p in paths]))
        arr = np.array(vecs, dtype=np.float32)
        return _l2_normalize(arr)

    def embed_text(self, text: str) -> np.ndarray:
        vec = next(iter(self._text_model.embed([text])))
        return _l2_normalize(np.asarray(vec, dtype=np.float32)[None, :])[0]

    @staticmethod
    def is_cached(cache_dir: Path) -> bool:
        return cache_dir.exists() and any(cache_dir.rglob("*.onnx"))


class VectorStore:
    """Append-only float32 matrix on disk, memory-mapped. Doubles capacity
    when full (rewrites the file, which is fine at this scale -- brute
    force cosine search is documented as fine up to ~200k images)."""

    def __init__(self, path: Path, dim: int = EMBED_DIM):
        self.path = path
        self.dim = dim
        self._count_path = path.with_suffix(".count")
        self._capacity = 0
        self._count = 0
        self._mm: np.memmap | None = None
        self._load()

    def _load(self) -> None:
        if self._count_path.exists() and self.path.exists():
            self._count = int(self._count_path.read_text().strip() or 0)
            size_bytes = self.path.stat().st_size
            self._capacity = size_bytes // (self.dim * 4)
            if self._capacity > 0:
                self._mm = np.memmap(self.path, dtype=np.float32, mode="r+", shape=(self._capacity, self.dim))
        if self._mm is None:
            self._capacity = 256
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._mm = np.memmap(self.path, dtype=np.float32, mode="w+", shape=(self._capacity, self.dim))
            self._mm.flush()
            self._count_path.write_text("0")

    def _grow(self, min_capacity: int) -> None:
        new_capacity = max(self._capacity * 2, min_capacity, 256)
        new_mm = np.memmap(self.path.with_suffix(".grow"), dtype=np.float32, mode="w+", shape=(new_capacity, self.dim))
        new_mm[: self._count] = self._mm[: self._count]
        new_mm.flush()
        del new_mm
        del self._mm
        self.path.with_suffix(".grow").replace(self.path)
        self._capacity = new_capacity
        self._mm = np.memmap(self.path, dtype=np.float32, mode="r+", shape=(self._capacity, self.dim))

    def append(self, vec: np.ndarray) -> int:
        if self._count >= self._capacity:
            self._grow(self._count + 1)
        row = self._count
        self._mm[row] = vec
        self._count += 1
        self._mm.flush()
        self._count_path.write_text(str(self._count))
        return row

    def update(self, row: int, vec: np.ndarray) -> None:
        self._mm[row] = vec
        self._mm.flush()

    def get(self, row: int) -> np.ndarray:
        return np.array(self._mm[row])

    def search(self, query: np.ndarray, rows: Iterable[int], limit: int) -> list[tuple[int, float]]:
        row_list = list(rows)
        if not row_list:
            return []
        idx = np.array(row_list, dtype=np.int64)
        mat = np.asarray(self._mm)[idx]
        scores = mat @ query
        order = np.argsort(-scores)[:limit]
        return [(row_list[i], float(scores[i])) for i in order]

    @property
    def count(self) -> int:
        return self._count
