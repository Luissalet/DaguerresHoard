# Owned adaptation of Prospero d412923 global_model.py; no runtime checkout dependency.
"""Consumer of Faustus938's stateless global model contract; no SDK changes.

Pin once per request/job, including its repair calls. A synchronous SDK facade
normally clones the base Link: this owned facade preserves the overrides.
"""
import asyncio
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
import threading

import httpx
from httpx._client import ClientState

from .hoard_link import BackendError, Link
from .hoard_link._sync import SyncFacade
from .hoard_link.types import Resolution
from .hoard_link.reasoning import timeout_for

_job = ContextVar('daguerre_global_job', default=None)


class Pin:
    def __init__(self):
        self.lock, self.choice = threading.Lock(), None


@contextmanager
def scope():
    token = _job.set(Pin())
    try:
        yield
    finally:
        _job.reset(token)


def job(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        with scope():
            return function(*args, **kwargs)
    return wrapped


def operation(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        if _job.get() is not None:
            return function(*args, **kwargs)
        with scope():
            return function(*args, **kwargs)
    return wrapped


def descriptor(config):
    if not config.faustus_urls:
        raise RuntimeError('Faustus no tiene un servicio global configurado.')
    origin = config.faustus_urls[0].rstrip('/')
    headers = {'Authorization':'Bearer '+config.faustus_token} if config.faustus_token else {}
    with httpx.Client(timeout=10, trust_env=False) as client:
        response = client.get(origin+'/api/global-model', headers=headers)
        response.raise_for_status()
        data = response.json()
    if data.get('protocol') != 'openai' or data.get('chat_path') != '/api/global-model/v1/chat/completions':
        raise RuntimeError('El servicio global no ofrece chat OpenAI; no se ha elegido otro modelo.')
    if any(not isinstance(data.get(k),str) or not data[k] for k in ('endpoint_id','model','connection_revision')):
        raise RuntimeError('El descriptor global está incompleto.')
    return {**data, 'url':origin+data['chat_path'], 'headers':headers}


def payload(body, choice):
    return {**body, 'model':choice['model'],
        **{'expected_'+k:choice[k] for k in ('endpoint_id','model','connection_revision')}}


class OwnedAsyncClient(httpx.AsyncClient):
    """HTTPX 0.28.1 closes its state before its transports; retain those owners.

    Record each successful resource separately, including pooled connections that
    httpcore otherwise removes before closing. No SDK or HTTPX source is changed.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._close_pending = None
        self._owner_loop = None

    async def send(self, *args, **kwargs):
        self._owner_loop = asyncio.get_running_loop()
        return await super().send(*args, **kwargs)

    async def aclose(self):
        if self._close_pending is None:
            transports = [self._transport, *self._mounts.values()]
            resources = []
            for transport in transports:
                if transport is not None:
                    # Capture connections before the pool consumes its list.
                    pool = getattr(transport, '_pool', None)
                    resources.extend((connection, pool) for connection in getattr(pool, '_connections', ()))
                    resources.append((transport, None))
            seen = set()
            self._close_pending = []
            for resource, pool in resources:
                if id(resource) not in seen:
                    seen.add(id(resource))
                    self._close_pending.append((resource, pool))
        self._state = ClientState.CLOSED
        while self._close_pending:
            resource, pool = self._close_pending[0]
            await resource.aclose()
            if pool is not None:
                # A successful connection must not be closed again by its pool.
                with pool._optional_thread_lock:
                    pool._connections = [c for c in pool._connections if c is not resource]
            self._close_pending.pop(0)


async def close_client(client):
    owner = getattr(client, '_owner_loop', None)
    if owner is not None and owner is not asyncio.get_running_loop() and owner.is_running():
        await asyncio.wrap_future(asyncio.run_coroutine_threadsafe(client.aclose(), owner))
    else:
        await client.aclose()


class GlobalSync(SyncFacade):
    def __init__(self, link):
        super().__init__(link)
        self._close_lock = threading.Lock()

    def close(self, timeout=2.0):
        # The SDK close suppresses HTTP errors and drops ownership after a timed
        # join. Retain the actual client/loop/thread until every close succeeds.
        if self._thread is threading.current_thread():
            raise RuntimeError('Close the global client from its owning module')
        with self._close_lock:
            loop, inner, thread = self._loop, self._inner, self._thread
            if loop is not None:
                async def drain():
                    if inner is not None and inner._owns_client:
                        await close_client(inner._client)
                    if self._link._owns_client:
                        await close_client(self._link._client)
                    await loop.shutdown_asyncgens()
                    await loop.shutdown_default_executor()
                asyncio.run_coroutine_threadsafe(drain(), loop).result()
                loop.call_soon_threadsafe(loop.stop)
            elif self._link._owns_client:
                asyncio.run(close_client(self._link._client))
            if thread is not None:
                thread.join()
            if loop is not None:
                loop.close()
            self._loop = self._thread = self._inner = None

    def _twin(self):
        with self._start_lock:
            if self._inner is None:
                parent = self._link
                self._inner = GlobalLink(parent.config, client=None if parent._owns_client else parent._client)
                self._inner._now, self._inner._sleep = parent._now, parent._sleep
            return self._inner


class GlobalLink(Link):
    def __init__(self, config, client=None):
        super().__init__(config, client=OwnedAsyncClient(trust_env=False) if client is None else client)
        self._owns_client = client is None
        self.sync = GlobalSync(self)
        self._selection = ContextVar('daguerre_call_selection', default=None)

    async def aclose(self):
        # Allow the async parent's owning loop to run while the facade joins.
        await asyncio.to_thread(self.sync.close)

    def global_selection(self):
        pin = _job.get()
        if pin is None:
            return descriptor(self.config)
        with pin.lock:
            if pin.choice is None:
                pin.choice = descriptor(self.config)
            return pin.choice

    async def resolve(self, capability, task=None):
        if capability not in ('llm','vision'):
            return await super().resolve(capability, task)
        try:
            choice = await asyncio.to_thread(self.global_selection)
            if capability == 'vision' and choice.get('vision') is not True:
                raise RuntimeError('El modelo global seleccionado no declara visión.')
            self._selection.set(choice)
            return Resolution(capability,'global',choice['url'],choice['model'],'openai','resolved',
                'Modelo global exacto de Faustus; sin fallback ni carga local.',
                {'endpoint_id':choice['endpoint_id'],'connection_revision':choice['connection_revision']})
        except Exception:
            return Resolution(capability,None,None,None,None,'unavailable',
                'El servicio global no está disponible o su selección no es válida.',{})

    async def _post_chat(self, provider, url, body, level):
        choice = self._selection.get()
        if choice is None or url != choice['url']:
            raise BackendError('global',409,'La llamada no coincide con el modelo global fijado.')
        response = await super()._post_json(provider, url, payload(body,choice),
            timeout=timeout_for(120,level), headers=choice['headers'])
        try:
            finish=response.json()['choices'][0]['finish_reason']
        except (ValueError,KeyError,IndexError,TypeError) as error:
            raise BackendError('global',502,'La respuesta global no tiene una finalización válida.') from error
        if finish != 'stop':
            raise BackendError('global',502,'El modelo global no completó la respuesta.')
        return response
