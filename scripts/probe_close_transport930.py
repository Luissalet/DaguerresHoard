"""Real HTTPX transport failures inside photo factories; ASGI only, no sockets."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
import subprocess
import threading

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--target', type=Path, required=True)
parser.add_argument('--profile', type=Path, required=True)
args = parser.parse_args()
target, root = args.target.resolve(), args.profile.resolve()
assert not root.exists(), 'Use a new synthetic profile'
sys.path.insert(0, str(target))
os.environ.update(HOARD_EVENTS='0', HOARD_AUTO_REGISTER='0', DAGUERRE_DATA_DIR=str(root))


async def endpoint(scope, receive, send):
    await send({'type': 'http.response.start', 'status': 200, 'headers': []})
    await send({'type': 'http.response.body', 'body': b'{}'})


async def main():
    import httpx
    import httpcore
    from httpcore._async.http11 import AsyncHTTP11Connection
    from httpcore._models import Origin
    from daguerre_hoard.global_model import OwnedAsyncClient
    from daguerre_hoard.studio import Studio
    popen = subprocess.Popen
    def forbidden_child(*args, **kwargs):
        raise AssertionError('Cold discovery started a child')
    subprocess.Popen = forbidden_child
    try:
        cold = Studio(root / 'cold', demo=True)
        assert len(cold.tools) == 95 and all(m.phase == 'off' for m in cold.modules.values())
        assert not root.exists()
        assert 'daguerre_hoard.library' not in sys.modules
        assert 'onnxruntime' not in sys.modules and 'fastembed' not in sys.modules
    finally:
        subprocess.Popen = popen
    send = httpx.AsyncClient.send
    async def no_network(self, *args, **kwargs):
        assert isinstance(self._transport, httpx.ASGITransport)
        return await send(self, *args, **kwargs)
    httpx.AsyncClient.send = no_network
    httpx.Client.send = lambda *a, **kw: (_ for _ in ()).throw(AssertionError('No network'))

    class RetryTransport(httpx.ASGITransport):
        def __init__(self, held=False):
            super().__init__(app=endpoint)
            self.attempts, self.resource_open = 0, True
            self.entered, self.release = threading.Event(), threading.Event()
            if not held:
                self.release.set()
        async def aclose(self):
            self.attempts += 1
            if self.attempts < 3:
                raise OSError('injected transport close failure')
            self.entered.set()
            await asyncio.to_thread(self.release.wait)
            await super().aclose()
            self.resource_open = False

    # Exercise a real HTTPX transport/httpcore pool, not only ASGI transports.
    class Stream:
        def __init__(self, failures):
            self.attempts, self.failures, self.open = 0, failures, True
        async def aclose(self):
            self.attempts += 1
            if self.attempts <= self.failures:
                raise OSError('injected pooled stream close failure')
            self.open = False
    pool_client = OwnedAsyncClient(trust_env=False)
    pool = pool_client._transport._pool
    origin = Origin(b'http', b'synthetic.invalid', 80)
    good, failing = Stream(0), Stream(2)
    connections = []
    for stream in (good, failing):
        connection = httpcore.AsyncHTTPConnection(origin)
        connection._connection = AsyncHTTP11Connection(origin, stream)
        connections.append(connection)
    pool._connections = connections.copy()
    for attempt in (1, 2):
        try:
            await pool_client.aclose()
        except OSError:
            pass
        else:
            raise AssertionError('A consumed HTTPX/pool close reported success')
        assert pool_client.is_closed and failing.open and failing.attempts == attempt
        assert good.attempts == 1 and not good.open
        assert pool._connections == [connections[1]]
    await pool_client.aclose()
    await pool_client.aclose()
    assert not failing.open and failing.attempts == 3 and good.attempts == 1
    assert not pool._connections and not pool_client._close_pending

    cases = []
    for retiring in (False, True):
        for parent in (False, True):
            studio = Studio(root / f'{retiring}-{parent}', demo=True)
            module = studio.modules['photos']
            await module.set(True)
            app = module.app
            backend = app.state.library.backend
            link = backend.link
            link.sync._run(lambda _: asyncio.sleep(0))
            inner, loop, thread = link.sync._inner, link.sync._loop, link.sync._thread
            client = link._client if parent else inner._client
            held = retiring and parent
            transport = RetryTransport(held)
            if parent:
                await client._transport.aclose()
                client._transport = transport
                response = await client.get('http://synthetic.invalid')
            else:
                link.sync._run(lambda _: client._transport.aclose())
                client._transport = transport
                response = link.sync._run(lambda _: client.get('http://synthetic.invalid'))
            assert response.status_code == 200
            if retiring:
                backend.link = backend._build_link()
                timer = threading.Timer(3600, lambda: None)
                timer.daemon = True
                backend._retiring[timer] = link
                timer.start()
            snapshots = []
            try:
                for n in (1, 2):
                    try:
                        await module.set(False)
                    except ValueError as error:
                        assert 'transport close failure' in str(error)
                    else:
                        raise AssertionError('Failed transport reported OFF')
                    assert transport.attempts == n and transport.resource_open
                    assert client.is_closed and client._close_pending
                    assert module.app is app and module.phase == 'stopping'
                    assert not app.state.library._closed
                    assert link.sync._inner is inner and link.sync._loop is loop and link.sync._thread is thread
                    assert loop.is_running() and thread.is_alive()
                    if retiring:
                        assert link in backend._retiring.values()
                    try:
                        await module.set(True)
                    except ValueError:
                        pass
                    else:
                        raise AssertionError('ON replaced retained owner')
                    snapshots.append({'off': n, 'attempts': transport.attempts, 'app_retained': True,
                        'HTTPX_closed': client.is_closed, 'transport_open': transport.resource_open})
                if held:
                    closing = asyncio.create_task(module.set(False))
                    assert await asyncio.to_thread(transport.entered.wait, 5)
                    closing.cancel()
                    await asyncio.sleep(.02)
                    closing.cancel()
                    await asyncio.sleep(.02)
                    assert not closing.done() and module.app is app and transport.resource_open
                    transport.release.set()
                    try:
                        await closing
                    except asyncio.CancelledError:
                        pass
                else:
                    await module.set(False)
                assert transport.attempts == 3 and not transport.resource_open
                assert module.phase == 'off' and module.app is None and app.state.library._closed
                assert inner._client.is_closed and link._client.is_closed and backend.link._client.is_closed
                assert loop.is_closed() and not thread.is_alive()
                assert link.sync._inner is link.sync._loop is link.sync._thread is None
                assert not backend._retiring
                await module.set(False)
                assert transport.attempts == 3
                cases.append({'retiring': retiring, 'parent': parent, 'snapshots': snapshots,
                    'third_attempt_closed': True, 'parent_and_twin_closed': True,
                    'cancelled_twice_during_third': held, 'loop_closed_thread_joined': True})
            finally:
                transport.release.set()
                await module.set(False)
    loaded = [str(Path(m.__file__).resolve()) for n, m in sys.modules.copy().items()
        if n.startswith('daguerre_hoard') and getattr(m, '__file__', None)]
    assert loaded and all(Path(p).is_relative_to(target) for p in loaded)
    print(json.dumps({'result': 'PASS', 'target': str(target), 'cases': cases,
        'cold_catalogue': 95, 'cold_modules': 'OFF/OFF',
        'real_HTTPX_transport_httpcore_pool': {'failed_stream_attempts': failing.attempts,
            'successful_stream_not_repeated': good.attempts, 'pool_empty': not pool._connections},
        'owned_modules_from_target': len(loaded)}, indent=2))


asyncio.run(main())
