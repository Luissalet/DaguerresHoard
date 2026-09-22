"""Argus's own thin wrapper around the vendored Hoard Link.

Per CONTRACT_BACKEND.md: Argus never loads its own copy of a model server.
It vendors Hoard Link (``argus_hoard/hoard_link/``, never edited) and
composes it here with the one piece Hoard Link cannot know about: the
pre-existing, per-app Ollama URL/model fields in Argus's own ``settings``
table (Settings -> "Ollama model"), which predate Hoard Link. Those fields
become the explicit override for the ``vision`` capability -- but only
once the owner has actually saved one (a row exists in ``settings``), so a
fresh install still benefits from Faustus/loopback resolution instead of
being pinned to the built-in Ollama default forever.

This module never touches ``hoard_link/*``; it only builds a ``Link`` from
a ``LinkConfig`` and persists ``data/backend.json``.
"""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from . import db as dbmod
from .captions import DEFAULT_BASE_URL, DEFAULT_MODEL
from .hoard_link import CapabilityConfig, Link, LinkConfig

# The two capabilities Argus actually uses. Kept in one place so the
# Settings "Models" panel and the override endpoint agree on what exists.
USED_CAPABILITIES = ("vision", "llm")


class Backend:
    """Everything `/api/backend` and Settings needs, in one place."""

    def __init__(self, data_dir: Path, conn: sqlite3.Connection):
        self.data_dir = Path(data_dir)
        self.config_path = self.data_dir / "backend.json"
        self._conn = conn
        self.link = self._build_link()

    # -- config ----------------------------------------------------- #
    def _raw_config(self) -> dict[str, Any]:
        if self.config_path.is_file():
            try:
                return json.loads(self.config_path.read_text(encoding="utf-8-sig"))
            except (json.JSONDecodeError, OSError):
                return {}
        return {}

    def _build_link(self) -> Link:
        config = LinkConfig.load(self.config_path, env=os.environ, app="argus")
        vision_cc = config.capability("vision")
        if not vision_cc.explicit:
            # Only a *saved* legacy setting counts as an explicit override
            # (default=None distinguishes "the owner set this" from "no
            # row yet"); an untouched fresh install lets Hoard Link probe
            # Faustus and loopback servers for a vision model instead of
            # being pinned to the built-in Ollama address forever.
            base_url = dbmod.get_setting(self._conn, "ollama_base_url", None)
            model = dbmod.get_setting(self._conn, "ollama_model", None)
            if base_url:
                config.capabilities["vision"] = CapabilityConfig(
                    url=base_url,
                    model=model or DEFAULT_MODEL,
                    api="ollama",
                    provider="ollama",
                    allow_load=vision_cc.allow_load,
                )
        return Link(config)

    def reload(self) -> None:
        """Rebuild the Link from the current backend.json + settings table.

        Also serves as "clear the probe cache" (POST /api/backend/recheck):
        a fresh Link starts with an empty probe cache."""
        self.link = self._build_link()

    def set_overrides(
        self,
        faustus_url: str | None = None,
        faustus_token: str | None = None,
        capability_overrides: dict[str, tuple[str | None, str | None]] | None = None,
    ) -> None:
        """Persist manual overrides into data/backend.json. An empty string
        clears that field; ``None`` leaves it untouched. The token is only
        ever written here, never read back by the API."""
        raw = self._raw_config()
        if faustus_url is not None:
            section = raw.setdefault("faustus", {})
            if faustus_url.strip():
                section["url"] = faustus_url.strip()
            else:
                section.pop("url", None)
        if faustus_token is not None:
            section = raw.setdefault("faustus", {})
            if faustus_token.strip():
                section["token"] = faustus_token.strip()
            else:
                section.pop("token", None)
        for cap, (url, model) in (capability_overrides or {}).items():
            if url is None and model is None:
                continue
            entry = raw.setdefault("capabilities", {}).setdefault(cap, {})
            if url is not None:
                if url.strip():
                    entry["url"] = url.strip()
                else:
                    entry.pop("url", None)
            if model is not None:
                if model.strip():
                    entry["model"] = model.strip()
                else:
                    entry.pop("model", None)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(json.dumps(raw, indent=2), encoding="utf-8")
        self.reload()

    def token_set(self) -> bool:
        return bool((self._raw_config().get("faustus") or {}).get("token"))

    # -- status ------------------------------------------------------ #
    def status(self) -> dict[str, Any]:
        caps = self.link.sync.status()  # {capability: Resolution.to_dict()}
        return {**caps, "token_set": self.token_set(), "used_capabilities": list(USED_CAPABILITIES)}
