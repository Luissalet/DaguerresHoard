from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from argus_hoard.api import create_app
from argus_hoard.embeddings import FakeEmbedder
from tests.conftest import make_image

PORT = 18841


@pytest.fixture()
def client(tmp_path, monkeypatch):
    # Force the fake embedder so tests never try to download CLIP.
    monkeypatch.setattr("argus_hoard.library.select_embedder", lambda settings: FakeEmbedder())
    app = create_app(data_dir=tmp_path / "data", static_dir=None, port=PORT)
    with TestClient(app, base_url=f"http://127.0.0.1:{PORT}") as c:
        yield c


def _wait_job(client, job_id, timeout=10.0):
    start = time.time()
    while time.time() - start < timeout:
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] in ("done", "error"):
            return job
        time.sleep(0.02)
    raise TimeoutError("job did not finish")


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["service"] == "argus-hoard"
    assert body["name"] == "Argus's Hoard"
    assert body["status"] == "ok"


def test_guard_rejects_bad_host(client):
    resp = client.get("/api/health", headers={"host": "evil.example.com"})
    assert resp.status_code == 403
    assert resp.json()["error"] == "forbidden_host"


def test_guard_rejects_cross_site_write(client):
    resp = client.post(
        "/api/albums",
        json={"name": "x", "photo_ids": []},
        headers={"sec-fetch-site": "cross-site"},
    )
    assert resp.status_code == 403
    assert resp.json()["error"] == "forbidden_origin"


def test_guard_rejects_cross_origin_write(client):
    resp = client.post(
        "/api/albums",
        json={"name": "x", "photo_ids": []},
        headers={"origin": "http://evil.example.com"},
    )
    assert resp.status_code == 403


def test_guard_allows_same_origin_write(client):
    resp = client.post(
        "/api/albums",
        json={"name": "x", "photo_ids": []},
        headers={"origin": f"http://127.0.0.1:{PORT}"},
    )
    assert resp.status_code == 200


def test_plain_get_navigation_always_works(client):
    # A plain GET from "any browser tab" (no Origin, arbitrary Sec-Fetch-Site)
    # must never be blocked -- only non-GET/HEAD/OPTIONS cross-origin writes.
    resp = client.get("/api/health", headers={"sec-fetch-site": "cross-site"})
    assert resp.status_code == 200


def test_add_root_rejects_relative_path(client):
    resp = client.post("/api/roots", json={"path": "relative/path"})
    assert resp.status_code == 400
    assert resp.json()["error"] == "invalid_argument"


def test_index_and_agent_search_flow(client, tmp_path):
    photos_dir = tmp_path / "srcphotos"
    make_image(photos_dir / "red.jpg", color=(220, 30, 30))
    make_image(photos_dir / "green.jpg", color=(30, 200, 30))

    root_resp = client.post("/api/roots", json={"path": str(photos_dir)})
    assert root_resp.status_code == 200
    root_id = root_resp.json()["id"]

    scan_resp = client.post("/api/scan", json={"root_id": root_id})
    job = _wait_job(client, scan_resp.json()["job_id"])
    assert job["status"] == "done"

    lib_resp = client.get("/api/library")
    assert lib_resp.json()["photo_count"] == 2

    search_resp = client.post(
        "/api/agent/photos_search",
        json={"query": "a red square", "limit": 5, "contact_sheet": True},
    )
    assert search_resp.status_code == 200
    body = search_resp.json()
    assert body["count"] >= 1
    assert body["results"][0]["path"].endswith("red.jpg")
    assert body["contact_sheet_jpeg_base64"]

    photo_id = body["results"][0]["id"]
    describe_resp = client.post("/api/agent/photos_describe", json={"photo_id": photo_id, "caption": False})
    assert describe_resp.status_code == 200
    assert describe_resp.json()["id"] == photo_id

    thumb_resp = client.get(f"/api/photos/{photo_id}/thumbnail")
    assert thumb_resp.status_code == 200
    assert thumb_resp.headers["content-type"] == "image/webp"

    album_resp = client.post("/api/agent/photos_album", json={"name": "Reds", "photo_ids": [photo_id]})
    assert album_resp.status_code == 200
    assert album_resp.json()["photos"][0]["id"] == photo_id

    calls = client.get("/api/agent-calls").json()
    tools_called = {c["tool"] for c in calls}
    assert "photos_search" in tools_called
    assert "photos_describe" in tools_called
    assert "photos_album" in tools_called


def test_places_endpoint_groups_by_country_and_city(client, tmp_path, monkeypatch):
    from argus_hoard.geocode import CityMatch

    photos_dir = tmp_path / "geophotos"
    make_image(photos_dir / "a.jpg")
    root_id = client.post("/api/roots", json={"path": str(photos_dir)}).json()["id"]

    app = client.app
    lib = app.state.library
    monkeypatch.setattr(lib.geocoder, "lookup", lambda lat, lon: CityMatch(city="Madrid", region=None, country="Spain", distance_km=0))
    from argus_hoard.metadata import PhotoMetadata

    monkeypatch.setattr(
        "argus_hoard.library.extract_metadata",
        lambda path: PhotoMetadata(
            width=10, height=10, taken_at="2020-01-01T00:00:00", date_source="exif", make=None, model=None,
            lens=None, f_number=None, exposure_time=None, iso=None, focal_length=None, orientation=1,
            gps_lat=40.4, gps_lon=-3.7,
        ),
    )
    job_id = client.post("/api/scan", json={"root_id": root_id}).json()["job_id"]
    _wait_job(client, job_id)

    places = client.get("/api/places").json()
    assert "Spain" in places["countries"]
    assert places["countries"]["Spain"][0]["city"] == "Madrid"


def test_agent_describe_not_found_returns_404(client):
    resp = client.post("/api/agent/photos_describe", json={"photo_id": "0" * 32})
    assert resp.status_code == 404
    assert resp.json()["error"] == "not_found"


def test_agent_add_folder_rejects_relative_path(client):
    resp = client.post("/api/agent/photos_add_folder", json={"path": "not/absolute"})
    assert resp.status_code == 400
    assert resp.json()["error"] == "invalid_argument"


def test_no_ui_page_when_frontend_not_built(tmp_path, monkeypatch):
    monkeypatch.setattr("argus_hoard.library.select_embedder", lambda settings: FakeEmbedder())
    app = create_app(data_dir=tmp_path / "data2", static_dir=None, port=PORT)
    with TestClient(app, base_url=f"http://127.0.0.1:{PORT}") as c:
        resp = c.get("/")
        assert resp.status_code == 200
        assert "npm run build" in resp.text
