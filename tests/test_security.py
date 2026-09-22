"""Regression tests for the HTTP surface: static-file serving must stay
inside frontend/dist, ids in URL paths cannot address files outside the
thumbnail store, and errors use the flat {"error", "message"} shape."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from argus_hoard.api import create_app
from argus_hoard.embeddings import FakeEmbedder

PORT = 18842


@pytest.fixture()
def dist_client(tmp_path, monkeypatch):
    monkeypatch.setattr("argus_hoard.library.select_embedder", lambda settings: FakeEmbedder())
    dist = tmp_path / "site" / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>spa</title>", encoding="utf-8")
    (dist / "favicon.svg").write_text("<svg/>", encoding="utf-8")
    (tmp_path / "site" / "secret.txt").write_text("TOP-SECRET", encoding="utf-8")
    app = create_app(data_dir=tmp_path / "data", static_dir=dist, port=PORT)
    with TestClient(app, base_url=f"http://127.0.0.1:{PORT}") as c:
        yield c


@pytest.mark.parametrize(
    "raw_path",
    [
        "/%2e%2e/secret.txt",
        "/..%2Fsecret.txt",
        "/assets/%2e%2e/%2e%2e/secret.txt",
        "/%2e%2e/%2e%2e/%2e%2e/%2e%2e/%2e%2e/%2e%2e/%2e%2e/etc/passwd",
    ],
)
def test_spa_fallback_never_serves_files_outside_dist(dist_client, raw_path):
    resp = dist_client.get(raw_path)
    assert "TOP-SECRET" not in resp.text
    assert "root:" not in resp.text


def test_spa_serves_real_files_and_falls_back_to_index(dist_client):
    assert dist_client.get("/favicon.svg").text == "<svg/>"
    assert "spa" in dist_client.get("/timeline").text
    assert "spa" in dist_client.get("/").text


def test_unknown_api_route_is_json_404_not_the_spa(dist_client):
    resp = dist_client.get("/api/does-not-exist")
    assert resp.status_code == 404
    assert resp.json()["error"] == "not_found"


@pytest.mark.parametrize("bad_id", ["..", "..\\..\\x", "ab", "../x", "%2e%2e", "Z" * 32])
def test_photo_ids_in_paths_are_validated(dist_client, bad_id):
    resp = dist_client.get(f"/api/photos/{bad_id}/thumbnail")
    assert resp.status_code in (400, 404)
    assert resp.headers["content-type"].startswith("application/json")


def test_errors_are_flat_error_message_objects(dist_client):
    resp = dist_client.post("/api/agent/photos_describe", json={"photo_id": "0" * 32})
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"] == "not_found"
    assert "photo" in body["message"]


def test_validation_errors_are_flat_and_actionable(dist_client):
    resp = dist_client.post("/api/agent/photos_search", json={"limit": 5})
    assert resp.status_code == 400
    body = resp.json()
    assert body["error"] == "invalid_argument"
    assert "query" in body["message"]
    # and the rejected call is still visible in the audit log
    calls = dist_client.get("/api/agent-calls").json()
    assert calls and calls[0]["tool"] == "photos_search" and calls[0]["ok"] == 0


def test_unknown_search_filter_is_rejected_with_the_valid_names(dist_client):
    resp = dist_client.post(
        "/api/agent/photos_search", json={"query": "red", "filters": {"city": "Madrid"}}
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body["error"] == "invalid_argument"
    assert "place" in body["message"]


def test_guard_rejects_host_header_with_other_port(dist_client):
    resp = dist_client.get("/api/health", headers={"host": f"127.0.0.1:{PORT + 1}"})
    assert resp.status_code == 403


def test_guard_rejects_null_origin_write(dist_client):
    resp = dist_client.post("/api/albums", json={"name": "x"}, headers={"origin": "null"})
    assert resp.status_code == 403


def test_ui_search_is_not_logged_as_an_assistant_call(dist_client):
    resp = dist_client.post("/api/search", json={"query": "red"})
    assert resp.status_code == 200
    assert dist_client.get("/api/agent-calls").json() == []


def test_ollama_url_must_be_http(dist_client):
    resp = dist_client.post("/api/settings", json={"ollama_base_url": "file:///etc/passwd"})
    assert resp.status_code == 400
    assert resp.json()["error"] == "invalid_argument"
