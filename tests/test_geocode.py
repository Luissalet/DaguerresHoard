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
    """rows: (name, lat, lon, feature_code, country_code, population[, admin codes]).
    admin codes are GeoNames admin1..admin4, e.g. ("14", "1106", "110665")."""
    geodata_dir.mkdir(parents=True, exist_ok=True)
    lines = []
    for i, row in enumerate(rows, start=1):
        name, lat, lon, fcode, cc, pop = row[:6]
        admin = list(row[6]) if len(row) > 6 else ["1"]
        admin += [""] * (4 - len(admin))
        # cities1000.txt is tab-separated with 19 columns; only the ones
        # ReverseGeocoder reads need real values.
        cols = [str(i), name, name, "", str(lat), str(lon), "P", fcode, cc, "", *admin, str(pop), "", "", "Europe/X", "2024-01-01"]
        lines.append("\t".join(cols))
    (geodata_dir / "cities1000.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


# Real GeoNames cities1000 rows (name, lat, lon, feature code, country,
# population, admin1..admin4) around the places of the use cases.
REAL_ROWS = [
    ("Lisbon", 38.72509, -9.1498, "PPLC", "PT", 517802, ("14", "1106")),
    ("Alfama", 38.7112, -9.12772, "PPLX", "PT", 2471, ("14", "1106", "110665")),
    ("São Jorge de Arroios", 38.7289, -9.13806, "PPLX", "PT", 22990, ("14", "1106", "110656")),
    ("Restelo", 38.69955, -9.21406, "PPLX", "PT", 7287, ("14", "1106", "110658")),
    ("Algés", 38.70245, -9.22936, "PPL", "PT", 19327, ("14", "1110", "111012")),
    ("Madrid", 40.4165, -3.70256, "PPLC", "ES", 3255944, ("29", "M", "28079")),
    ("Retiro", 40.41317, -3.68307, "PPLX", "ES", 126058, ("29", "M", "28079", "3")),
    ("Salamanca", 40.42972, -3.67975, "PPLX", "ES", 147707, ("29", "M", "28079", "4")),
    ("Cadiz", 36.52672, -6.2891, "PPLA2", "ES", 116979, ("51", "CA", "11012")),
    ("Seville", 37.38283, -5.97317, "PPLA", "ES", 703206, ("51", "SE", "41091")),
    ("Tokyo", 35.6895, 139.69171, "PPLC", "JP", 9733276, ("40",)),
    ("Minato City", 35.6581, 139.7515, "PPLA2", "JP", 260486, ("40", "1857091")),
    ("Akasaka", 35.67135, 139.73442, "PPLX", "JP", 17603, ("40", "1857091")),
    ("Kyoto", 35.02107, 135.75385, "PPLA", "JP", 1463723, ("22", "1857906", "26102")),
    ("Nakagyo-ku", 35.0103, 135.7543, "PPLX", "JP", 105000, ("22", "1857906", "26104")),
]


def test_geonames_labels_neighbourhood_with_its_city_from_admin_codes(tmp_path):
    # B4 (live report, and again in the re-walk on the real cities1000
    # file): the nearest place of 15,000+ people to a Lisbon neighbourhood
    # is often another neighbourhood (São Jorge de Arroios, Algés), so
    # "nearest big place" labelled Alfama "Alfama, São Jorge de Arroios" and
    # `place="Lisbon"` found 10 of 54 trip photos. The admin codes say which
    # city a place belongs to.
    _write_fake_geonames(tmp_path, REAL_ROWS)
    geocoder = ReverseGeocoder(geodata_dir=tmp_path)
    assert geocoder.source == "geonames-cities1000"

    def at(name):
        row = next(r for r in REAL_ROWS if r[0] == name)
        return geocoder.lookup(row[1], row[2])

    alfama = at("Alfama")
    assert (alfama.city, alfama.region, alfama.country) == ("Alfama", "Lisbon", "Portugal")
    assert alfama.approximate is False
    assert at("Restelo").region == "Lisbon"
    # a neighbourhood bigger than 15,000 people is still not a parent
    assert at("São Jorge de Arroios").region == "Lisbon"
    # Algés is its own municipality, but in Lisbon's district, 8 km away
    assert at("Algés").region == "Lisbon"
    # Madrid districts (populations above 100,000) belong to Madrid
    assert at("Retiro").region == "Madrid"
    assert at("Salamanca").region == "Madrid"
    # Tokyo's wards: Tokyo wins over Minato City by population
    assert at("Akasaka").region == "Tokyo"
    assert at("Minato City").region == "Tokyo"
    # Kyoto lists its city hall's ward as its own code; its wards still
    # belong to it
    assert at("Nakagyo-ku").region == "Kyoto"
    # a city is not its own parent, and a region's capital 95 km away
    # does not claim it (Seville is the seat of Andalusia, 51)
    assert at("Cadiz").region is None
    assert at("Madrid").region is None
    assert at("Tokyo").region is None


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
