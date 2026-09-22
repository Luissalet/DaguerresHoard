"""start_caption_batch: the good-citizen wait_idle("vision") loop -- a
background batch yields to the shared model instead of racing whatever the
owner is doing with it, per CONTRACT_BACKEND.md's "good citizen" rule."""
from __future__ import annotations

import time

from argus_hoard.captions import CaptionResult
from tests.conftest import make_image


def _wait(library, job_id, timeout=10.0):
    start = time.time()
    while time.time() - start < timeout:
        job = library.jobs.get(job_id)
        if job and job["status"] not in ("running", "queued"):
            return job
        time.sleep(0.01)
    raise TimeoutError(library.jobs.get(job_id))


class _StubCaptioner:
    def __init__(self):
        self.calls = 0

    def test_connection(self):
        return CaptionResult(ok=True)

    def caption(self, path):
        self.calls += 1
        return CaptionResult(ok=True, caption=f"caption {self.calls}")


def test_batch_waits_while_the_shared_model_is_busy(library, tmp_path, monkeypatch):
    make_image(tmp_path / "photos" / "a.jpg", color=(200, 30, 30))
    root = library.add_root(str(tmp_path / "photos"))
    job = _wait(library, library.start_scan(root["id"]))
    assert job["status"] == "done"

    stub = _StubCaptioner()
    monkeypatch.setattr(library, "_captioner", lambda: stub)

    # Busy on the first two polls, then idle: the batch must not caption
    # while busy, and must proceed once wait_idle finally returns True.
    calls = {"n": 0}

    def fake_wait_idle(capability, max_wait_s=30.0):
        assert capability == "vision"
        calls["n"] += 1
        return calls["n"] > 2

    monkeypatch.setattr(library.backend.link.sync, "wait_idle", fake_wait_idle)
    job = _wait(library, library.start_caption_batch())
    assert job["status"] == "done", job
    assert stub.calls == 1
    assert calls["n"] >= 3  # busy, busy, idle


def test_batch_captions_immediately_when_never_busy(library, tmp_path, monkeypatch):
    make_image(tmp_path / "photos" / "a.jpg", color=(200, 30, 30))
    make_image(tmp_path / "photos" / "b.jpg", color=(30, 200, 30))
    root = library.add_root(str(tmp_path / "photos"))
    _wait(library, library.start_scan(root["id"]))

    stub = _StubCaptioner()
    monkeypatch.setattr(library, "_captioner", lambda: stub)
    monkeypatch.setattr(library.backend.link.sync, "wait_idle", lambda capability, max_wait_s=30.0: True)

    job = _wait(library, library.start_caption_batch())
    assert job["status"] == "done", job
    assert stub.calls == 2
    assert job["stats"]["captioned"] == 2
