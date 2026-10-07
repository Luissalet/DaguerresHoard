"""The per-tool routes /api/agent/<tool> need the same bearer token as POST /api/agent/call."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from daguerre_hoard.api import create_app
from daguerre_hoard.embeddings import FakeEmbedder
from tests.conftest import agent_headers

PORT = 18843


@pytest.fixture()
def app(tmp_path, monkeypatch):
    monkeypatch.setattr("daguerre_hoard.library.select_embedder", lambda settings: FakeEmbedder())
    return create_app(data_dir=tmp_path / "data", static_dir=None, port=PORT)


@pytest.fixture()
def anonymous(app):
    with TestClient(app, base_url=f"http://127.0.0.1:{PORT}") as c:
        yield c


def test_tool_routes_are_refused_without_the_token(anonymous):
    tools = [t["name"] for t in anonymous.get("/api/agent/tools").json()["tools"]]
    assert len(tools) == 17
    for name in tools:
        r = anonymous.post(f"/api/agent/{name}", json={})
        assert r.status_code == 401, name
        assert r.json()["error"] == "unauthorized"
    assert anonymous.post("/api/agent/photos_library", json={}, headers={"Authorization": "Bearer wrong"}).status_code == 401


def test_tool_routes_work_with_the_token(app, anonymous):
    r = anonymous.post("/api/agent/photos_library", json={}, headers=agent_headers(app))
    assert r.status_code == 200
    lowercase = {"Authorization": agent_headers(app)["Authorization"].replace("Bearer", "bearer")}
    assert anonymous.post("/api/agent/photos_library", json={}, headers=lowercase).status_code == 200


def test_a_tool_that_changes_state_does_not_run_without_the_token(anonymous, tmp_path):
    folder = tmp_path / "pics"
    folder.mkdir()
    r = anonymous.post("/api/agent/photos_add_folder", json={"path": str(folder)})
    assert r.status_code == 401
    assert anonymous.get("/api/roots").json() == []


def test_the_ui_routes_the_catalogue_and_health_stay_open(anonymous):
    assert anonymous.get("/api/agent/tools").status_code == 200
    assert anonymous.get("/api/roots").status_code == 200
    assert anonymous.get("/api/health").status_code == 200
    assert anonymous.get("/api/agent-calls").status_code == 200


def test_the_token_is_stable_across_starts(tmp_path, monkeypatch):
    monkeypatch.setattr("daguerre_hoard.library.select_embedder", lambda settings: FakeEmbedder())
    first = agent_headers(create_app(data_dir=tmp_path / "data", static_dir=None, port=PORT))
    second = agent_headers(create_app(data_dir=tmp_path / "data", static_dir=None, port=PORT))
    assert first == second
