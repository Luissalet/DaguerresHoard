"""Immutable complete captures, cold transport and failure publication."""
import asyncio
import base64
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import io
import json

import httpx
from PIL import Image
import pytest

from daguerre_hoard import figures
from daguerre_hoard.studio import create_app
from daguerre_hoard.studio_projects import Projects


def capture(state='open', size=(64, 40)):
    stream=io.BytesIO()
    Image.new('RGB',size,'#237c92').save(stream,format='PNG')
    return {'format':'vitruvius.figure/1','document_id':'123456abcdef','revision':3,'title':'Synthetic mechanism',
            'state_id':state,'content':{'diagram':{'type':'isometric','nodes':[]},
                'mechanism':{'parts':[{'id':'base','description':'Complete notes.\n'*3000}],
                             'states':[{'id':'open'},{'id':'closed'}]}},
            'origin':{'editor_url':'http://127.0.0.1:5191/design/#/diagrams?document=123456abcdef'},
            'future_optional':{'keep':['á',{'value':7.5}]},
            'preview':{'mime':'image/png','data':base64.b64encode(stream.getvalue()).decode('ascii')}}


def test_complete_source_identity_history_and_concurrent_dedup(tmp_path):
    projects=Projects(tmp_path/'data')
    project=projects.create('Synthetic figures')['id']
    original=capture();before=deepcopy(original)
    with ThreadPoolExecutor(max_workers=4) as pool:
        imported=list(pool.map(lambda _:projects.import_figure(project,original),range(4)))
    first=imported[0]
    assert all(item['id']==first['id'] for item in imported)
    assert original==before and first['snapshot']==original
    second=projects.import_figure(project,capture('closed'))
    assert second['id']!=first['id'] and second['snapshot']['preview']==first['snapshot']['preview']
    assert len(projects.get(project)['objects'])==2
    reopened=Projects(projects.root).figure(project,first['id'])
    assert reopened['snapshot']==original
    _,retained,path=projects.figure_source(project,first['id'])
    assert retained==original and path.read_bytes()==base64.b64decode(original['preview']['data'])
    assert len(list((projects.root/'studio-artifacts').rglob('*.vfigure')))==2


@pytest.mark.parametrize('change',[
    lambda f:f.update(format='other/1'),
    lambda f:f.update(document_id='../other'),
    lambda f:f.update(revision=True),
    lambda f:f.update(revision=0),
    lambda f:f.update(content={}),
    lambda f:f.update(state_id='missing'),
    lambda f:f['content']['diagram'].update(type='flowchart'),
    lambda f:f.update(page_id='missing'),
    lambda f:f.update(origin={'editor_url':'javascript:alert(1)'}),
    lambda f:f.update(origin={'editor_url':'https://user:secret@example.com'}),
    lambda f:f['preview'].update(mime='image/jpeg'),
    lambda f:f['preview'].update(data='invalid base64'),
    lambda f:f['preview'].update(data=base64.b64encode(b'not PNG').decode()),
])
def test_invalid_figure_never_changes_project_or_retained_files(tmp_path,change):
    projects=Projects(tmp_path/'data');project=projects.create('Atomic')['id']
    projects.import_figure(project,capture())
    before=projects.get(project)
    files={str(p.relative_to(projects.root)):p.read_bytes() for p in (projects.root/'studio-artifacts').rglob('*') if p.is_file()}
    invalid=capture('closed');change(invalid)
    with pytest.raises(ValueError): projects.import_figure(project,invalid)
    assert projects.get(project)==before
    assert files=={str(p.relative_to(projects.root)):p.read_bytes() for p in (projects.root/'studio-artifacts').rglob('*') if p.is_file()}


def test_failed_file_publication_rolls_back_only_new_capture(tmp_path,monkeypatch):
    from daguerre_hoard.hoard_link import atomic
    projects=Projects(tmp_path/'data');project=projects.create('Atomic files')['id']
    original=projects.import_figure(project,capture())
    before=projects.get(project)
    real=atomic.write_bytes_atomic
    def fail_source(path,data):
        if path.suffix=='.vfigure': raise OSError('Synthetic disk failure')
        return real(path,data)
    monkeypatch.setattr(atomic,'write_bytes_atomic',fail_source)
    with pytest.raises(OSError,match='Synthetic disk failure'):projects.import_figure(project,capture('closed'))
    assert projects.get(project)==before
    assert len(list((projects.root/'studio-artifacts').rglob('*.png')))==1
    assert projects.figure(project,original['id'])['snapshot']==capture()


def test_page_selection_keeps_other_pages_and_legacy_optional_absence():
    source=capture();del source['state_id'];source['page_id']='two'
    source['content']['view']={'pages':[{'id':'one'},{'id':'two'}]}
    retained,png,size=figures.validate(source)
    assert retained==source and size==(64,40) and png==base64.b64decode(source['preview']['data'])
    del source['page_id'];del source['origin']
    assert figures.validate(source)[0]==source


@pytest.mark.asyncio
async def test_api_import_get_and_both_downloads_work_off_without_engine_factory(tmp_path):
    async def forbidden(*_):raise AssertionError('Native engine started')
    app=create_app(tmp_path/'data',port=64841,factories={'photos':forbidden,'vector':forbidden})
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://127.0.0.1:64841') as client:
        assert len((await client.get('/api/agent/tools')).json()['tools'])==97
        assert not app.studio.root.exists()
        project=(await client.post('/api/studio/projects',json={'title':'Synthetic import'})).json()['id']
        result=await client.post(f'/api/studio/projects/{project}/figure',json={'action':'import','figure':capture()})
        assert result.status_code==200,result.text
        item=result.json()
        assert (await client.get(item['png_url'])).content==base64.b64decode(capture()['preview']['data'])
        assert (await client.get(item['source_url'])).json()==capture()
        read=await client.post(f'/api/studio/projects/{project}/figure',json={'action':'get','object_id':item['id']})
        assert read.json()['figure']==capture()
        for action in ('vector','layers'):
            response=await client.post(f'/api/studio/projects/{project}/figure',json={'action':action,'object_id':item['id']})
            assert response.status_code==409
        assert all(m.phase=='off' for m in app.studio.modules.values())
        assert app.studio.projects.get(project)['transfers']==[]
        assert (await client.get(item['source_url'])).json()==capture()
    await app.studio.close()


@pytest.mark.asyncio
async def test_failed_native_copy_keeps_source_without_completed_transfer(tmp_path, monkeypatch):
    from daguerre_hoard.studio import Studio
    from daguerre_hoard.studio_native.durer.durer_hoard import store
    from daguerre_hoard.studio_native.durer.durer_hoard.sessions import sessions
    studio = Studio(tmp_path / 'data')
    project = studio.projects.create('Failed native copy')['id']
    item = studio.projects.import_figure(project, capture())
    before = studio.projects.get(project)
    native = tmp_path / 'native'
    native.mkdir()
    monkeypatch.setattr(store, 'create', lambda *a, **k: {'id':'partial-copy', 'source':{'path':str(k['source'])}})
    monkeypatch.setattr(store, 'project_root', lambda _: native)
    def failed(*args, **kwargs):
        (native / 'project.durer').write_bytes(b'partial document')
        raise TimeoutError('Synthetic timeout; inspect operation 123')
    monkeypatch.setattr(sessions, 'execute', failed)
    module = studio.modules['vector']
    module.phase = 'on'  # Inert owner: no engine is started by this failure test.
    try:
        with pytest.raises(ValueError, match='partial-copy.*Synthetic timeout'):
            await studio.control('visual_project_figure', {'action':'vector','project':project,'object_id':item['id']})
        assert studio.projects.get(project) == before
        assert (native / 'project.durer').read_bytes() == b'partial document'
        assert not module.requests
    finally:
        module.phase = 'off'
        await studio.close()


@pytest.mark.asyncio
async def test_figure_native_owner_waits_for_cancelled_write(tmp_path, monkeypatch):
    import asyncio
    import threading
    from daguerre_hoard.studio import Studio
    studio = Studio(tmp_path / 'data')
    entered, release = threading.Event(), threading.Event()
    completed = []
    def write(_):
        entered.set()
        assert release.wait(5)
        completed.append(True)
    monkeypatch.setattr(studio, 'figure_layers', write)
    module = studio.modules['photos']
    module.phase = 'on'
    task = asyncio.create_task(studio.control('visual_project_figure', {'action':'layers','project':'synthetic'}))
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done() and len(module.requests) == 1
        release.set()
        with pytest.raises(asyncio.CancelledError): await task
        assert completed == [True] and not module.requests
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)
        module.phase = 'off'
        await studio.close()


def test_small_capture_is_retained_but_layers_bounds_apply_before_native_write(tmp_path):
    from types import SimpleNamespace
    from daguerre_hoard.library import Library
    value = capture()
    stream = io.BytesIO()
    Image.new('RGB', (8, 8)).save(stream, format='PNG')
    value['preview']['data'] = base64.b64encode(stream.getvalue()).decode()
    projects = Projects(tmp_path / 'data')
    project = projects.create('Small source')['id']
    item = projects.import_figure(project, value)
    owner = SimpleNamespace(settings=SimpleNamespace(data_dir=tmp_path / 'photo-data'))
    with pytest.raises(ValueError, match='between 16 and 8192'):
        Library.figure_to_layers(owner, value)
    assert not owner.settings.data_dir.exists()
    assert projects.figure(project, item['id'])['snapshot'] == value


def test_partial_layers_failure_reports_native_copy_for_recovery(tmp_path, monkeypatch):
    import re
    from daguerre_hoard.craft_engines import CraftEngines, CraftEngineError
    engines = CraftEngines(tmp_path / 'data', restore_editors=False)
    def fail(_engine, calls):
        target = engines.workspace / next(call['arguments']['path'] for call in calls if call['tool']=='doc_save')
        target.write_bytes(b'partial native document')
        raise TimeoutError('Synthetic native timeout')
    monkeypatch.setattr(engines, 'call', fail)
    with pytest.raises(CraftEngineError, match='Synthetic native timeout') as raised:
        engines.create_layered_document('Synthetic', 32, 32, '#000000')
    identifier = re.search(r'Layers copy ([0-9a-f]{32})', str(raised.value)).group(1)
    assert (engines.workspace / 'exports' / (identifier+'.dglayers')).read_bytes()==b'partial native document'
