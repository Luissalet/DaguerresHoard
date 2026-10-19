"""The complete native contract is data, not an engine startup."""
import subprocess
import sys


def test_complete_vector_discovery_creates_no_runtime_or_child(tmp_path):
    program = '''
import asyncio, os, subprocess, sys
from pathlib import Path
os.environ['DURER_DATA_DIR'] = sys.argv[1]
def unexpected(*a, **k): raise AssertionError('discovery started a child')
subprocess.Popen = unexpected
from daguerre_hoard.studio_native.durer.durer_hoard.native import catalog
from daguerre_hoard.studio_native.durer.durer_hoard.mcp_server import list_tools
c = catalog()
assert len(c['tools']) == 25 and len(c['commands']) == 659
assert len(asyncio.run(list_tools())) == 57
assert not Path(sys.argv[1]).exists()
'''
    subprocess.run([sys.executable, '-c', program, str(tmp_path/'cold-vector')], check=True)
