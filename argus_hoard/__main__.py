"""Entry point: `python -m argus_hoard [--port P] [--data-dir D] [--demo] [--no-browser]`."""
from __future__ import annotations

import argparse
import logging
import logging.handlers
import threading
import webbrowser
from pathlib import Path

import uvicorn

from .api import create_app
from .config import DEFAULT_PORT, resolve_data_dir

REPO_ROOT = Path(__file__).resolve().parents[1]


def _setup_logging(logs_dir: Path) -> None:
    logs_dir.mkdir(parents=True, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        logs_dir / "app.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)


def main() -> None:
    parser = argparse.ArgumentParser(prog="argus_hoard")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--data-dir", type=str, default=None)
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    data_dir = resolve_data_dir(args.data_dir, args.demo, REPO_ROOT)
    data_dir.mkdir(parents=True, exist_ok=True)
    _setup_logging(data_dir / "logs")

    static_dir = REPO_ROOT / "frontend" / "dist"
    app = create_app(data_dir=data_dir, static_dir=static_dir if static_dir.exists() else None, port=args.port)

    if args.demo:
        from .demo import generate_demo_photos

        photos_dir = data_dir / "photos"
        generate_demo_photos(photos_dir)
        lib = app.state.library
        if not lib.list_roots():
            root = lib.add_root(str(photos_dir), added_by="user")
            lib.start_scan(root["id"])

    if not args.no_browser:
        url = f"http://127.0.0.1:{args.port}/"
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
