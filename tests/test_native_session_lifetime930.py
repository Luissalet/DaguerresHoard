"""Causal drain tests with held native work; no engine or window."""
import asyncio
from contextlib import asynccontextmanager
import threading
from types import SimpleNamespace

import pytest

from daguerre_hoard.studio_lifecycle import Module
from daguerre_hoard.studio_native.durer.durer_hoard.sessions import NativeSessions


def test_close_waits_for_timed_out_native_save_and_reconciliation(tmp_path, monkeypatch):
    sessions = NativeSessions()
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    async def execute(*_args):
        entered.set()
        await asyncio.to_thread(release.wait)
        (tmp_path/'native.document').write_bytes(b'saved after request timeout')
        finished.set()
        return ['saved']
    monkeypatch.setattr(sessions, '_execute', execute)
    with pytest.raises(TimeoutError, match='may still complete'):
        sessions.execute('p', tmp_path/'native.document', [], timeout=.05)
    assert entered.is_set() and not finished.is_set()
    operation = next(iter(sessions.operations))
    closing = threading.Thread(target=sessions.close)
    closing.start()
    assert closing.is_alive() and sessions.thread.is_alive()
    release.set()
    closing.join(3)
    assert not closing.is_alive() and finished.is_set()
    assert sessions.loop is sessions.thread is None
    assert sessions.operation(operation)['state'] == 'completed'
    assert sessions.operation(operation)['result'] == ['saved']


@pytest.mark.asyncio
async def test_repeated_caller_cancellation_cannot_release_native_work_before_off(tmp_path):
    entered, release, saved = threading.Event(), threading.Event(), threading.Event()
    closed = asyncio.Event()
    @asynccontextmanager
    async def lifetime(_app):
        yield
        assert saved.is_set()
        closed.set()
    async def factory(*_args):
        return SimpleNamespace(router=SimpleNamespace(lifespan_context=lifetime))
    module = Module('vector', factory, tmp_path, 1, False)
    await module.set(True)
    def work():
        entered.set()
        release.wait()
        saved.set()
    request = asyncio.create_task(module.work(work))
    await asyncio.to_thread(entered.wait)
    request.cancel()
    await asyncio.sleep(0)
    request.cancel()
    stopping = asyncio.create_task(module.set(False))
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    assert module.phase == 'stopping' and not closed.is_set()
    assert not request.done() and not stopping.done()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await request
    await stopping
    assert closed.is_set() and module.phase == 'off' and not module.requests


@pytest.mark.asyncio
async def test_failed_async_generator_close_retries_owned_cleanup_before_off(tmp_path):
    repaired=threading.Event()
    calls=[]
    def shutdown():
        calls.append('close')
        if not repaired.is_set():raise RuntimeError('owned window is unavailable')
    @asynccontextmanager
    async def lifetime(_app):
        yield
        shutdown()
    async def factory(*_args):
        return SimpleNamespace(router=SimpleNamespace(lifespan_context=lifetime),state=SimpleNamespace(shutdown=shutdown))
    module=Module('vector',factory,tmp_path,1,False)
    await module.set(True)
    for count in (1,2):
        with pytest.raises(ValueError,match='close is incomplete'):
            await module.set(False)
        assert module.phase=='stopping' and module.app is not None
        assert len(calls)==count
    repaired.set()
    await module.set(False)
    assert len(calls)==3 and module.phase=='off' and module.app is None


@pytest.mark.asyncio
@pytest.mark.parametrize('name',['photos','vector'])
async def test_real_native_factory_retains_resources_across_two_failed_closes(tmp_path,monkeypatch,name):
    from daguerre_hoard.studio import Studio
    studio=Studio(tmp_path/'data',demo=True)
    module=studio.modules[name]
    await module.set(True)
    if name=='photos':
        owner=module.app.state.library.craft_engines
        field='close'
        library=module.app.state.library
    else:
        from daguerre_hoard.studio_native.durer.durer_hoard import native as owner
        field='close_guis'
    original=getattr(owner,field);calls=[]
    def close():
        calls.append(1)
        if len(calls)<3:raise RuntimeError('synthetic owned-window failure')
        original()
    monkeypatch.setattr(owner,field,close)
    try:
        for count in (1,2):
            with pytest.raises(ValueError,match='close is incomplete'):
                await module.set(False)
            assert module.phase=='stopping' and module.app is not None and len(calls)==count
            with pytest.raises(ValueError,match='Retry OFF'):
                await module.set(True)
            if name=='photos':
                assert not library._closed
                assert library.conn.execute('SELECT 1').fetchone()[0]==1
        await module.set(False)
        assert module.phase=='off' and module.app is None and len(calls)==3
        if name=='photos':assert library._closed and library.vectors._mm is None
    finally:
        monkeypatch.setattr(owner,field,original)
        await studio.close()
