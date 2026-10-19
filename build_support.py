"""Build-only resource assembly; never runs node, cargo, an app or an engine."""
import json
from pathlib import Path
import shutil
from setuptools.command.build_py import build_py
from wheel.bdist_wheel import bdist_wheel

ROOT=Path(__file__).resolve().parent


class StudioBuild(build_py):
    def run(self):
        required=['frontend/dist/index.html','app-icon.png','native/catalogs/layers.json','native/catalogs/develop.json']
        required += ['native/bin/'+name+'.exe' for name in ('daguerre-layers-cli','daguerre-layers','daguerre-develop-cli','daguerre-develop')]
        required += ['daguerre_hoard/studio_native/durer/native/bin/'+name+'.exe' for name in ('durer-cli','durer')]
        required += ['daguerre_hoard/studio_ui/fonts/'+name+'-latin-400-normal.woff2' for name in ('cinzel','source-sans-3')]
        missing=[name for name in required if not (ROOT/name).is_file()]
        if missing:raise RuntimeError('Build owned assets before packaging: '+', '.join(missing))
        super().run()
        target=Path(self.build_lib)/'daguerre_hoard'/'resources'
        for directory in ('frontend/dist','native/bin','native/catalogs'):
            for source in (ROOT/directory).rglob('*'):
                if source.is_file():
                    destination=target/source.relative_to(ROOT)
                    destination.parent.mkdir(parents=True,exist_ok=True)
                    shutil.copyfile(source,destination)
        for name in ('app-icon.png','LICENSE'):
            source=ROOT/name
            if source.is_file():
                target.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(source,target/name)
        (target/'installed.json').write_text(json.dumps({'owner':'daguerre','mutable_profile':'external','schema':1})+'\n',encoding='utf-8')


class StudioWheel(bdist_wheel):
    def finalize_options(self):
        super().finalize_options()
        self.root_is_pure=False

    def get_tag(self):
        _python,_abi,platform=super().get_tag()
        return 'py3','none',platform
