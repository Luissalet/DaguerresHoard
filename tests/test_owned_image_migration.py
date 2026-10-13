"""Real historical-format readback and one-way catalog/preferences migration."""
import hashlib,json,os,zipfile
from pathlib import Path
import pytest
from PIL import Image
from daguerre_hoard.craft_engines import CraftEngines


def _engines(tmp_path):
    if os.environ.get('DAGUERRE_NATIVE_TESTS')!='1':
        pytest.skip('enable real incorporated engine tests')
    engines=CraftEngines(tmp_path/'data')
    assert engines.executable('layers') and engines.executable('develop')
    return engines


def _state(result):
    assert not any(row['is_error'] for row in result['calls']),result
    return json.loads(result['calls'][-1]['content'][0]['text'])


def test_historical_layer_bundle_preserves_ids_pixels_and_original(tmp_path):
    engines=_engines(tmp_path)
    made=engines.create_layered_document('Historical source',96,64,'#285a82')
    path=Path(made['native_path']);own=path.read_bytes()
    assert '.dglayers'==path.suffix
    legacy=engines.workspace/'historical.pcraft'
    with zipfile.ZipFile(path) as reader,zipfile.ZipFile(legacy,'w',compression=zipfile.ZIP_STORED) as writer:
        for name in reader.namelist():
            data=reader.read(name)
            if name=='manifest.json':
                manifest=json.loads(data)
                assert 'daguerre' in manifest['generator']
                manifest['generator']='photocraft-format 0.2.0'
                data=json.dumps(manifest).encode()
            writer.writestr(name,data)
    before=legacy.read_bytes()
    imported=_state(engines.call('layers',[{'tool':'doc_open','arguments':{'path':'historical.pcraft'}},{'tool':'doc_inspect','arguments':{}}]))
    reread=_state(engines.call('layers',[{'tool':'doc_open','arguments':{'path':path.relative_to(engines.workspace).as_posix()}},{'tool':'doc_inspect','arguments':{}}]))
    assert imported['width']==reread['width']==96 and imported['height']==64
    assert imported['layers']==reread['layers']
    assert path.read_bytes()==own and legacy.read_bytes()==before


def test_historical_develop_catalog_is_copied_and_reopened_without_original_changes(tmp_path):
    engines=_engines(tmp_path)
    source=tmp_path/'source.png';Image.new('RGB',(64,48),(49,92,126)).save(source)
    original=source.read_bytes()
    engines.develop_photo(source,.7,'png')
    old=engines.runtime/'lightcraft-library'
    current=engines.runtime/'develop-library'
    assert current.resolve().is_relative_to(tmp_path.resolve())
    current.rename(old)
    snap=old/'catalog.snap';data=json.loads(snap.read_text(encoding='utf-8'))
    assert data['format']=='daguerre-develop-catalog'
    data['format']='lightcraft-catalog';snap.write_text(json.dumps(data),encoding='utf-8')
    hashes={p.relative_to(old).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in old.rglob('*') if p.is_file()}
    reopened=_state(engines.call('develop',[{'tool':'query_photos','arguments':{}},{'tool':'get_develop','arguments':{}}]))
    assert reopened['light']['exposure']==pytest.approx(.7)
    assert (current/'catalog.snap').is_file()
    assert source.read_bytes()==original
    assert hashes=={p.relative_to(old).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in old.rglob('*') if p.is_file()}


def test_historical_editor_preferences_are_copied_without_rewriting(tmp_path):
    engines=_engines(tmp_path)
    originals=[]
    for key,folder in [('photocraft','Photocraft'),('lightcraft','LightCraft')]:
        path=engines.runtime/key/'appdata'/folder/'preferences.json'
        path.parent.mkdir(parents=True);path.write_text('{"custom":"preserve me"}',encoding='utf-8')
        originals.append((path,path.read_bytes()))
    engines._server_params('layers');engines._server_params('develop')
    copies=[engines.runtime/'layers-config/preferences.json',engines.runtime/'lightcraft/appdata/Daguerre Develop/preferences.json']
    assert all(copy.read_bytes()==originals[i][1] for i,copy in enumerate(copies))
    assert all(path.read_bytes()==value for path,value in originals)
