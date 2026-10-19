"""Explicit build-time metadata capture; isolated runtime and no documents/models."""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from daguerre_hoard.craft_engines import CraftEngines,ENGINE_NAMES,OWN_NAMES


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--metadata-root',type=Path,required=True)
    args=parser.parse_args()
    output=ROOT/'native'/'catalogs';output.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='daguerre-craft-metadata-') as raw:
        engines=CraftEngines(Path(raw),restore_editors=False)
        paths={name:args.metadata_root/('daguerre-'+OWN_NAMES[name]+'-cli.exe') for name in OWN_NAMES}
        engines.executable=lambda name:paths[ENGINE_NAMES[name]]
        for name,path in paths.items():
            data=asyncio.run(engines._request(name,[{'tool':'__list_tools__'}]))[0]
            data['metadata_binary_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
            (output/(OWN_NAMES[name]+'.json')).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            print(OWN_NAMES[name],len(data['tools']),flush=True)


if __name__=='__main__':main()
