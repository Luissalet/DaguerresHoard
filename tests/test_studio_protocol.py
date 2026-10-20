"""Real stdio/HTTP owner with synthetic stores and an inert vector worker."""
import asyncio
import json
import os
from pathlib import Path
import sys
import threading
import time

import pytest
import uvicorn
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
from PIL import Image

from daguerre_hoard.studio import create_app,catalog

ROOT=Path(__file__).resolve().parents[1]


@pytest.mark.asyncio
async def test_stdio_cold_contract_and_native_store_roundtrip(tmp_path,monkeypatch):
    from daguerre_hoard import global_model
    from daguerre_hoard.studio_native.durer.durer_hoard.sessions import sessions
    def no_model(*a,**k): raise AssertionError('QA must not query a model service')
    monkeypatch.setattr(global_model,'descriptor',no_model)
    monkeypatch.setenv('HOARD_EVENTS','0')
    def worker(project,path,actions,**kwargs):
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(b'synthetic native editor document')
        for action in actions:
            if action['name']=='export': Image.new('RGB',(64,64),(120,60,20)).save(action['arguments']['path'])
        return [{'name':a['name'],'is_error':False,'result':{}} for a in actions]
    native = os.environ.get('DAGUERRE_VECTOR_NATIVE_TESTS') == '1'
    if not native:
        monkeypatch.setattr(sessions,'execute',worker)
    data=tmp_path/'data'
    app=create_app(data,port=64846,demo=True)
    server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=64846,log_level='warning'))
    thread=threading.Thread(target=server.run,name='daguerre-qa930-http')
    thread.start()
    try:
        async with asyncio.timeout(10):
            while not server.started: await asyncio.sleep(.02)
        env={**os.environ,'DAGUERRE_URL':'http://127.0.0.1:64846','DAGUERRE_TOKEN_FILE':str(data/'mcp-token'),
            'DAGUERRE_DATA_DIR':str(data),'DAGUERRE_TOKEN':'','HOARD_EVENTS':'0'}
        params=StdioServerParameters(command=sys.executable,args=[str(ROOT/'daguerre_hoard/mcp_server.py')],env=env,cwd=str(ROOT))
        async with stdio_client(params) as (read,write),ClientSession(read,write) as session:
            await session.initialize()
            tools=await session.list_tools()
            assert len(tools.tools)==96
            by_name={t.name:t for t in tools.tools}
            for group in catalog().values():
                for item in group: assert by_name[item['name']].inputSchema==item['inputSchema']
            async def call(name,args):
                result=await session.call_tool(name,args)
                assert not result.isError,result.content
                return json.loads(result.content[0].text)
            assert all(not m['enabled'] for m in (await call('visual_modules',{}))['modules'])
            assert not (data/'daguerre.db').exists() and not (data/'vector').exists()
            project=await call('visual_project_create',{'title':'Synthetic shared project'})
            await call('visual_module_set',{'module':'vector','enabled':True})
            missing=await session.call_tool('illustration_inspect',{'project_id':'missing'})
            assert missing.isError
            native=await call('illustration_create',{'title':'Owned vector'})
            vector_id=native['illustration']['id']
            await call('visual_module_set',{'module':'vector','enabled':False})
            assert (await call('visual_projects',{'project':project['id']}))['objects']==[]
            await call('visual_module_set',{'module':'vector','enabled':True})
            retained=await call('illustration_inspect',{'project_id':vector_id})
            assert retained['illustration']['id']==vector_id
            if native:
                await call('visual_module_set',{'module':'photos','enabled':True})
                await call('visual_demo_prepare',{})
                lib=app.studio.modules['photos'].app.state.library
                async with asyncio.timeout(20):
                    while await asyncio.to_thread(lib.jobs.running): await asyncio.sleep(.02)
                photo=(await asyncio.to_thread(lib.list_photos))['results'][0]
                moved=await call('visual_project_photo',{'project':project['id'],'photo_id':photo['id']})
                illustration=moved['transfers'][-1]['receipt']['illustration']
                exported=await call('visual_project_export',{'project':project['id'],'illustration':illustration})
                receipt=exported['transfers'][-1]['receipt']
                assert (await asyncio.to_thread(lib.describe,receipt['photo_id']))['id']==receipt['photo_id']
                await call('visual_module_set',{'module':'photos','enabled':False})
                import httpx
                async with httpx.AsyncClient() as client:
                    response=await client.get(f"http://127.0.0.1:64846/api/studio/artifacts/{project['id']}/{receipt['sha256']}",headers={'Range':'bytes=0-7'})
                    assert response.status_code==206 and response.content==b'\x89PNG\r\n\x1a\n'
            await call('visual_module_set',{'module':'vector','enabled':False})
    finally:
        server.should_exit=True
        await asyncio.to_thread(thread.join,10)
        assert not thread.is_alive()
    assert all(m.phase=='off' and not m.requests for m in app.studio.modules.values())
