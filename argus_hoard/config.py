"""Paths and runtime settings for Argus's Hoard.

Everything lives under a single data directory so the app never touches
files outside of it (except the read-only photo roots the user registers).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

SERVICE_SLUG = "argus-hoard"
DISPLAY_NAME = "Argus's Hoard"
DEFAULT_PORT = 8814

SUPPORTED_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff",
    ".heic", ".heif",
}
MIN_FILE_SIZE_BYTES = 8 * 1024

EMBED_DIM = 512


@dataclass
class Settings:
    data_dir: Path
    port: int = DEFAULT_PORT
    demo: bool = False

    @property
    def db_path(self) -> Path:
        return self.data_dir / "argus.db"

    @property
    def thumbs_dir(self) -> Path:
        return self.data_dir / "thumbs"

    @property
    def vectors_path(self) -> Path:
        return self.data_dir / "vectors.f32"

    @property
    def models_dir(self) -> Path:
        return self.data_dir / "models"

    @property
    def geodata_dir(self) -> Path:
        return self.data_dir / "geodata"

    @property
    def logs_dir(self) -> Path:
        return self.data_dir / "logs"

    def ensure_dirs(self) -> None:
        for d in (
            self.data_dir,
            self.thumbs_dir,
            self.models_dir,
            self.geodata_dir,
            self.logs_dir,
        ):
            d.mkdir(parents=True, exist_ok=True)


def resolve_data_dir(cli_value: str | None, demo: bool, repo_root: Path) -> Path:
    """Resolve the data directory: CLI flag > env var > default, with --demo override."""
    if demo:
        return repo_root / "data-demo"
    if cli_value:
        return Path(cli_value).expanduser().resolve()
    env_value = os.environ.get("ARGUS_DATA_DIR")
    if env_value:
        return Path(env_value).expanduser().resolve()
    return repo_root / "data"
