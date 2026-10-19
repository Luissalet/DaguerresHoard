"""Explicit metadata-only QA/build step; never used by application discovery."""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--metadata-executable', required=True, type=Path)
    args = parser.parse_args()
    executable = args.metadata_executable.resolve()
    from daguerre_hoard.studio_native.durer.durer_hoard import native
    from daguerre_hoard.studio_native.durer.durer_hoard.config import Settings
    with tempfile.TemporaryDirectory(prefix='daguerre-native-metadata-') as raw:
        native.executable = lambda: executable
        native.settings = lambda: Settings(Path(raw), None, None)
        data = asyncio.run(native.discover_catalog_async())
    data['executable'] = 'native/bin/durer-cli'
    data['cli']['executable'] = 'native/bin/durer-cli'
    data['metadata_binary_sha256'] = hashlib.sha256(executable.read_bytes()).hexdigest()
    output = native.ROOT / 'native-catalog.json'
    output.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n', encoding='utf-8')
    from daguerre_hoard.studio_native.durer.durer_hoard import mcp_server
    tools = [t.model_dump(exclude_none=True) for t in asyncio.run(mcp_server.list_tools())]
    (native.ROOT/'mcp-catalog.json').write_text(json.dumps(tools,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'native_tools':len(data['tools']),'commands':len(data['commands']),
        'mcp_tools':len(tools),'metadata_binary_sha256':data['metadata_binary_sha256']}))


if __name__ == '__main__':
    main()
