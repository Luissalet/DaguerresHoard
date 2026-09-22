from argus_hoard.geocode import NEARBY_KM, ReverseGeocoder


def test_reverse_geocode_on_bundled_fixture():
    geocoder = ReverseGeocoder(geodata_dir=None)
    assert geocoder.source == "bundled-fixture"

    match = geocoder.lookup(40.4168, -3.7038)  # Madrid
    assert match is not None
    assert match.city == "Madrid"
    assert match.country == "Spain"

    match2 = geocoder.lookup(38.7223, -9.1393)  # Lisbon
    assert match2.city == "Lisbon"
    assert match2.country == "Portugal"


def test_bundled_fixture_gives_up_far_from_any_reference_city():
    # A11 (live report): a Cadiz beach (~330 km from Lisbon, the nearest of
    # the 10 bundled cities) was labelled "Lisbon, Portugal". With only 10
    # reference points the country guess is not reliable that far out
    # either, so it now reports nothing instead of a wrong place.
    geocoder = ReverseGeocoder(geodata_dir=None)
    match = geocoder.lookup(36.53, -6.30)  # Cadiz, Spain
    assert match is None


def _write_fake_geonames(geodata_dir, rows):
    """rows: list of (name, lat, lon, feature_code, country_code, population)."""
    geodata_dir.mkdir(parents=True, exist_ok=True)
    lines = []
    for i, (name, lat, lon, fcode, cc, pop) in enumerate(rows, start=1):
        # cities1000.txt is tab-separated with 19 columns; only the ones
        # ReverseGeocoder reads need real values.
        cols = [str(i), name, name, "", str(lat), str(lon), "P", fcode, cc, "", "1", "", "", "", str(pop), "", "", "Europe/X", "2024-01-01"]
        lines.append("\t".join(cols))
    (geodata_dir / "cities1000.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_geonames_labels_neighbourhood_with_its_parent_city(tmp_path):
    # B4 (live report): after the world-cities download, a neighbourhood's
    # `region` was empty and `place="Lisbon"` stopped finding its photos.
    _write_fake_geonames(
        tmp_path,
        [
            ("Lisbon", 38.7223, -9.1393, "PPLC", "PT", 506654),
            ("Restelo", 38.7020, -9.2050, "PPLX", "PT", 0),
            ("Madrid", 40.4168, -3.7038, "PPLC", "ES", 3223000),
        ],
    )
    geocoder = ReverseGeocoder(geodata_dir=tmp_path)
    assert geocoder.source == "geonames-cities1000"

    neighbourhood = geocoder.lookup(38.7020, -9.2050)  # exactly at Restelo
    assert neighbourhood.city == "Restelo"
    assert neighbourhood.region == "Lisbon"  # the parent municipality
    assert neighbourhood.country == "Portugal"
    assert neighbourhood.approximate is False

    # The big place itself must not get "Madrid, Madrid, Spain".
    capital = geocoder.lookup(40.4168, -3.7038)
    assert capital.city == "Madrid"
    assert capital.region is None


def test_geonames_beyond_cutoff_keeps_only_the_country(tmp_path):
    _write_fake_geonames(
        tmp_path,
        [
            ("Lisbon", 38.7223, -9.1393, "PPLC", "PT", 506654),
            ("Madrid", 40.4168, -3.7038, "PPLC", "ES", 3223000),
        ],
    )
    geocoder = ReverseGeocoder(geodata_dir=tmp_path)
    far = geocoder.lookup(41.9028, 12.4964)  # Rome: far from both entries
    assert far is not None
    assert far.city is None
    assert far.region is None
    assert far.country in ("Portugal", "Spain")  # whichever is nearer
    assert far.approximate is True
    assert far.distance_km > NEARBY_KM
