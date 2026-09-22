"""HTTP surface added by the shared-backend retrofit: GET/PUT/POST
/api/backend*, the translate_search setting, and the UI's automatic query
translation on /api/search (never on /api/agent/photos_search)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from argus_hoard.api import create_app
from argus_hoard.embeddings import FakeEmbedder
from argus_hoard.hoard_link import ChatResult, Usage

PORT = 18842


@pytest.fixture()
def app_and_client(tmp_path, monkeypatch):
    monkeypatch.setattr("argus_hoard.library.select_embedder", lambda settings: FakeEmbedder())
    app = create_app(data_dir=tmp_path / "data", static_dir=None, port=PORT)
    with TestClient(app, base_url=f"http://127.0.0.1:{PORT}") as c:
        yield app, c


def test_get_backend_lists_every_capability_and_image_search(app_and_client):
    app, client = app_and_client
    resp = client.get("/api/backend")
    assert resp.status_code == 200
    body = resp.json()
    for cap in ("llm", "vision", "embeddings", "tts", "stt", "image", "video", "music"):
        assert cap in body
    assert body["image_search"]["active"] == "fake-colorhist-v1"
    assert body["image_search"]["semantic"] is False
    assert body["token_set"] is False


def test_put_backend_config_saves_overrides_and_never_returns_the_token(app_and_client, tmp_path):
    app, client = app_and_client
    resp = client.put(
        "/api/backend/config",
        json={
            "faustus_url": "http://127.0.0.1:7000",
            "faustus_token": "ody_super_secret",
            "vision_url": "http://127.0.0.1:11434",
            "vision_model": "qwen2.5vl:7b",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_set"] is True
    assert "ody_super_secret" not in resp.text
    assert body["vision"]["url"] == "http://127.0.0.1:11434"
    on_disk = (tmp_path / "data" / "backend.json").read_text(encoding="utf-8")
    assert "ody_super_secret" in on_disk  # persisted, just never served back


def test_put_backend_config_rejects_a_bad_url(app_and_client):
    app, client = app_and_client
    resp = client.put("/api/backend/config", json={"vision_url": "not-a-url"})
    assert resp.status_code == 400
    assert resp.json()["error"] == "invalid_argument"


def test_recheck_backend_rebuilds_the_link(app_and_client):
    app, client = app_and_client
    lib = app.state.library
    before = lib.backend.link
    resp = client.post("/api/backend/recheck")
    assert resp.status_code == 200
    assert lib.backend.link is not before


def test_ui_search_translates_a_non_english_query(app_and_client, monkeypatch):
    app, client = app_and_client
    lib = app.state.library

    def fake_chat(messages, **kwargs):
        assert kwargs.get("capability") == "llm"
        return ChatResult(text="dog on the beach", model="m", provider="p", usage=Usage(), elapsed_ms=1.0)

    monkeypatch.setattr(lib.backend.link.sync, "chat", fake_chat)
    resp = client.post("/api/search", json={"query": "un perro en la playa", "filters": {}, "limit": 5})
    assert resp.status_code == 200
    body = resp.json()
    assert body["translated_query"] == "dog on the beach"
    assert body["original_query"] == "un perro en la playa"
    assert body["query"] == "dog on the beach"


def test_ui_search_falls_back_silently_when_llm_unavailable(app_and_client, monkeypatch):
    app, client = app_and_client
    lib = app.state.library
    from argus_hoard.hoard_link import Unavailable

    def fake_chat(messages, **kwargs):
        raise Unavailable("llm", ["no server available"])

    monkeypatch.setattr(lib.backend.link.sync, "chat", fake_chat)
    resp = client.post("/api/search", json={"query": "un perro en la playa", "filters": {}, "limit": 5})
    assert resp.status_code == 200
    body = resp.json()
    assert "translated_query" not in body
    assert body["query"] == "un perro en la playa"  # searched with the original text
    assert "translate_error" in body


def test_agent_search_never_translates(app_and_client, monkeypatch):
    """The MCP tool description tells the agent to translate itself; the
    agent-facing endpoint must call search() directly, never search_translated()."""
    app, client = app_and_client
    lib = app.state.library
    called = {"chat": False}

    def fake_chat(*a, **k):
        called["chat"] = True
        raise AssertionError("agent calls must not trigger translation")

    monkeypatch.setattr(lib.backend.link.sync, "chat", fake_chat)
    resp = client.post("/api/agent/photos_search", json={"query": "un perro en la playa", "filters": {}, "limit": 5})
    assert resp.status_code == 200
    assert called["chat"] is False


def test_translate_search_can_be_disabled(app_and_client, monkeypatch):
    app, client = app_and_client
    lib = app.state.library
    called = {"chat": False}

    def fake_chat(*a, **k):
        called["chat"] = True
        raise AssertionError("translation must be off")

    monkeypatch.setattr(lib.backend.link.sync, "chat", fake_chat)
    assert client.post("/api/settings", json={"translate_search": False}).status_code == 200
    resp = client.post("/api/search", json={"query": "un perro en la playa", "filters": {}, "limit": 5})
    assert resp.status_code == 200
    assert called["chat"] is False
    assert resp.json()["query"] == "un perro en la playa"


def test_settings_get_reports_translate_search_default_on(app_and_client):
    app, client = app_and_client
    assert client.get("/api/settings").json()["translate_search"] is True
