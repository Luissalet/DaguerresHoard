"""Install a complete owned wheel/dependency target without touching user profiles."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target',type=Path,required=True)
    parser.add_argument('--wheel',type=Path,required=True)
    parser.add_argument('--python',type=Path,required=True)
    parser.add_argument('--profile',type=Path)
    args=parser.parse_args()
    target=args.target.resolve();python=args.python.resolve();wheel=args.wheel.resolve()
    if target.exists() or target==ROOT or ROOT in target.parents:
        raise ValueError('Use a fresh installation target outside the checkout.')
    if ROOT in python.parents:raise ValueError('The installed runtime must use an external Python, not the development venv.')
    subprocess.run([str(python),'-m','pip','install','--disable-pip-version-check','--no-warn-script-location',
        '--target',str(target),'-r',str(ROOT/'requirements-lock.txt'),str(wheel)],check=True)
    config={'python':str(python),'profile':str(args.profile.resolve()) if args.profile else None}
    (target/'launch.json').write_text(json.dumps(config,indent=2)+'\n',encoding='utf-8')
    for name,function in (('daguerre-run','app_main'),('daguerre-mcp','mcp_main')):
        (target/(name+'.py')).write_text(
            'from pathlib import Path\nimport sys\nsys.path.insert(0,str(Path(__file__).resolve().parent))\n'
            'from daguerre_hoard.runtime_entry import '+function+'\n'+function+'()\n',encoding='utf-8')
        (target/(name+'.cmd')).write_text('@echo off\n"'+str(python)+'" -I "%~dp0'+name+'.py" %*\n',encoding='utf-8')
    print(json.dumps({'installed':str(target),'profile_untouched':config['profile'],'python':str(python)}))


if __name__=='__main__':main()
