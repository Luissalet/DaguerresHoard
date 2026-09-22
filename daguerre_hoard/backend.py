"""Daguerre's own thin wrapper around the vendored Hoard Link.

Per CONTRACT_BACKEND.md: Daguerre never loads its own copy of a model server.
It vendors Hoard Link (``daguerre_hoard/hoard_link/``, never edited) and
composes it here with the one piece Hoard Link cannot know about: the
pre-existing, per-app Ollama URL/model fields in Daguerre's own ``settings``
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
import threading
from pathlib import Path
from typing import Any

from . import db as dbmod
from .captions import DEFAULT_BASE_URL, DEFAULT_MODEL
from .hoard_link import CapabilityConfig, Link, LinkConfig

# The two capabilities Daguerre actually uses. Kept in one place so the
# Settings "Models" panel and the override endpoint agree on what exists.
USED_CAPABILITIES = ("vision", "llm")

# A replaced Link is closed only after this grace period, so a call already
# in flight on it (a chat times out after 120 s, a wait_idle round after
# 30 s) finishes normally instead of hanging on a stopped event loop.
RETIRE_GRACE_S = 180.0


class Backend:
    """Everything `/api/backend` and Settings needs, in one place."""

    def __init__(self, data_dir: Path, conn: sqlite3.Connection):
        self.data_dir = Path(data_dir)
        self.config_path = self.data_dir / "backend.json"
        self._conn = conn
        self._retiring: dict[threading.Timer, Link] = {}
        self._retire_lock = threading.Lock()
        self.link = self._build_link()

    # -- config ----------------------------------------------------- #
    def _raw_config(self) -> dict[str, Any]:
        if self.config_path.is_file():
            try:
                raw = json.loads(self.config_path.read_text(encoding="utf-8-sig"))
            except (json.JSONDecodeError, OSError):
                return {}
            return raw if isinstance(raw, dict) else {}
        return {}

    def _build_link(self) -> Link:
        try:
            config = LinkConfig.load(self.config_path, env=os.environ, app="daguerre")
            self.config_error: str | None = None
        except ValueError as exc:
            # A hand-edited backend.json with a typo must not stop the app
            # from starting (everything but captions/translation works
            # without a model): fall back to env + probing and say why.
            config = LinkConfig.load(None, env=os.environ, app="daguerre")
            self.config_error = (
                f"backend.json is not usable ({exc}); using automatic detection "
                "until it is fixed."
            )
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
                    # A model saved in the Shared models panel is newer
                    # than the legacy field, so it wins.
                    model=vision_cc.model or model or DEFAULT_MODEL,
                    api="ollama",
                    provider="ollama",
                    allow_load=vision_cc.allow_load,
                )
        return Link(config)

    def reload(self) -> None:
        """Rebuild the Link from the current backend.json + settings table.

        Also serves as "clear the probe cache" (POST /api/backend/recheck):
        a fresh Link starts with an empty probe cache.

        Each Link's sync facade owns a thread, an event loop and an HTTP
        client, so the replaced one is closed after RETIRE_GRACE_S instead
        of leaking on every Re-check."""
        old, self.link = self.link, self._build_link()
        timer = threading.Timer(RETIRE_GRACE_S, self._retire, args=(old,))
        timer.daemon = True
        with self._retire_lock:
            self._retiring[timer] = old
        timer.start()

    def _retire(self, link: Link) -> None:
        with self._retire_lock:
            for timer, pending in list(self._retiring.items()):
                if pending is link:
                    del self._retiring[timer]
        _close_quietly(link)

    def close(self) -> None:
        """Shutdown: close the current Link and every one still retiring."""
        with self._retire_lock:
            pending = list(self._retiring.items())
            self._retiring.clear()
        for timer, link in pending:
            timer.cancel()
            _close_quietly(link)
        _close_quietly(self.link)

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

    def saved_overrides(self) -> dict[str, Any]:
        """What the Settings form shows as already saved -- never the token."""
        raw = self._raw_config()
        caps = raw.get("capabilities") or {}
        out: dict[str, Any] = {"faustus_url": (raw.get("faustus") or {}).get("url") or ""}
        for cap in USED_CAPABILITIES:
            entry = caps.get(cap) or {}
            out[cap] = {"url": entry.get("url") or "", "model": entry.get("model") or ""}
        return out

    # -- status ------------------------------------------------------ #
    def status(self) -> dict[str, Any]:
        caps = self.link.sync.status()  # {capability: Resolution.to_dict()}
        return {
            **caps,
            "token_set": self.token_set(),
            "overrides": self.saved_overrides(),
            "config_error": self.config_error,
            "used_capabilities": list(USED_CAPABILITIES),
        }


def _close_quietly(link: Link) -> None:
    try:
        link.sync.close()
    except Exception:  # noqa: BLE001 - best effort; never blocks a reload or shutdown
        pass
