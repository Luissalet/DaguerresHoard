"""Synthetic stores and events; no network, model or native executable."""
import threading

from daguerre_hoard.config import Settings
from daguerre_hoard.embeddings import FakeEmbedder
from daguerre_hoard.library import Library


def test_manual_activation_does_not_regeocode(monkeypatch, tmp_path):
    def unexpected(_self):
        raise AssertionError('automatic geocoding was invoked')
    monkeypatch.setattr(Library, '_maybe_regeocode', unexpected)
    library = Library(Settings(tmp_path), embedder=FakeEmbedder(), automatic=False)
    library.close()
    assert library.vectors._mm is None


def test_close_joins_a_held_job_before_closing_database(tmp_path):
    library = Library(Settings(tmp_path), embedder=FakeEmbedder(), automatic=False)
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    def job(handle):
        entered.set()
        release.wait()
        handle.set_stats({'preserved': True})
        finished.set()
    job_id = library.jobs.start('held', job)
    assert entered.wait(2)
    closing = threading.Thread(target=library.close)
    closing.start()
    assert not finished.is_set() and not library._closed
    release.set()
    closing.join(3)
    assert not closing.is_alive() and finished.is_set() and library._closed
