"""argus_hoard.backend.Backend: the legacy-Ollama-as-vision-override
mapping, config persistence (token never read back), and reload/recheck."""
from __future__ import annotations

import json

import httpx

from argus_hoard.backend import Backend
from argus_hoard.config import Settings
from argus_hoard.db import ThreadLocalConnections, set_setting
from argus_hoard.hoard_link import LinkConfig


def _conn(tmp_path):
    settings = Settings(data_dir=tmp_path / "data")
    settings.ensure_dirs()
    return settings, ThreadLocalConnections(settings.db_path).get()


def test_fresh_install_has_no_explicit_vision_override(tmp_path):
    """No row in `settings` yet: Hoard Link is left free to probe Faustus
    and loopback servers instead of being pinned to the built-in default."""
    settings, conn = _conn(tmp_path)
    backend = Backend(settings.data_dir, conn)
    assert backend.link.config.capability("vision").explicit is False


def test_saved_ollama_settings_become_the_explicit_vision_override(tmp_path):
    settings, conn = _conn(tmp_path)
    set_setting(conn, "ollama_base_url", "http://127.0.0.1:22222")
    set_setting(conn, "ollama_model", "custom-vl")
    backend = Backend(settings.data_dir, conn)
    cc = backend.link.config.capability("vision")
    assert cc.explicit is True
    assert cc.url == "http://127.0.0.1:22222"
    assert cc.model == "custom-vl"
    assert cc.api == "ollama"


def test_backend_json_vision_override_wins_over_legacy_settings(tmp_path):
    settings, conn = _conn(tmp_path)
    set_setting(conn, "ollama_base_url", "http://127.0.0.1:22222")
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    (settings.data_dir / "backend.json").write_text(
        json.dumps({"capabilities": {"vision": {"url": "http://127.0.0.1:9999", "model": "explicit-vl"}}}),
        encoding="utf-8",
    )
    backend = Backend(settings.data_dir, conn)
    cc = backend.link.config.capability("vision")
    assert cc.url == "http://127.0.0.1:9999"
    assert cc.model == "explicit-vl"


def test_set_overrides_persists_and_never_leaks_the_token(tmp_path):
    settings, conn = _conn(tmp_path)
    backend = Backend(settings.data_dir, conn)
    assert backend.token_set() is False
    backend.set_overrides(
        faustus_url="http://127.0.0.1:7000",
        faustus_token="ody_secret",
        capability_overrides={"llm": ("http://127.0.0.1:8081", "qwen3")},
    )
    try:
        assert backend.token_set() is True
        raw = json.loads((settings.data_dir / "backend.json").read_text(encoding="utf-8"))
        assert raw["faustus"]["token"] == "ody_secret"  # on disk only
        status = backend.status()
        assert "ody_secret" not in json.dumps(status)  # never surfaced through status()
        assert status["token_set"] is True
        assert status["llm"]["url"] == "http://127.0.0.1:8081"
    finally:
        backend.link.sync.close()


def test_set_overrides_empty_string_clears_a_field(tmp_path):
    settings, conn = _conn(tmp_path)
    backend = Backend(settings.data_dir, conn)
    backend.set_overrides(faustus_token="ody_secret")
    assert backend.token_set() is True
    backend.set_overrides(faustus_token="")
    assert backend.token_set() is False


def test_reload_rebuilds_the_link_from_current_state(tmp_path):
    settings, conn = _conn(tmp_path)
    backend = Backend(settings.data_dir, conn)
    before = backend.link
    set_setting(conn, "ollama_base_url", "http://127.0.0.1:22222")
    backend.reload()
    assert backend.link is not before
    assert backend.link.config.capability("vision").url == "http://127.0.0.1:22222"


def test_status_shape_includes_every_capability_and_used_capabilities(tmp_path):
    settings, conn = _conn(tmp_path)
    backend = Backend(settings.data_dir, conn)
    try:
        status = backend.status()
        for cap in ("llm", "vision", "embeddings", "tts", "stt", "image", "video", "music"):
            assert cap in status
            assert "reason" in status[cap]
        assert status["used_capabilities"] == ["vision", "llm"]
    finally:
        backend.link.sync.close()
