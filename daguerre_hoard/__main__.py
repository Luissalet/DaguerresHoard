"""Entry point: `python -m daguerre_hoard [--port P] [--data-dir D] [--demo] [--no-browser]`."""
from __future__ import annotations

import argparse
import logging
import logging.handlers
import threading
import webbrowser
from pathlib import Path

import uvicorn

from .studio import create_app
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
    from .runtime_entry import bootstrap
    parser = argparse.ArgumentParser(prog="daguerre_hoard")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--data-dir", type=str, default=None)
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    bootstrap(args.data_dir)

    data_dir = resolve_data_dir(args.data_dir, args.demo, REPO_ROOT)
    data_dir.mkdir(parents=True, exist_ok=True)
    _setup_logging(data_dir / "logs")

    app = create_app(data_dir,port=args.port,demo=args.demo)

    if not args.no_browser:
        url = f"http://127.0.0.1:{args.port}/"
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()

    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
