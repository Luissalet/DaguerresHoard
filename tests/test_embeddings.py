import os
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

from daguerre_hoard.embeddings import FakeEmbedder, VectorStore


def test_fake_embedder_ranks_red_image_first_for_red_query(tmp_path):
    red = tmp_path / "red.jpg"
    green = tmp_path / "green.jpg"
    blue = tmp_path / "blue.jpg"
    Image.new("RGB", (64, 64), (220, 20, 20)).save(red)
    Image.new("RGB", (64, 64), (20, 200, 20)).save(green)
    Image.new("RGB", (64, 64), (20, 20, 220)).save(blue)

    embedder = FakeEmbedder()
    vectors = embedder.embed_images([red, green, blue])
    query = embedder.embed_text("a red square")

    scores = vectors @ query
    best = int(np.argmax(scores))
    assert best == 0  # red.jpg


def test_vector_store_append_and_grow(tmp_path):
    store = VectorStore(tmp_path / "vectors.f32", dim=8)
    rows = []
    for i in range(600):  # forces at least one grow beyond the initial 256 capacity
        vec = np.zeros(8, dtype=np.float32)
        vec[i % 8] = 1.0
        rows.append(store.append(vec))
    assert store.count == 600
    assert rows == list(range(600))
    got = store.get(599)
    assert got[599 % 8] == 1.0


def test_vector_store_persists_across_reopen(tmp_path):
    path = tmp_path / "vectors.f32"
    store = VectorStore(path, dim=4)
    row = store.append(np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32))
    del store
    reopened = VectorStore(path, dim=4)
    assert reopened.count == 1
    assert reopened.get(row)[0] == 1.0


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_fake_text_embedding_is_stable_across_processes():
    code = (
        "import sys; sys.path.insert(0, %r);"
        "from daguerre_hoard.embeddings import FakeEmbedder;"
        "print(FakeEmbedder().embed_text('dog on the beach')[:4].round(6).tolist())"
    ) % str(REPO_ROOT)
    outs = set()
    for seed in ("1", "2"):
        env = dict(os.environ, PYTHONHASHSEED=seed)
        outs.add(subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, check=True).stdout)
    assert len(outs) == 1
