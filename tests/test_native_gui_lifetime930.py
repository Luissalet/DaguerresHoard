"""Native close/save barriers with fake owned processes; no window is opened."""
import threading
from daguerre_hoard import native_gui
from daguerre_hoard.config import Settings
from daguerre_hoard.embeddings import FakeEmbedder
from daguerre_hoard.library import Library


def test_library_waits_for_owned_editor_save_and_exit_before_stores_close(tmp_path,monkeypatch):
    library=Library(Settings(tmp_path/'data'),embedder=FakeEmbedder(),automatic=False)
    close_requested,release=threading.Event(),threading.Event()
    saved=tmp_path/'saved-native-document.dglayers'
    class Process:
        pid=12345
        def poll(self):return 0 if saved.exists() else None
        def wait(self):
            release.wait()
            saved.write_bytes(b'completed native save')
            return 0
    def request(pid):
        assert pid==12345
        close_requested.set()
    monkeypatch.setattr(native_gui,'request_close',request)
    library.craft_engines._editors['layers']={'process':Process()}
    closing=threading.Thread(target=library.close)
    closing.start()
    assert close_requested.wait(2)
    assert not library._closed and library.vectors._mm is not None and not saved.exists()
    assert library.conn.execute('SELECT 1').fetchone()[0]==1
    release.set()
    closing.join(3)
    assert not closing.is_alive() and library._closed
    assert saved.read_bytes()==b'completed native save'
    assert not library.craft_engines._editors
