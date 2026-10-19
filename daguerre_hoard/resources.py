"""Source and installed resources; installed mutable data stays outside the payload."""
import os
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
INSTALLED = (PACKAGE/'resources'/'installed.json').is_file()
ROOT = PACKAGE/'resources' if INSTALLED else PACKAGE.parent


def default_profile_root(source_root: Path) -> Path:
    if not INSTALLED:
        return source_root
    if os.name == 'nt':
        base=Path(os.environ.get('LOCALAPPDATA') or Path.home()/'AppData'/'Local')
    else:
        base=Path(os.environ.get('XDG_DATA_HOME') or Path.home()/'.local'/'share')
    return base/'DaguerresHoard'
