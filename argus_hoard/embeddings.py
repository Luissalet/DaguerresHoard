"""Image/text embedding backends and the on-disk vector store.

`Embedder` is the interface the indexing pipeline and search use. Two
implementations exist:

- `FakeEmbedder`: a deterministic colour-histogram embedding. Used by
  default in tests and whenever the real model is not downloaded, so tests
  never hit the network. A "red" text query finds a red image because the
  text embedder maps colour-name keywords onto the same histogram axes.
- `ClipEmbedder`: real CLIP (ViT-B/32) via `fastembed` + ONNX Runtime, no
  PyTorch. Downloads about 600 MB from Hugging Face on explicit request into
  `data/models`; the caller is responsible for surfacing that to the user.

Both embed into the same `EMBED_DIM`-dimensional, L2-normalised space so
cosine similarity == dot product.
"""
from __future__ import annotations

import hashlib
import re
import threading
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
            img = img.convert("RGB").resize((64, 64), Image.BILINEAR)
            arr = np.asarray(img, dtype=np.float32) / 255.0
        hsv = _rgb_to_hsv(arr)
        hue = hsv[..., 0].flatten()
        sat = hsv[..., 1].flatten()
        val = hsv[..., 2].flatten()
        hue_hist, _ = np.histogram(hue, bins=self.dim - 32, range=(0.0, 1.0), weights=sat + 0.05)
        val_hist, _ = np.histogram(val, bins=32, range=(0.0, 1.0))
        vec = np.concatenate([hue_hist, val_hist]).astype(np.float32)
        return vec

    @staticmethod
    def has_color_word(text: str) -> bool:
        """Whether `text` contains one of the colour words the histogram
        embedding actually understands. Used to calibrate relevance bands:
        a query with no colour word gets a meaningless (hash-seeded) vector,
        so it must never look as confident as a real colour match."""
        words = re.findall(r"[a-zA-Z]+", (text or "").lower())
        return any(w == name or w.rstrip("s") == name for w in words for name in _COLOR_WORDS)

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
            # (blake2b, not hash(): str hashing is salted per process.)
            digest = hashlib.blake2b(" ".join(sorted(words)).encode("utf-8"), digest_size=8).digest()
            rng = np.random.default_rng(int.from_bytes(digest, "little"))
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
_CLIP_LOCK = threading.Lock()
CLIP_IMAGE_MODEL = "Qdrant/clip-ViT-B-32-vision"
CLIP_TEXT_MODEL = "Qdrant/clip-ViT-B-32-text"


class ClipEmbedder:
    """Real CLIP embeddings via fastembed (ONNX Runtime, no PyTorch).

    `local_only=True` never touches the network (used at start-up, so an
    incomplete cache cannot turn app launch into a 600 MB download);
    `local_only=False` is the explicit, user-triggered download."""

    name = "clip-vit-b32"
    dim = EMBED_DIM

    def __init__(self, cache_dir: Path, local_only: bool = True):
        from fastembed import ImageEmbedding, TextEmbedding  # local import: optional dep

        cache_dir.mkdir(parents=True, exist_ok=True)
        key = str(cache_dir)
        with _CLIP_LOCK:
            if key not in _CLIP_SINGLETON:
                kwargs = {"cache_dir": str(cache_dir), "local_files_only": local_only}
                _CLIP_SINGLETON[key] = (
                    ImageEmbedding(CLIP_IMAGE_MODEL, **kwargs),
                    TextEmbedding(CLIP_TEXT_MODEL, **kwargs),
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
    def cache_state(cache_dir: Path) -> dict:
        """Which of the two CLIP halves are on disk, and how big the cache is."""
        state = {"image": False, "text": False, "bytes": 0}
        if not cache_dir.exists():
            return state
        for f in cache_dir.rglob("*"):
            try:
                # the Hugging Face cache links snapshot files to blobs:
                # count each blob once, not once per link
                if f.is_file() and not f.is_symlink():
                    state["bytes"] += f.stat().st_size
            except OSError:
                continue
            if f.suffix == ".onnx":
                low = str(f).lower()
                if "vision" in low:
                    state["image"] = True
                elif "text" in low:
                    state["text"] = True
        return state

    @staticmethod
    def is_cached(cache_dir: Path) -> bool:
        state = ClipEmbedder.cache_state(cache_dir)
        return state["image"] and state["text"]


class VectorStore:
    """Append-only float32 matrix on disk, memory-mapped, with a row count
    side file. Grows by doubling in place (the mapping is closed, the file
    extended, and re-mapped -- no rename, so it also works on Windows,
    where a mapped file cannot be replaced). Every access holds a lock so a
    search never reads through a mapping that is being swapped. Brute-force
    cosine search is documented as fine up to ~200k images."""

    def __init__(self, path: Path, dim: int = EMBED_DIM):
        self.path = path
        self.dim = dim
        self._count_path = path.with_suffix(".count")
        self._capacity = 0
        self._count = 0
        self._mm: np.memmap | None = None
        self._lock = threading.RLock()
        self._load()

    def _row_bytes(self) -> int:
        return self.dim * 4

    def _load(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists() and self.path.stat().st_size >= self._row_bytes():
            if self._count_path.exists():
                try:
                    self._count = int(self._count_path.read_text(encoding="utf-8").strip() or 0)
                except ValueError:
                    self._count = 0
            self._capacity = self.path.stat().st_size // self._row_bytes()
            self._count = max(0, min(self._count, self._capacity))
            self._mm = np.memmap(self.path, dtype=np.float32, mode="r+", shape=(self._capacity, self.dim))
            return
        self._capacity = 256
        self._mm = np.memmap(self.path, dtype=np.float32, mode="w+", shape=(self._capacity, self.dim))
        self._mm.flush()
        self._write_count()

    def _write_count(self) -> None:
        tmp = self._count_path.with_suffix(".count.tmp")
        tmp.write_text(str(self._count), encoding="utf-8")
        tmp.replace(self._count_path)

    def _grow(self, min_capacity: int) -> None:
        new_capacity = max(self._capacity * 2, min_capacity, 256)
        assert self._mm is not None
        self._mm.flush()
        mm, self._mm = self._mm, None
        del mm  # last reference: closes the mapping before the file is resized
        with open(self.path, "r+b") as f:
            f.truncate(new_capacity * self._row_bytes())
        self._capacity = new_capacity
        self._mm = np.memmap(self.path, dtype=np.float32, mode="r+", shape=(self._capacity, self.dim))

    def append(self, vec: np.ndarray) -> int:
        with self._lock:
            if self._count >= self._capacity:
                self._grow(self._count + 1)
            row = self._count
            self._mm[row] = vec
            self._count += 1
            self._mm.flush()
            self._write_count()
            return row

    def update(self, row: int, vec: np.ndarray) -> None:
        with self._lock:
            self._mm[row] = vec
            self._mm.flush()

    def get(self, row: int) -> np.ndarray:
        with self._lock:
            return np.array(self._mm[row])

    def scores(self, query: np.ndarray, rows: Iterable[int]) -> tuple[list[int], np.ndarray]:
        """Cosine (dot product of unit vectors) of `query` against `rows`."""
        row_list = list(rows)
        if not row_list:
            return [], np.zeros(0, dtype=np.float32)
        idx = np.array(row_list, dtype=np.int64)
        with self._lock:
            mat = np.asarray(self._mm)[idx]  # fancy indexing copies
        return row_list, mat @ np.asarray(query, dtype=np.float32)

    def search(self, query: np.ndarray, rows: Iterable[int], limit: int) -> list[tuple[int, float]]:
        row_list, scores = self.scores(query, rows)
        if not row_list:
            return []
        order = np.argsort(-scores, kind="stable")[:limit]
        return [(row_list[i], float(scores[i])) for i in order]

    @property
    def count(self) -> int:
        return self._count
