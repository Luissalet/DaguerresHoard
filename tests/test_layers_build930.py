"""Run existing native document assertions as soon as this owned CLI completes."""
import os
from pathlib import Path
import pytest
from daguerre_hoard.craft_engines import CraftEngines
from tests import test_craft_engines as original

pytestmark = pytest.mark.skipif(os.environ.get('DAGUERRE_LAYERS_BUILD_QA')!='1',
    reason='explicit headless check of this checkout build')


@pytest.mark.parametrize('scenario',[
    'test_real_photocraft_saves_editable_layers_and_png',
    'test_real_photocraft_opens_a_copy_as_background_and_keeps_editable_overlay',
])
def test_owned_layered_documents(tmp_path,monkeypatch,scenario):
    target=Path(__file__).resolve().parents[1]/'native/layers/target/release'/(
        'daguerre-layers-cli.exe' if os.name=='nt' else 'daguerre-layers-cli')
    assert target.is_file()
    engines=CraftEngines(tmp_path/'data',restore_editors=False)
    production=engines.executable
    monkeypatch.setattr(engines,'executable',lambda name:target if name in ('layers','photocraft') else production(name))
    monkeypatch.setattr(original,'_configured_engines',lambda _tmp:engines)
    try:
        getattr(original,scenario)(tmp_path)
    finally:
        engines.close()
