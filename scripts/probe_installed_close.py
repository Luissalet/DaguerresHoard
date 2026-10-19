"""Installed real photo/HTTP owner close retry, with all HTTP requests forbidden."""
import argparse
import asyncio
import json
from pathlib import Path
import sys
import threading


async def check(target, profile):
    sys.path.insert(0, str(target))
    import httpx
    from daguerre_hoard.studio import Studio
    async def forbidden(*args, **kwargs):
        raise AssertionError('No network is allowed in this close probe')
    httpx.AsyncClient.request = forbidden
    cases = []
    for retiring in (False, True):
        root = profile / ('retiring' if retiring else 'current')
        assert not root.exists(), 'Use a new synthetic profile'
        studio = Studio(root, demo=True)
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
                raise OSError('injected installed HTTP close failure')
            await close()
        inner._client.aclose = fail_twice
        if retiring:
            backend.link = backend._build_link()
            timer = threading.Timer(3600, lambda: None)
            timer.daemon = True
            backend._retiring[timer] = link
            timer.start()
        try:
            for count in (1, 2):
                try:
                    await module.set(False)
                except ValueError as error:
                    assert 'HTTP close failure' in str(error)
                else:
                    raise AssertionError('Failed cleanup reported OFF')
                assert len(attempts) == count and module.app is app and module.phase == 'stopping'
                assert not app.state.library._closed and not inner._client.is_closed
                assert link.sync._inner is inner and link.sync._loop is loop and link.sync._thread is thread
                assert thread.is_alive() and loop.is_running()
                if retiring:
                    assert link in backend._retiring.values()
                try:
                    await module.set(True)
                except ValueError:
                    pass
                else:
                    raise AssertionError('ON replaced a retained owner')
            await module.set(False)
            assert attempts == [1, 2, 3] and module.phase == 'off' and module.app is None
            assert app.state.library._closed and inner._client.is_closed
            assert loop.is_closed() and not thread.is_alive() and not backend._retiring
            assert link.sync._inner is link.sync._loop is link.sync._thread is None
            await module.set(False)
            assert attempts == [1, 2, 3]
            cases.append({'retiring': retiring, 'attempts': attempts, 'same_owner': True, 'closed_and_joined': True})
        finally:
            inner._client.aclose = close
            await module.set(False)
            await link._client.aclose()
            if backend.link is not link:
                await backend.link._client.aclose()
    loaded = [str(Path(m.__file__).resolve()) for n, m in sys.modules.copy().items()
        if n.startswith('daguerre_hoard') and getattr(m, '__file__', None)]
    assert loaded and all(Path(path).is_relative_to(target) for path in loaded)
    print(json.dumps({'result': 'PASS', 'target': str(target), 'cases': cases, 'owned_modules_from_target': len(loaded)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', type=Path, required=True)
    parser.add_argument('--profile', type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(check(args.target.resolve(), args.profile.resolve()))
