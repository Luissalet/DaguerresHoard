"""Native module ownership adapted from Prospero CAS2 590a0ca."""
import asyncio
from contextlib import asynccontextmanager
from .cancellation import join_tasks

class Module:
    async def work(self, function, *args):
        """A sync native operation keeps its lease through cancelled waiters."""
        async def run():
            async with self.use():
                return await asyncio.to_thread(function,*args)
        task=asyncio.create_task(run())
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            await join_tasks([task])
            raise

    def __init__(self, name, factory, root, port, demo):
        self.name, self.factory, self.root, self.port, self.demo = name, factory, root, port, demo
        self.lock = asyncio.Lock()
        self.app = self.context = None
        self.phase = 'off'
        self.automatic = False
        self.requests = {}
        self.transition = None

    def status(self):
        return dict(id=self.name, enabled=self.phase == 'on', phase=self.phase, automatic=self.automatic,
                    active=len(self.requests), url=f'/{self.name}/')

    async def set(self, enabled, automatic=False):
        # Cancellation of a control request must not abandon a half-open/closed owner.
        async with self.lock:
            task = asyncio.create_task(self._set(enabled, automatic))
            self.transition = task
            try:
                return await asyncio.shield(task)
            except asyncio.CancelledError:
                await join_tasks([task])
                raise
            finally:
                self.transition = None

    async def _set(self, enabled, automatic):
        if enabled and self.app is None:
            self.phase = 'starting'
            app = None
            try:
                app = await self.factory(self.root, self.port, self.demo, automatic)
                context = app.router.lifespan_context(app)
                await context.__aenter__()
                self.app, self.context, self.automatic = app, context, bool(automatic)
                self.phase = 'on'
            except BaseException:
                if app is not None and hasattr(app.state, 'shutdown'):
                    await asyncio.to_thread(app.state.shutdown)
                self.phase = 'off'
                raise
        elif not enabled and self.app is not None:
            self.phase = 'stopping'
            # Disconnect active response bodies, then wait for their finally blocks.
            # In-flight ordinary writes finish before resources can close.
            active = list(self.requests.items())
            for _task, disconnect in active:
                disconnect.set()
            if active:
                await asyncio.gather(*(t for t, _ in active), return_exceptions=True)
            await self.context.__aexit__(None, None, None)
            self.app = self.context = None
            self.phase, self.automatic = 'off', False
        return self.status()

    @asynccontextmanager
    async def use(self):
        async with self.lock:
            if self.phase != 'on':
                raise ValueError(f'{self.name} is OFF. Enable it explicitly in Modules.')
            task = asyncio.current_task()
            disconnect = asyncio.Event()
            self.requests[task] = disconnect
            app = self.app
        try:
            yield app, disconnect
        finally:
            self.requests.pop(task, None)

    async def request(self, scope, receive, send):
        # The child owns a distinct task: OFF can await it independently of its caller.
        async def run():
            async with self.use() as (app, disconnect):
                started = False
                async def native_receive():
                    incoming = asyncio.create_task(receive())
                    stopped = asyncio.create_task(disconnect.wait())
                    try:
                        done, _ = await asyncio.wait({incoming, stopped}, return_when=asyncio.FIRST_COMPLETED)
                        return {'type': 'http.disconnect'} if stopped in done else incoming.result()
                    finally:
                        for pending in (incoming, stopped):
                            if not pending.done():
                                pending.cancel()
                        await asyncio.gather(incoming, stopped, return_exceptions=True)
                async def native_send(message):
                    nonlocal started
                    if message['type'] == 'http.response.start':
                        started = True
                    if started and disconnect.is_set():
                        raise asyncio.CancelledError()
                    await send(message)
                from .global_model import scope as global_scope
                with global_scope():
                    await app(scope, native_receive, native_send)
        task = asyncio.create_task(run())
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            # Disconnect the stream, but don't lose an already dispatched mutation.
            event = self.requests.get(task)
            if event:
                event.set()
            await join_tasks([task])
            raise
