"""CPU-only acceptance of an installed target, using isolated system Python."""
import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


async def exercise(target,profile,port,manifest):
    sys.path.insert(0,str(target))
    os.environ.update(DAGUERRE_DATA_DIR=str(profile),DAGUERRE_DEV='caller-preserved',HOARD_EVENTS='0',HOARD_AUTO_REGISTER='0')
    for name in ('DAGUERRE_URL','DAGUERRE_TOKEN','DAGUERRE_TOKEN_FILE'):os.environ.pop(name,None)
    profile.mkdir(parents=True,exist_ok=True)
    seeds={'.env':f'DAGUERRE_URL=http://127.0.0.1:{port}\nDAGUERRE_DEV=file-value\nDAGUERRE_QA_ENV=preserved\n',
        'mcp-token':'opaque-installed-qa-token-930-preserved-valid',
        'backend.json':json.dumps({'faustus':{'url':'http://127.0.0.1:1','token':'inert-family'},
            'capabilities':{'vision':{'url':'http://retired.invalid','model':'retained-legacy'}}})}
    for name,value in seeds.items():
        path=profile/name
        if path.exists():raise ValueError('Use a new synthetic profile; never overwrite an existing one.')
        path.write_text(value,encoding='utf-8')
    before={name:digest(profile/name) for name in seeds}
    from daguerre_hoard.runtime_entry import bootstrap
    bootstrap()
    assert os.environ['DAGUERRE_DEV']=='caller-preserved'
    assert os.environ['DAGUERRE_QA_ENV']=='preserved'
    from daguerre_hoard.resources import ROOT,INSTALLED
    from daguerre_hoard.config import resolve_data_dir
    assert INSTALLED and ROOT.is_relative_to(target)
    assert resolve_data_dir(str(profile),True,ROOT)==profile
    import httpx
    import uvicorn
    from mcp import ClientSession,StdioServerParameters
    from mcp.client.stdio import stdio_client
    from daguerre_hoard.studio import create_app
    import daguerre_hoard.mcp_server as bridge
    assert 'daguerre_hoard.library' not in sys.modules
    assert 'onnxruntime' not in sys.modules and 'fastembed' not in sys.modules
    popen=subprocess.Popen
    def forbidden(*a,**k):raise AssertionError('cold discovery started a child')
    subprocess.Popen=forbidden
    try:
        app=create_app(profile,port=port,demo=True)
        assert len(app.studio.tools)==95 and all(m.phase=='off' for m in app.studio.modules.values())
        assert 'daguerre_hoard.library' not in sys.modules
    finally:subprocess.Popen=popen
    assert bridge._token_file()==profile/'mcp-token'
    fingerprinted=0
    for item in json.loads(manifest.read_text(encoding='utf-8'))['artifacts']:
        relative=Path(item['file'])
        payload=target/relative if relative.parts[0]=='daguerre_hoard' else ROOT/relative
        assert payload.is_file() and digest(payload)==item['sha256'],str(payload)
        fingerprinted+=1
    assert (target/'daguerre_hoard/hoard_link/_data/family-services.json').is_file()
    assert (target/'daguerre_hoard/hoard_link/LICENSE').is_file()
    assert (target/'daguerre_hoard/studio_native/durer/LICENSE').is_file()
    server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=port,log_level='warning'))
    thread=threading.Thread(target=server.run,name='installed-visual-qa')
    thread.start();surfaces={}
    try:
        async with asyncio.timeout(15):
            while not server.started:await asyncio.sleep(.02)
        base=f'http://127.0.0.1:{port}'
        async with httpx.AsyncClient(base_url=base,trust_env=False) as client:
            assert len((await client.get('/api/agent/tools')).json()['tools'])==95
            assert not (profile/'daguerre.db').exists() and not (profile/'vector').exists()
            params=StdioServerParameters(command=sys.executable,args=['-I',str(target/'daguerre-mcp.py')],
                env={**os.environ,'DAGUERRE_TOKEN_FILE':str(profile/'mcp-token')},cwd=str(target))
            async with stdio_client(params) as (read,write),ClientSession(read,write) as session:
                await session.initialize()
                assert len((await session.list_tools()).tools)==95
                async def call(name,args):
                    result=await session.call_tool(name,args)
                    assert not result.isError,result.content
                    return json.loads(result.content[0].text)
                assert all(not m['enabled'] for m in (await call('visual_modules',{}))['modules'])
                project=await call('visual_project_create',{'title':'Installed native transfer'})
                for name in ('photos','vector'):await call('visual_module_set',{'module':name,'enabled':True})
                assert (await client.post('/photos/api/agent/photos_library',json={})).status_code==401
                # The incorporated vector contract guards /call; its original
                # read-only per-tool route remains available to the native UI.
                assert (await client.post('/vector/api/agent/call',json={'name':'illustration_list','arguments':{}})).status_code==401
                assert (await client.get('/vector/openapi.json')).json()['info']['title']=='Daguerre · Vector'
                for path in ('/','/photos/','/vector/'):
                    response=await client.get(path)
                    assert response.status_code==200 and '<iframe' not in response.text
                    surfaces[path]={'sha256':hashlib.sha256(response.content).hexdigest(),'bytes':len(response.content),'resources':[]}
                    for resource in sorted(set(re.findall(r'(?:src|href)=["\']([^"\']+)["\']',response.text))):
                        if resource.startswith('/') and not resource.endswith('/'):
                            fetched=await client.get(resource)
                            assert fetched.status_code==200,(path,resource,fetched.status_code)
                            surfaces[path]['resources'].append({'url':resource,'bytes':len(fetched.content),'sha256':hashlib.sha256(fetched.content).hexdigest()})
                for name in ('cinzel','source-sans-3'):
                    font=await client.get('/studio-assets/fonts/'+name+'-latin-400-normal.woff2')
                    assert font.status_code==200 and font.content[:4]==b'wOF2'
                    assert (await client.get('/studio-assets/fonts/'+name+'-LICENSE.txt')).status_code==200
                await call('visual_demo_prepare',{})
                async with asyncio.timeout(30):
                    while True:
                        library=await call('photos_library',{})
                        objects=(await client.get('/api/studio/objects')).json()
                        if objects['photos']:break
                        await asyncio.sleep(.05)
                # Wait for the actual photo indexing job, using its installed owner.
                lib=app.studio.modules['photos'].app.state.library
                async with asyncio.timeout(30):
                    while await asyncio.to_thread(lib.jobs.running):await asyncio.sleep(.02)
                original=(await client.get('/api/studio/objects')).json()['photos'][0]
                moved=await call('visual_project_photo',{'project':project['id'],'photo_id':original['id']})
                illustration=moved['transfers'][-1]['receipt']['illustration']
                exported=await call('visual_project_export',{'project':project['id'],'illustration':illustration})
                receipt=exported['transfers'][-1]['receipt']
                assert (await call('photos_describe',{'photo_id':receipt['photo_id']}))['id']==receipt['photo_id']
                for name in ('photos','vector'):await call('visual_module_set',{'module':name,'enabled':False})
                retained=await call('visual_projects',{'project':project['id']})
                assert len(retained['transfers'])==2
                result=await client.get('/api/studio/artifacts/'+project['id']+'/'+receipt['sha256'],headers={'Range':'bytes=0-7'})
                assert result.status_code==206 and result.content==b'\x89PNG\r\n\x1a\n'
                assert all(not m['enabled'] for m in (await call('visual_modules',{}))['modules'])
    finally:
        server.should_exit=True
        await asyncio.to_thread(thread.join,15)
        assert not thread.is_alive()
    assert all(m.phase=='off' and not m.requests for m in app.studio.modules.values())
    after={name:digest(profile/name) for name in seeds}
    assert before==after,{'before':before,'after':after}
    loaded={name:str(Path(module.__file__).resolve()) for name,module in sys.modules.copy().items()
        if name.startswith('daguerre_hoard') and getattr(module,'__file__',None)}
    assert loaded and all(Path(path).is_relative_to(target) for path in loaded.values())
    print(json.dumps({'result':'PASS','target':str(target),'catalogue':95,'initial_modules':'OFF/OFF',
        'artifact_fingerprints':fingerprinted,'profile_hashes_preserved':before,'surfaces':surfaces,
        'loaded_owned_modules':loaded,'native_transfer':'photo/vector/PNG/photoID, persisted and Range206 after both OFF',
        'limits':'No GUI, live model, real profile, old checkout, integration or deployment'},indent=2))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target',type=Path,required=True)
    parser.add_argument('--profile',type=Path,required=True)
    parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--port',type=int,default=64846)
    args=parser.parse_args()
    asyncio.run(exercise(args.target.resolve(),args.profile.resolve(),args.port,args.manifest.resolve()))


if __name__=='__main__':main()
