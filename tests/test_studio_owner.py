"""Cold owner and native synthetic store transfer; vector worker inert, no models."""
import asyncio
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import threading
import os

import httpx
import pytest
from PIL import Image
import numpy as np

from daguerre_hoard.studio import Studio,create_app


def test_cold_host_import_and_catalogue_do_not_create_data(tmp_path):
    program='''
from pathlib import Path
import sys,subprocess,asyncio
def forbidden(*a,**k):raise AssertionError('engine started')
subprocess.Popen=forbidden
from daguerre_hoard.studio import Studio
s=Studio(Path(sys.argv[1]))
assert len(s.tools)==97
assert 'daguerre_hoard.library' not in sys.modules
assert 'daguerre_hoard.studio_native.durer.durer_hoard.api' not in sys.modules
assert not s.root.exists()
assert all(m.phase=='off' for m in s.modules.values())
'''
    subprocess.run([sys.executable,'-c',program,str(tmp_path/'cold')],check=True)


@pytest.mark.asyncio
async def test_http_catalogue_and_off_project_reads_are_cold(tmp_path):
    app=create_app(tmp_path/'data',port=64838)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://127.0.0.1:64838') as client:
        assert len((await client.get('/api/agent/tools')).json()['tools'])==97
        assert not (tmp_path/'data').exists()
        project=(await client.post('/api/studio/projects',json={'title':'Native cut'})).json()
        assert (await client.get('/api/studio/projects/'+project['id'])).json()['objects']==[]
        assert all(not m['enabled'] for m in (await client.get('/api/studio/modules')).json()['modules'])
        off=await client.get('/vector/?project=retained')
        assert 'off.js' in off.text
        assert app.studio.modules['vector'].phase=='off'


@pytest.mark.asyncio
@pytest.mark.parametrize('native', [False, pytest.param(True, marks=pytest.mark.skipif(
    os.environ.get('DAGUERRE_VECTOR_NATIVE_TESTS') != '1', reason='explicit owned native CPU check'))])
async def test_photo_vector_photo_retains_originals_revisions_and_native_ids(tmp_path,monkeypatch,native):
    from daguerre_hoard.studio_native.durer.durer_hoard.sessions import sessions
    if native and os.environ.get('DAGUERRE_VECTOR_BUILD_QA') == '1':
        from daguerre_hoard.studio_native.durer.durer_hoard import native as engine
        from daguerre_hoard.studio_native.durer.durer_hoard import sessions as session_module
        target = engine.ROOT/'native/target/release'/('durer-cli.exe' if os.name=='nt' else 'durer-cli')
        assert target.is_file()
        # Explicit build QA of this checkout's completed CLI while GUI links.
        # Production executable resolution continues to use native/bin only.
        monkeypatch.setattr(engine,'executable',lambda:target)
        monkeypatch.setattr(session_module,'executable',lambda:target)
    def execute(project,path,actions,**kwargs):
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(b'synthetic-native-document')
        for action in actions:
            if action['name']=='export': Image.new('RGB',(64,64),(30,90,140)).save(action['arguments']['path'])
        return [{'name':action['name'],'is_error':False,'result':{}} for action in actions]
    if not native:
        monkeypatch.setattr(sessions,'execute',execute)
    studio=Studio(tmp_path/'data',port=64838)
    sources=tmp_path/'originals';sources.mkdir()
    original=sources/'photo.png'
    Image.fromarray(np.random.default_rng(8).integers(0,256,(128,128,3),dtype=np.uint8)).save(original)
    before=hashlib.sha256(original.read_bytes()).hexdigest()
    try:
        await studio.modules['photos'].set(True)
        await studio.modules['vector'].set(True)
        lib=studio.modules['photos'].app.state.library
        root=await asyncio.to_thread(lib.add_root,str(sources))
        job=await asyncio.to_thread(lib.start_scan,root['id'])
        async with asyncio.timeout(10):
            while (await asyncio.to_thread(lib.jobs.get,job))['status']=='running':await asyncio.sleep(.01)
        pid=(await asyncio.to_thread(lib.list_photos))['results'][0]['id']
        project=studio.projects.create('Retained visual project')
        moved=await studio.control('visual_project_photo',{'project':project['id'],'photo_id':pid})
        vector_id=moved['transfers'][-1]['receipt']['illustration']
        assert moved['objects'][0]['native_id']==pid
        exported=await studio.control('visual_project_export',{'project':project['id'],'illustration':vector_id})
        new_photo=exported['transfers'][-1]['receipt']['photo_id']
        assert (await asyncio.to_thread(lib.describe,new_photo))['id']==new_photo
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=studio),base_url='http://127.0.0.1:64838') as client:
            first=(await client.get('/api/studio/objects')).json()['photos']
            later=(await client.get('/api/studio/objects?offset=1')).json()['photos']
            assert len(first)==2 and len(later)==1
            assert later[0]['id']==first[1]['id']
        assert hashlib.sha256(original.read_bytes()).hexdigest()==before
        await studio.close()
        retained=studio.projects.get(project['id'])
        assert len(retained['transfers'])==2
        assert any(o['native_id']==vector_id for o in retained['objects'])
        await studio.modules['vector'].set(True)
        from daguerre_hoard.studio_native.durer.durer_hoard import store
        assert store.read(vector_id)['id']==vector_id
    finally:
        await studio.close()
