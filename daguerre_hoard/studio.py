"""Cold visual owner; native engines only exist after explicit module activation."""
from __future__ import annotations
import asyncio
from contextlib import AsyncExitStack
import hashlib
import json
from pathlib import Path
from urllib.parse import parse_qs

from .studio_lifecycle import Module
from .studio_projects import Projects
from .studio_response import NativeResponse

from .resources import ROOT
VECTOR = Path(__file__).with_name('studio_native')/'durer'


async def photos(root, port, demo, automatic):
    from .api import create_app
    return await asyncio.to_thread(create_app,root,ROOT/'frontend'/'dist',port,automatic=automatic,demo=demo)


async def vector(root, port, demo, automatic):
    from .studio_native.durer.durer_hoard.config import Settings
    from .studio_native.durer.durer_hoard.api import create_app
    return await asyncio.to_thread(create_app,Settings(root/'vector',None,None,port=port))


def tool(name, description, properties=None, required=(), read=False):
    return {'name':name,'description':description+'\nKeywords: photos, vector, project, fotos, vector, proyecto',
        'inputSchema':{'type':'object','properties':properties or {},'required':list(required)},
        'annotations':{'readOnlyHint':read,'destructiveHint':False,'openWorldHint':False}}


TOOLS = [
    tool('visual_modules','Read module state without starting engines.',read=True),
    tool('visual_module_set','Explicitly activate/stop one visual module.',{
        'module':{'type':'string','enum':['photos','vector']},'enabled':{'type':'boolean'},
        'automatic':{'type':'boolean','default':False}},['module','enabled']),
    tool('visual_projects','Read common projects/revisions while modules are OFF.',{'project':{'type':'string'}},read=True),
    tool('visual_project_create','Create a visual project.',{'title':{'type':'string'}},['title']),
    tool('visual_project_photo','Bring an original photo into a real editable vector project; retain original bytes and revisions.',
        {'project':{'type':'string'},'photo_id':{'type':'string'}},['project','photo_id']),
    tool('visual_project_export','Export a vector revision and index its PNG result in the native photo library.',
        {'project':{'type':'string'},'illustration':{'type':'string'}},['project','illustration']),
    tool('visual_demo_prepare','Explicitly generate and scan synthetic demo photos only in a --demo instance.'),
]


def catalog():
    photo = json.loads(Path(__file__).with_name('photo-catalog.json').read_text(encoding='utf-8'))
    native = json.loads((VECTOR/'mcp-catalog.json').read_text(encoding='utf-8'))
    return {'photos':photo,'vector':native,'host':TOOLS}


class Studio:
    def __init__(self,root,*,port=8814,demo=False,factories=None):
        self.root,self.port = Path(root).resolve(),port
        self.demo=demo
        self.catalogs = catalog()
        self.tools = {t['name']:group for group,tools in self.catalogs.items() for t in tools}
        if len(self.tools) != sum(map(len,self.catalogs.values())):
            raise ValueError('Visual native tool names collide.')
        self.modules = {name:Module(name,factory,self.root,port,demo)
            for name,factory in (factories or {'photos':photos,'vector':vector}).items()}
        self.projects = Projects(self.root)
        self.copilot=None

    def token(self):
        from .hoard_link.tokens import read_or_create_token
        return read_or_create_token(self.root/'mcp-token')

    async def close(self):
        from .cancellation import join_tasks
        tasks = [asyncio.create_task(m.set(False)) for m in self.modules.values()]
        results=await join_tasks(tasks)
        for result in results:
            if isinstance(result,BaseException): raise result

    async def __call__(self,scope,receive,send):
        if scope['type']=='lifespan':
            while True:
                event = await receive()
                if event['type']=='lifespan.startup':
                    await asyncio.to_thread(self.token)
                    await send({'type':'lifespan.startup.complete'})
                else:
                    await self.close()
                    await send({'type':'lifespan.shutdown.complete'})
                    return
        if scope['type']=='http':
            try:
                await self.http(scope,receive,send)
            except (ValueError,FileNotFoundError) as error:
                await self.json(send,{'error':'unavailable','message':str(error)},409)

    @staticmethod
    async def body(receive):
        parts=[]
        while True:
            message=await receive()
            if message['type']=='http.disconnect': raise asyncio.CancelledError
            parts.append(message.get('body',b''))
            if not message.get('more_body'): return json.loads(b''.join(parts) or b'{}')

    @staticmethod
    async def json(send,value,status=200):
        await send({'type':'http.response.start','status':status,'headers':[(b'content-type',b'application/json; charset=utf-8')]})
        await send({'type':'http.response.body','body':json.dumps(value,ensure_ascii=False).encode()})

    async def control(self,name,args):
        if name=='visual_modules': return {'modules':[m.status() for m in self.modules.values()]}
        if name=='visual_module_set':
            if args.get('module') not in self.modules or not isinstance(args.get('enabled'),bool) or not isinstance(args.get('automatic',False),bool):
                raise ValueError('Choose photos/vector and boolean enabled/automatic.')
            return await self.modules[args['module']].set(args['enabled'],args.get('automatic',False))
        if name=='visual_projects':
            return await asyncio.to_thread(self.projects.get,args['project']) if args.get('project') else await asyncio.to_thread(self.projects.list)
        if name=='visual_project_create': return await asyncio.to_thread(self.projects.create,args['title'])
        if name=='visual_demo_prepare':
            if not self.demo: raise ValueError('Synthetic demo preparation requires an isolated --demo instance.')
            def prepare():
                from .demo import generate_demo_photos
                folder=self.root/'photos'
                generate_demo_photos(folder)
                lib=self.modules['photos'].app.state.library
                root=lib.add_root(str(folder),added_by='user')
                return {'job':lib.start_scan(root['id'])}
            return await self.modules['photos'].work(prepare)
        if name in ('visual_project_photo','visual_project_export'):
            function=self.transfer_photo if name=='visual_project_photo' else self.export_photo
            async def run():
                async with AsyncExitStack() as stack:
                    await stack.enter_async_context(self.modules['photos'].use())
                    await stack.enter_async_context(self.modules['vector'].use())
                    return await asyncio.to_thread(function,args)
            task=asyncio.create_task(run())
            try: return await asyncio.shield(task)
            except asyncio.CancelledError:
                from .cancellation import join_tasks
                await join_tasks([task])
                raise
        raise ValueError('Unknown visual control.')

    def transfer_photo(self,args):
        from .studio_native.durer.durer_hoard import store,native
        from .studio_native.durer.durer_hoard.sessions import sessions
        from .hoard_link.atomic import write_bytes_atomic
        project=self.projects.get(args['project'])
        lib=self.modules['photos'].app.state.library
        photo=lib.describe(args['photo_id'])
        preview=lib.render_preview(photo['id'])
        sha=hashlib.sha256(preview).hexdigest()
        folder=self.root/'studio-artifacts'/project['id']/'sources'
        folder.mkdir(parents=True,exist_ok=True)
        source=folder/(sha+'.jpg')
        if not source.exists(): write_bytes_atomic(source,preview)
        item=store.create(project['title'],source=source)
        path=store.project_root(item['id'])/'project.durer'
        result=sessions.execute(item['id'],path,[{'name':'open_file','arguments':{'path':item['source']['path']}}])
        if native.failed_results(result) or not path.is_file():
            raise ValueError('The native editor did not save the imported project; inspect its native receipt before retrying.')
        original=Path(photo['path'])
        source_snapshot={'photo':photo,'original_sha256':hashlib.sha256(original.read_bytes()).hexdigest(),
            'derived_sha256':sha}
        one=self.projects.link(project['id'],'photos','photo',photo['id'],'/photos/?photo='+photo['id'],source_snapshot)
        two=self.projects.link(project['id'],'vector','illustration',item['id'],'/vector/?project='+item['id'],
            {'manifest':store.read(item['id']),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
        return self.projects.receipt(project['id'],one['id'],two['id'],
            {'kind':'photo_to_vector','sha256':sha,'file':str(source),'illustration':item['id'],'result':result})

    def export_photo(self,args):
        import time
        import uuid
        from .studio_native.durer.durer_hoard import store,native
        from .studio_native.durer.durer_hoard.sessions import sessions
        self.projects.get(args['project'])
        item=store.read(args['illustration'])
        path=store.project_root(item['id'])/'project.durer'
        folder=self.root/'studio-artifacts'/args['project']/'photo-results'
        folder.mkdir(parents=True,exist_ok=True)
        export=folder/(uuid.uuid4().hex+'.png')
        result=sessions.execute(item['id'],path,[{'name':'export','arguments':{'path':str(export),'format':'png'}}])
        if native.failed_results(result) or not export.is_file() or not export.stat().st_size:
            raise ValueError('The native export did not produce a PNG; inspect the vector state before retrying.')
        sha=hashlib.sha256(export.read_bytes()).hexdigest()
        lib=self.modules['photos'].app.state.library
        root=lib.add_root(str(folder),added_by='agent')
        job=lib.start_scan(root['id'])
        while lib.jobs.get(job)['status']=='running': time.sleep(.02)
        if lib.jobs.get(job)['status']!='done': raise ValueError('Photo indexing did not finish; the native export remains saved.')
        row=lib.conn.execute('SELECT id FROM photos WHERE path=?',(str(export),)).fetchone()
        if row is None: raise ValueError('The PNG is saved but not indexed as a photo; inspect the scan receipt.')
        source=self.projects.link(args['project'],'vector','illustration',item['id'],'/vector/?project='+item['id'],
            {'manifest':store.read(item['id']),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
        target=self.projects.link(args['project'],'photos','result',row['id'],'/photos/?photo='+row['id'],
            {'photo':lib.describe(row['id']),'sha256':sha})
        return self.projects.receipt(args['project'],source['id'],target['id'],
            {'kind':'vector_to_photo','sha256':sha,'file':str(export),'photo_id':row['id'],'result':result})

    async def native(self,module,path,scope,receive,send):
        # This dispatcher strips the owner prefix itself. Native middleware and
        # nested StaticFiles mounts must see an ordinary application scope;
        # response/runtime URL adapters add the public prefix exactly once.
        child=dict(scope,path=path,raw_path=path.encode(),root_path='')
        child['asgi']={**scope.get('asgi',{}),'spec_version':'2.3'}
        await self.modules[module].request(child,receive,NativeResponse(send,module,self.port))

    async def http(self,scope,receive,send):
        path,method=scope['path'],scope['method']
        if path.startswith('/api/copilot/'):
            if self.copilot is None:
                from .studio_ui.api import create_app
                self.copilot=create_app(self.root)
            return await self.copilot(scope,receive,send)
        if path=='/api/health':
            return await self.json(send,{'service':'daguerres-hoard','name':"Daguerre's Hoard",'status':'ok','demo':self.demo,
                'modules':[m.status() for m in self.modules.values()]})
        if path in ('/api/agent/tools','/api/studio/catalog'):
            return await self.json(send,{'app':'daguerre','tools':sum(self.catalogs.values(),[])})
        if path=='/api/studio/modules': return await self.json(send,await self.control('visual_modules',{}))
        if path=='/api/studio/demo' and method=='POST': return await self.json(send,await self.control('visual_demo_prepare',{}))
        if path=='/api/studio/objects':
            query=parse_qs(scope.get('query_string',b'').decode())
            offset=max(0,int(query.get('offset',['0'])[0]))
            result={'photos':[],'vector':[]}
            if self.modules['photos'].phase=='on':
                result['photos']=await self.modules['photos'].work(lambda:self.modules['photos'].app.state.library.list_photos(limit=50,offset=offset)['results'])
            if self.modules['vector'].phase=='on':
                def read():
                    from .studio_native.durer.durer_hoard.store import list_projects
                    return list_projects()
                result['vector']=await self.modules['vector'].work(read)
            return await self.json(send,result)
        if path.startswith('/api/studio/modules/') and method=='PUT':
            return await self.json(send,await self.control('visual_module_set',{'module':path.rsplit('/',1)[1],**await self.body(receive)}))
        if path=='/api/studio/projects':
            return await self.json(send,await self.control('visual_project_create',await self.body(receive)) if method=='POST' else await self.control('visual_projects',{}))
        if path.startswith('/api/studio/projects/'):
            parts=path.split('/')
            if len(parts)==6 and method=='POST' and parts[-1] in ('photo','export'):
                return await self.json(send,await self.control('visual_project_'+parts[-1],
                    {'project':parts[4],**await self.body(receive)}))
            return await self.json(send,await self.control('visual_projects',{'project':parts[4]}))
        if path.startswith('/api/studio/artifacts/') and method=='GET':
            parts=path.split('/')
            if len(parts)!=6: return await self.json(send,{'error':'not_found'},404)
            project=await asyncio.to_thread(self.projects.get,parts[4])
            receipt=next((t['receipt'] for t in project['transfers'] if t['receipt']['sha256']==parts[5]),None)
            if receipt is None: return await self.json(send,{'error':'not_found'},404)
            from starlette.responses import FileResponse
            return await FileResponse(receipt['file'])(scope,receive,send)
        if path.startswith('/api/agent/'):
            name=path.removeprefix('/api/agent/')
            body=await self.body(receive) if method=='POST' else {}
            if name=='call': name,args=body.get('name') or body.get('tool'),body.get('arguments') or {}
            else: args=body
            module=self.tools.get(name)
            if module in ('host','vector'):
                from .hoard_link.tokens import check_bearer
                headers=dict(scope.get('headers',[]))
                token_path=self.root/'mcp-token'
                token=token_path.read_text(encoding='utf-8').strip() if token_path.is_file() else ''
                if not check_bearer(headers.get(b'authorization',b'').decode(),token):
                    return await self.json(send,{'error':'unauthorized'},401)
                if module=='host': return await self.json(send,await self.control(name,args))
                def invoke():
                    from .studio_native.durer.durer_hoard.mcp_server import call_tool
                    return asyncio.run(call_tool(name,args,owned=True))
                result=await self.modules['vector'].work(invoke)
                return await self.json(send,result.model_dump(exclude_none=True))
            # Original photographic wrappers and accountability remain native.
            raw=json.dumps(body).encode()
            delivered=False
            async def replay():
                nonlocal delivered
                if not delivered:
                    delivered=True
                    return {'type':'http.request','body':raw}
                return await receive()
            return await self.native('photos',path,scope,replay,send)
        for module in self.modules:
            prefix='/'+module
            if path==prefix or path.startswith(prefix+'/'):
                if path in (prefix,prefix+'/') and self.modules[module].phase=='off':
                    from starlette.responses import HTMLResponse
                    html=f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Daguerre · {module}</title><link rel="stylesheet" href="/studio-assets/studio.css"><script src="/studio-assets/off.js" defer></script></head><body class="studio-home" data-module="{module}"><main><h1>{module.title()}</h1><p id="message">This module is OFF.</p><button id="activate">Activate</button> <a href="/">Projects / Proyectos</a><p id="error" role="alert"></p></main></body></html>'''
                    return await HTMLResponse(html)(scope,receive,send)
                return await self.native(module,path[len(prefix):] or '/',scope,receive,send)
        if path=='/':
            from starlette.responses import FileResponse
            return await FileResponse(Path(__file__).with_name('studio_ui')/'index.html')(scope,receive,send)
        if path.startswith('/studio-assets/'):
            name=path.removeprefix('/studio-assets/')
            font=Path(name)
            is_font=len(font.parts)==2 and font.parts[0]=='fonts' and font.suffix in ('.woff2','.txt')
            if name not in ('studio.js','studio.css','native.js','off.js','app-icon.png') and not is_font:
                return await self.json(send,{'error':'not_found'},404)
            from starlette.responses import FileResponse
            file=ROOT/'app-icon.png' if name=='app-icon.png' else Path(__file__).with_name('studio_ui')/name
            return await FileResponse(file)(scope,receive,send)
        return await self.native('photos',path,scope,receive,send)


def create_app(root,**kwargs):
    from .hoard_link.guard import GuardMiddleware,parse_allowed_hosts
    import os
    studio=Studio(root,**kwargs)
    from .compat_mcp import install
    app=GuardMiddleware(install(studio),port_getter=lambda:studio.port,strict_ports=True,
        allowed=parse_allowed_hosts(os.environ.get('DAGUERRE_ALLOWED_HOSTS','')))
    app.studio=studio
    return app
