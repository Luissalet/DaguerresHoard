from __future__ import annotations

import shutil
from pathlib import Path
import time

from tests.conftest import make_image


def _wait_job(library, job_id, timeout=10.0):
    start = time.time()
    while time.time() - start < timeout:
        job = library.jobs.get(job_id)
        if job and job["status"] in ("done", "error"):
            return job
        time.sleep(0.02)
    raise TimeoutError(f"job {job_id} did not finish in time: {library.jobs.get(job_id)}")


def _index_sync(library, root_path):
    root = library.add_root(str(root_path))
    job_id = library.start_scan(root["id"])
    job = _wait_job(library, job_id)
    assert job["status"] == "done", job
    return root


def test_full_index_preserves_original_files(library, tmp_path):
    photos_dir = tmp_path / "photos"
    p1 = make_image(photos_dir / "a.jpg", color=(200, 20, 20))
    p2 = make_image(photos_dir / "b.jpg", color=(20, 200, 20))

    before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in (p1, p2)}
    _index_sync(library, photos_dir)

    # Exercise duplicates + album on top of the freshly indexed library.
    library.duplicates(kind="exact")
    photo_ids = [r["id"] for r in library.list_photos()["results"]]
    library.album("Test album", photo_ids)

    for p, (data, mtime) in before.items():
        assert p.read_bytes() == data
        assert p.stat().st_mtime_ns == mtime


def test_incremental_rescan_skips_unchanged_files(library, tmp_path, monkeypatch):
    photos_dir = tmp_path / "photos"
    make_image(photos_dir / "a.jpg")
    make_image(photos_dir / "b.jpg")
    root = _index_sync(library, photos_dir)

    calls = []
    from argus_hoard import hashing

    original = hashing.content_hash

    def spy(path):
        calls.append(path)
        return original(path)

    monkeypatch.setattr(hashing, "content_hash", spy)
    # library._index_one references the module-level function directly via
    # `from .hashing import content_hash`, so patch that binding too.
    import argus_hoard.library as library_mod

    monkeypatch.setattr(library_mod, "content_hash", spy)

    job_id = library.start_scan(root["id"])
    _wait_job(library, job_id)
    assert calls == []  # nothing changed since the first scan: no re-hashing


def test_add_root_strips_quotes_from_copy_as_path(library, tmp_path):
    # A7 (live report): Windows Explorer's "Copy as path" wraps the path in
    # quotes; the absolute path was rejected as "must be absolute".
    photos_dir = tmp_path / "Pictures"
    photos_dir.mkdir()
    import os

    root = library.add_root(f'"{photos_dir}"')
    assert root["path"] == os.path.abspath(photos_dir)

    root2 = library.add_root(f"'{photos_dir}'")
    assert root2["id"] == root["id"]  # same folder, quoted differently


def test_moved_file_keeps_its_id(library, tmp_path):
    photos_dir = tmp_path / "photos"
    p = make_image(photos_dir / "sub" / "a.jpg", color=(50, 60, 70))
    root = _index_sync(library, photos_dir)

    before = library.list_photos()["results"]
    assert len(before) == 1
    old_id = before[0]["id"]

    new_path = photos_dir / "sub" / "renamed.jpg"
    shutil.move(str(p), str(new_path))

    job_id = library.start_scan(root["id"])
    _wait_job(library, job_id)

    after = library.list_photos()["results"]
    assert len(after) == 1
    assert after[0]["id"] == old_id
    assert after[0]["path"] == str(new_path)


def test_place_filter_matches_neighbourhood_via_parent_region(library, tmp_path, monkeypatch):
    # B4 (live report): after the world-cities download, photos are
    # labelled with the nearest neighbourhood and `place="Lisbon"` stopped
    # finding them. `region` now carries the parent municipality.
    from argus_hoard.geocode import CityMatch

    photos_dir = tmp_path / "photos"
    make_image(photos_dir / "restelo.jpg", gps=(38.702, -9.205))
    make_image(photos_dir / "elsewhere.jpg", gps=(41.0, 2.0))

    def fake_lookup(lat, lon):
        if abs(lat - 38.702) < 0.01:
            return CityMatch(city="Restelo", region="Lisbon", country="Portugal", distance_km=6.0)
        return CityMatch(city="Barcelona", region=None, country="Spain", distance_km=0.0)

    monkeypatch.setattr(library.geocoder, "lookup", fake_lookup)
    _index_sync(library, photos_dir)

    matches = library.list_photos(filters={"place": "Lisbon"})["results"]
    assert len(matches) == 1
    assert matches[0]["place"] == "Restelo, Lisbon, Portugal"


def test_places_groups_neighbourhoods_under_their_city(library, tmp_path, monkeypatch):
    # Re-walk (UC8): with the world-cities data the Places page listed
    # Madrid's districts ("Ibiza", "Salamanca") and never "Madrid".
    from argus_hoard.geocode import CityMatch

    photos_dir = tmp_path / "photos"
    make_image(photos_dir / "retiro.jpg", gps=(40.413, -3.683))
    make_image(photos_dir / "ibiza.jpg", gps=(40.419, -3.674))
    make_image(photos_dir / "cadiz.jpg", gps=(36.527, -6.289))
    labels = {
        40.413: CityMatch(city="Retiro", region="Madrid", country="Spain", distance_km=0.1),
        40.419: CityMatch(city="Ibiza", region="Madrid", country="Spain", distance_km=0.1),
        36.527: CityMatch(city="Cadiz", region=None, country="Spain", distance_km=0.1),
    }
    monkeypatch.setattr(library.geocoder, "lookup", lambda lat, lon: labels[round(lat, 3)])
    _index_sync(library, photos_dir)

    spain = {c["city"]: c["count"] for c in library.places()["countries"]["Spain"]}
    assert spain == {"Madrid": 2, "Cadiz": 1}
    assert len(library.list_photos(filters={"place": "Madrid"})["results"]) == 2


def test_bundled_cities_have_no_admin_region_as_parent():
    # the bundled table's region column is an admin area (Ile-de-France),
    # not the city a place belongs to; Paris is its own city
    from argus_hoard.geocode import ReverseGeocoder

    paris = ReverseGeocoder(None).lookup(48.8566, 2.3522)
    assert (paris.city, paris.region, paris.country) == ("Paris", None, "France")


def test_places_suggests_world_cities_for_photos_the_bundled_table_cannot_place(library, tmp_path):
    # Re-walk (UC8): beyond the cutoff the bundled table returns nothing,
    # not even a country, so the Cadiz beach photos vanished from Places
    # without the hint to download the world-cities data.
    photos_dir = tmp_path / "photos"
    make_image(photos_dir / "cadiz.jpg", gps=(36.53, -6.30))
    make_image(photos_dir / "lisbon.jpg", gps=(38.7223, -9.1393))
    _index_sync(library, photos_dir)

    places = library.places()
    assert places["countries"] == {"Portugal": [places["countries"]["Portugal"][0]]}
    assert places["approximate_count"] == 1
    assert "world-cities" in places["note"]


def test_place_beyond_cutoff_keeps_country_without_a_wrong_city(library, tmp_path, monkeypatch):
    # A11 (live report): a photo far from any reference point got a
    # confidently wrong city; it should keep only the country.
    from argus_hoard.geocode import CityMatch

    photos_dir = tmp_path / "photos"
    make_image(photos_dir / "far.jpg", gps=(41.9, 12.5))
    monkeypatch.setattr(
        library.geocoder, "lookup",
        lambda lat, lon: CityMatch(city=None, region=None, country="Italy", distance_km=400.0, approximate=True),
    )
    _index_sync(library, photos_dir)

    photo = library.list_photos()["results"][0]
    assert photo["place"] == "Italy (approximate)"


def test_existing_library_is_relabelled_when_the_geocoder_changes(tmp_settings, tmp_path, monkeypatch):
    # B4/A11 (re-walk): the fixed labels only reached photos indexed after
    # the fix -- a rescan skips unchanged files -- so an upgraded library
    # kept "Restelo, Portugal" and a Cadiz beach kept "Lisbon, Portugal".
    from argus_hoard import db as dbmod
    from argus_hoard.embeddings import FakeEmbedder
    from argus_hoard.library import Library

    lib = Library(tmp_settings, embedder=FakeEmbedder())
    photos_dir = tmp_path / "photos"
    make_image(photos_dir / "lisbon.jpg", gps=(38.7223, -9.1393))
    make_image(photos_dir / "cadiz.jpg", gps=(36.53, -6.30))
    _index_sync(lib, photos_dir)
    # labels an older version wrote, and no stamp of the version that wrote them
    lib.conn.execute("UPDATE photos SET city = 'Lisbon', region = NULL, country = 'Portugal'")
    lib.conn.execute("DELETE FROM settings WHERE key = 'geocoder_version'")
    lib.conn.commit()
    lib.close()

    lib2 = Library(tmp_settings, embedder=FakeEmbedder())
    try:
        jobs = [j for j in lib2.jobs.list(limit=5) if j["kind"] == "regeocode"]
        assert jobs, "an upgraded library is relabelled once in the background"
        _wait_job(lib2, jobs[0]["id"])
        places = {Path(p["path"]).name: p["place"] for p in lib2.list_photos()["results"]}
        assert places["lisbon.jpg"] == "Lisbon, Portugal"
        assert places["cadiz.jpg"] is None  # too far from the bundled cities: no wrong label
        assert dbmod.get_setting(lib2.conn, "geocoder_version")
    finally:
        lib2.close()

    lib3 = Library(tmp_settings, embedder=FakeEmbedder())
    try:
        assert not [j for j in lib3.jobs.list(limit=5) if j["kind"] == "regeocode" and j["status"] == "running"]
        assert len([j for j in lib3.jobs.list(limit=10) if j["kind"] == "regeocode"]) == 1  # only once
    finally:
        lib3.close()


def test_search_and_similar_use_fake_embedder(library, tmp_path):
    photos_dir = tmp_path / "photos"
    make_image(photos_dir / "red.jpg", color=(220, 20, 20))
    make_image(photos_dir / "green.jpg", color=(20, 200, 20))
    _index_sync(library, photos_dir)

    result = library.search("a red square", limit=5, contact_sheet=True)
    assert result["count"] >= 1
    assert result["results"][0]["path"].endswith("red.jpg")
    assert result["contact_sheet_jpeg_base64"] is not None

    red_id = result["results"][0]["id"]
    similar = library.similar(photo_id=red_id, limit=5)
    assert all(r["id"] != red_id for r in similar["results"])


def test_search_default_has_no_contact_sheet(library, tmp_path):
    # B1 (live report): a text-only model's turn failed the moment a
    # default search/similar call carried an image.
    photos_dir = tmp_path / "photos"
    make_image(photos_dir / "red.jpg", color=(220, 20, 20))
    _index_sync(library, photos_dir)

    result = library.search("a red square", limit=5)
    assert result["contact_sheet_jpeg_base64"] is None
    similar = library.similar(photo_id=result["results"][0]["id"], limit=5)
    assert similar["contact_sheet_jpeg_base64"] is None


def test_search_returned_and_indexed_total_replace_misleading_count(library, tmp_path):
    # B2 (live report): `count` used to be "every ranked photo" (the whole
    # library), which read as "N photos match".
    photos_dir = tmp_path / "photos"
    for i in range(3):
        make_image(photos_dir / f"red{i}.jpg", color=(220, 20, 20))
    make_image(photos_dir / "green.jpg", color=(20, 200, 20))
    _index_sync(library, photos_dir)

    result = library.search("a red square", limit=2)
    assert result["indexed_total"] == 4  # every ranked photo, not a match count
    assert result["returned"] == 2  # what this call actually returned
    assert result["count"] == result["indexed_total"]  # kept as an alias, nothing removed
    assert result["has_more"] is True
    assert result["next_offset"] == 2
    page2 = library.search("a red square", limit=2, offset=2)
    assert page2["returned"] == 2
    assert page2["has_more"] is False
    seen_ids = {r["id"] for r in result["results"]} | {r["id"] for r in page2["results"]}
    assert len(seen_ids) == 4  # offset pages through the full ranked list, no overlap/gap


def test_search_limit_clamped_is_reported(library, tmp_path):
    # B5 (live report): limit=100 was silently clamped to 50.
    photos_dir = tmp_path / "photos"
    make_image(photos_dir / "red.jpg", color=(220, 20, 20))
    _index_sync(library, photos_dir)

    result = library.search("a red square", limit=100)
    assert result["limit_clamped"] is True
    assert result["requested_limit"] == 100
    assert result["returned"] <= 50


def test_search_query_optional_with_filters_is_chronological_listing(library, tmp_path):
    # B5 (live report): "every photo of the trip" forced the model to
    # invent a query like "photo" even when only filters were meant.
    photos_dir = tmp_path / "photos"
    make_image(photos_dir / "a.jpg", color=(220, 20, 20))
    make_image(photos_dir / "b.jpg", color=(20, 200, 20))
    _index_sync(library, photos_dir)

    result = library.search(None, filters={"orientation": "landscape"})
    assert result["mode"] == "filtered_listing"
    assert result["indexed_total"] == 2
    assert all("relevance" not in r for r in result["results"])

    from argus_hoard.library import ValidationError

    try:
        library.search("", filters=None)
        raise AssertionError("expected ValidationError")
    except ValidationError as exc:
        assert "query is required" in str(exc)


def test_search_empty_result_says_filters_excluded_everything(library, tmp_path):
    # A10 (live report): an empty result did not say whether the filters
    # excluded everything or nothing is indexed at all.
    photos_dir = tmp_path / "photos"
    make_image(photos_dir / "red.jpg", color=(220, 20, 20))
    _index_sync(library, photos_dir)

    result = library.search("a red square", filters={"camera": "no-such-camera-xyz"})
    assert result["indexed_total"] == 0
    assert "no photo passes these filters" in result["note"]


def test_album_name_matches_accent_insensitively(library, tmp_path):
    # A8 (live report): "Rodaje La Estación" and "Rodaje La Estacion" became two
    # albums because COLLATE NOCASE does not fold accents.
    photos_dir = tmp_path / "photos"
    p1 = make_image(photos_dir / "a.jpg")
    p2 = make_image(photos_dir / "b.jpg")
    _index_sync(library, photos_dir)
    ids = [r["id"] for r in library.list_photos()["results"]]

    first = library.album("Rodaje La Estación", ids[:1])
    assert first["created"] is True
    second = library.album("Rodaje La Estacion", ids[1:])
    assert second["created"] is False
    assert second["id"] == first["id"]
    assert second["name"] == "Rodaje La Estación"  # kept as first typed
    assert len(library.list_albums()) == 1


def test_search_fallback_relevance_never_strong(library, tmp_path):
    # B3 (live report): a query with no colour word scored like a
    # confident CLIP match with the colour-histogram fallback.
    photos_dir = tmp_path / "photos"
    make_image(photos_dir / "red.jpg", color=(220, 20, 20))
    make_image(photos_dir / "green.jpg", color=(20, 200, 20))
    _index_sync(library, photos_dir)

    colorless = library.search("a cat wearing a hat", limit=5)
    assert all(r["relevance"] == "weak" for r in colorless["results"])
    assert "arbitrary" in colorless["note"]

    colorful = library.search("a red square", limit=5)
    assert all(r["relevance"] in ("weak", "medium") for r in colorful["results"])
    assert "strong" not in {r["relevance"] for r in colorful["results"]}
