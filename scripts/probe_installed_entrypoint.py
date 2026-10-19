"""Actual installed CLI argument/bootstrap path with listener replaced by an assertion."""
import argparse
import json
import os
from pathlib import Path
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--target', type=Path, required=True)
parser.add_argument('--profile', type=Path, required=True)
args = parser.parse_args()
target, profile = args.target.resolve(), args.profile.resolve()
assert not profile.exists()
profile.mkdir(parents=True)
(profile/'.env').write_text('DAGUERRE_QA_CLI=explicit-profile\nDAGUERRE_DEV=file-value\n', encoding='utf-8')
os.environ.update(DAGUERRE_DATA_DIR=str(profile/'wrong-environment-profile'), DAGUERRE_DEV='caller-preserved')
os.environ.pop('DAGUERRE_QA_CLI', None)
sys.path.insert(0, str(target))
import uvicorn
from daguerre_hoard.runtime_entry import app_main
seen = []
def checked_run(app, **kwargs):
    assert app.studio.root == profile
    assert all(m.phase == 'off' for m in app.studio.modules.values())
    assert os.environ['DAGUERRE_QA_CLI'] == 'explicit-profile'
    assert os.environ['DAGUERRE_DEV'] == 'caller-preserved'
    assert 'daguerre_hoard.library' not in sys.modules
    seen.append(True)
uvicorn.run = checked_run
sys.argv = ['daguerre-hoard', '--data-dir', str(profile), '--no-browser']
app_main()
assert seen == [True] and not (profile/'wrong-environment-profile').exists()
print(json.dumps({'result': 'PASS', 'target': str(target), 'CLI_profile_precedence': True,
    'profile_env_loaded': True, 'caller_dev_preserved': True, 'actual_listener_started': False}))
