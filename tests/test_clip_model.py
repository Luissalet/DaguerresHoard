"""Optional: the real CLIP model end to end. Not part of the default run.

    pytest -m model            # uses ARGUS_MODELS_DIR or <repo>/data/models;
                               # downloads about 600 MB there if not cached

Indexes the synthetic demo scenes with the real embedder and checks that
plain-English queries find the matching scene (the fallback embedder
cannot do this; it only understands colour words)."""
from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from argus_hoard.config import Settings
from argus_hoard.demo import generate_demo_photos
from argus_hoard.embeddings import ClipEmbedder
from argus_hoard.library import Library

pytestmark = pytest.mark.model
REPO = Path(__file__).resolve().parents[1]


def test_real_clip_finds_scenes_by_description(tmp_path):
    models_dir = Path(os.environ.get("ARGUS_MODELS_DIR", REPO / "data" / "models"))
    embedder = ClipEmbedder(models_dir, local_only=False)
    generate_demo_photos(tmp_path / "photos", count=24)
    lib = Library(Settings(data_dir=tmp_path / "data"), embedder=embedder)
    root = lib.add_root(str(tmp_path / "photos"))
    job_id = lib.start_scan(root["id"])
    deadline = time.time() + 300
    while lib.jobs.get(job_id)["status"] == "running" and time.time() < deadline:
        time.sleep(0.2)
    assert lib.jobs.get(job_id)["status"] == "done"
    for query, scene in (
        ("sunset over the sea", "sunset"),
        ("a sandy beach and blue ocean", "sea"),
        ("pine trees in a forest", "forest"),
        ("a whiteboard with handwritten notes", "whiteboard"),
    ):
        top = lib.search(query, limit=3)["results"]
        assert all(Path(r["path"]).name.startswith(scene) for r in top), (query, [r["path"] for r in top])
