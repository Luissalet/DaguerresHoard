"""Installed CSS delivery and cold catalogue; root owns visual CUA."""
import asyncio
import hashlib
import json
from pathlib import Path
import subprocess
import sys

target = Path(sys.argv[1]).resolve()
profile = Path(sys.argv[2]).resolve()
assert not profile.exists()
sys.path.insert(0, str(target))
import httpx
from daguerre_hoard.studio import create_app
def forbidden(*args, **kwargs):
    raise AssertionError('Cold CSS check started a child')
subprocess.Popen = forbidden

async def main():
    app = create_app(profile)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url='http://127.0.0.1') as client:
        css = await client.get('/studio-assets/studio.css')
        assert css.status_code == 200
        assert css.content == (target/'daguerre_hoard/studio_ui/studio.css').read_bytes()
        assert 'body:has(#inputForm)' in css.text and 'color-scheme: dark' in css.text
        assert len((await client.get('/api/agent/tools')).json()['tools']) == 95
    assert all(m.phase == 'off' for m in app.studio.modules.values())
    assert not profile.exists() and 'daguerre_hoard.library' not in sys.modules
    assert 'onnxruntime' not in sys.modules and 'fastembed' not in sys.modules
    for name, module in sys.modules.copy().items():
        if name.startswith('daguerre_hoard') and getattr(module, '__file__', None):
            assert Path(module.__file__).resolve().is_relative_to(target)
    print(json.dumps({'result':'PASS','target':str(target),'catalogue':95,'modules':'OFF/OFF',
        'CSS_bytes':len(css.content),'CSS_sha256':hashlib.sha256(css.content).hexdigest(),
        'profile_created':False,'visual_CUA':'pending root'}))
asyncio.run(main())
