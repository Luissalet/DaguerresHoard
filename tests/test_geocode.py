from argus_hoard.geocode import ReverseGeocoder


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
