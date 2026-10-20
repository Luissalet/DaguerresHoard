from pathlib import Path
import json

import pytest

from tests.faustus_manifest import check_repo, ManifestError

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_manifest_is_valid():
    data = check_repo(REPO_ROOT)
    assert data["id"] == "daguerre"
    assert data["mcp"]["command"] == "{PYTHON}"
    assert data["defaults"]["PYTHON"] == "{DAGUERRE_DIR}/.venv/Scripts/python.exe"
    assert data["mcp"]["args"] == ["-I", "-m", "daguerre_hoard.mcp_server"]


@pytest.mark.parametrize('args, reason', [(['-I','-m'], 'valid module name'),
    (['-m','../outside'], 'valid module name'), (['-m','missing.entry'], 'no source entry'),
    (['{DAGUERRE_DIR}/missing_server.py'], 'missing file: missing_server.py')])
def test_repo_check_rejects_missing_module_or_script(tmp_path, args, reason):
    data = json.loads((REPO_ROOT / 'faustus-plugin.json').read_text(encoding='utf-8'))
    data['mcp']['args'] = args
    data['provides'] = {}
    (tmp_path / 'faustus-plugin.json').write_text(json.dumps(data), encoding='utf-8')
    with pytest.raises(ManifestError, match=reason): check_repo(tmp_path)


def test_legacy_script_entry_still_valid(tmp_path):
    data = json.loads((REPO_ROOT / 'faustus-plugin.json').read_text(encoding='utf-8'))
    data['mcp']['args'] = ['{DAGUERRE_DIR}/server.py']
    data['provides'] = {}
    (tmp_path / 'server.py').write_text('# Synthetic source entry', encoding='utf-8')
    (tmp_path / 'faustus-plugin.json').write_text(json.dumps(data), encoding='utf-8')
    assert check_repo(tmp_path)['mcp']['args'] == data['mcp']['args']
