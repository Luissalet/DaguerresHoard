"""Installed entrypoints preserve the external profile and caller environment."""
import json
import os
from pathlib import Path
from .resources import INSTALLED, PACKAGE, default_profile_root


def bootstrap(profile=None):
    if not INSTALLED:return
    config=PACKAGE.parent/'launch.json'
    saved=json.loads(config.read_text(encoding='utf-8')) if config.is_file() else {}
    if saved.get('profile'):
        os.environ.setdefault('DAGUERRE_DATA_DIR',saved['profile'])
    profile=Path(profile or os.environ.get('DAGUERRE_DATA_DIR') or default_profile_root(PACKAGE.parent)/'data')
    if (profile/'.env').is_file():
        from dotenv import load_dotenv
        load_dotenv(profile/'.env',override=False)


def app_main():
    from .__main__ import main
    main()


def mcp_main():
    bootstrap()
    from .mcp_server import main
    main()
