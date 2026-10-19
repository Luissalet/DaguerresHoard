"""Explicit headless checks of this checkout's owned build, never a live app."""
import asyncio
import hashlib
import json
import os
from pathlib import Path

import pytest

from daguerre_hoard.studio_native.durer.durer_hoard import native, sessions as session_module, store
from daguerre_hoard.studio_native.durer.durer_hoard.config import Settings, configure_owner

pytestmark = pytest.mark.skipif(os.environ.get('DAGUERRE_VECTOR_NATIVE_TESTS')!='1',
    reason='explicit owned native CPU check')


@pytest.fixture
def owned(tmp_path,monkeypatch):
    configure_owner(Settings(tmp_path/'data',None,None))
    if os.environ.get('DAGUERRE_VECTOR_BUILD_QA')=='1':
        target=native.ROOT/'native/target/release'/('durer-cli.exe' if os.name=='nt' else 'durer-cli')
        assert target.is_file()
        monkeypatch.setattr(native,'executable',lambda:target)
        monkeypatch.setattr(session_module,'executable',lambda:target)
    yield
    session_module.sessions.close()
    configure_owner(None)


def test_fresh_native_catalogue_matches_frozen_full_schemas(owned):
    actual=asyncio.run(native.discover_catalog_async())
    frozen=native.catalog()
    for field in ('tools','commands','resources','resource_templates','prompts'):
        assert actual[field]==frozen[field],field
    assert len(actual['tools'])==25 and len(actual['commands'])==659


def test_historical_native_copy_edit_undo_redo_and_three_exports(owned):
    # Historical preservation workflow adapted from incorporated public tests.
    from daguerre_hoard.studio_native.durer.durer_hoard.history import execute
    source=native.ROOT/'tests/fixtures/historical.vectorcraft'
    item=store.create('Historical CPU document')
    root=store.project_root(item['id']);legacy=root/'project.vectorcraft'
    legacy.write_bytes(source.read_bytes());before_hash=hashlib.sha256(legacy.read_bytes()).hexdigest()
    path=root/'project.durer'
    sessions=session_module.sessions
    assert not any(r['is_error'] for r in sessions.execute(item['id'],path,[]))
    before=path.read_bytes()
    result=execute(item['id'],path,[{'name':'draw_shape','arguments':{
        'shape':'ellipse','x':12,'y':23,'width':45,'height':56,'fill':'#114488'}}])
    assert not any(r['is_error'] for r in result)
    after=path.read_bytes();assert after!=before
    sessions.close()
    assert not any(r['is_error'] for r in execute(item['id'],path,[{'name':'undo','arguments':{}}]))
    assert path.read_bytes()==before
    sessions.close()
    assert not any(r['is_error'] for r in execute(item['id'],path,[{'name':'redo','arguments':{}}]))
    assert path.read_bytes()==after
    for fmt in ('svg','png','pdf'):
        target=root/'exports'/('cpu.'+fmt)
        result=sessions.execute(item['id'],path,[{'name':'export','arguments':{'format':fmt,'path':str(target)}}])
        assert not any(r['is_error'] for r in result)
        assert target.is_file() and target.stat().st_size>100
    assert hashlib.sha256(legacy.read_bytes()).hexdigest()==before_hash
    assert json.loads(path.read_bytes())['format']=='durer'
