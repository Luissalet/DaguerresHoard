"""Real owned Link/twin/httpx close failures; no HTTP request or model."""
import asyncio
import threading

import httpx
import pytest

from daguerre_hoard.studio import Studio


@pytest.mark.parametrize('retiring', [False, True])
def test_real_photo_owner_retains_failed_inner_until_third_off(tmp_path, monkeypatch, retiring):
    async def forbidden(*args, **kwargs):
        raise AssertionError('This close test must not send HTTP')
    monkeypatch.setattr(httpx.AsyncClient, 'request', forbidden)

    async def run():
        studio = Studio(tmp_path, demo=True)
        module = studio.modules['photos']
        await module.set(True)
        app = module.app
        backend = app.state.library.backend
        link = backend.link
        link.sync._run(lambda _: asyncio.sleep(0))
        inner, loop, thread = link.sync._inner, link.sync._loop, link.sync._thread
        close = inner._client.aclose
        attempts = []

        async def fail_twice():
            attempts.append(len(attempts) + 1)
            if len(attempts) < 3:
                raise OSError('injected real HTTP close failure')
            await close()
        monkeypatch.setattr(inner._client, 'aclose', fail_twice)
        if retiring:
            # The actual retirement registry must retain this owner on failure.
            backend.link = backend._build_link()
            timer = threading.Timer(3600, lambda: None)
            timer.daemon = True
            backend._retiring[timer] = link
            timer.start()
        try:
            for count in (1, 2):
                with pytest.raises(ValueError, match='HTTP close failure'):
                    await module.set(False)
                assert len(attempts) == count
                assert module.app is app and module.phase == 'stopping'
                assert not app.state.library._closed
                assert not inner._client.is_closed
                assert link.sync._inner is inner and link.sync._loop is loop
                assert link.sync._thread is thread and thread.is_alive() and loop.is_running()
                if retiring:
                    assert link in backend._retiring.values()
                with pytest.raises(ValueError, match='Retry OFF'):
                    await module.set(True)
                assert module.app is app
            await module.set(False)
            assert attempts == [1, 2, 3]
            assert module.phase == 'off' and module.app is None
            assert app.state.library._closed and inner._client.is_closed
            assert loop.is_closed() and not thread.is_alive()
            assert link.sync._inner is link.sync._loop is link.sync._thread is None
            assert not backend._retiring
            await module.set(False)
            assert attempts == [1, 2, 3]
        finally:
            monkeypatch.setattr(inner._client, 'aclose', close)
            await module.set(False)
            await link._client.aclose()
            if backend.link is not link:
                await backend.link._client.aclose()
    asyncio.run(run())
