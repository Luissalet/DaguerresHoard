"""Offline reverse geocoding: nearest city by haversine distance over a
numpy array, no external network at query time.

Ships with a tiny bundled fixture (`data/cities_fixture.tsv`, ~10 cities)
so reverse geocoding and its tests work with zero setup. When GPS photos
exist and the user opts in, `download_geonames` fetches the full GeoNames
`cities1000` dataset (CC BY 4.0, credited in the README) into
`data/geodata/` and `ReverseGeocoder` prefers it automatically.
"""
from __future__ import annotations

import csv
import io
import math
import zipfile
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

import numpy as np

GEONAMES_URL = "https://download.geonames.org/export/dump/cities1000.zip"
COUNTRY_INFO_URL = "https://download.geonames.org/export/dump/countryInfo.txt"

# B4/A11 (live report): with no cutoff, a neighbourhood ("Restelo") was
# geocoded fine, but a photo far from the nearest reference point (a
# 450 km-away "Lisbon" for a Cadiz beach, on the 10-city bundled fixture)
# was mislabelled with total confidence. Within NEARBY_KM the city-level
# match is trusted; beyond it, cities1000 is still dense enough worldwide
# to trust the *country*, but the 10-city fixture is not, so it gives up
# rather than guess a city or a country from hundreds of km away.
NEARBY_KM = 50.0
# Seats of government in GeoNames, and the depth of the division each one
# is the seat of: the capital (PPLC, usually also the seat of its first-order
# division) and the seats of the first- to fourth-order divisions.
_SEAT_LEVEL = {"PPLC": 1, "PPLA": 1, "PPLA2": 2, "PPLA3": 3, "PPLA4": 4}
# A parent further away than this is not what anyone means by "the city"
# (and keeps a region's capital from claiming villages of the next province).
PARENT_KM = 30.0
# Bump when the labels lookup() produces change, so existing libraries are
# re-geocoded on the next start (see Library._maybe_regeocode).
GEOCODER_VERSION = "2"


@dataclass
class CityMatch:
    city: str | None
    region: str | None
    country: str | None
    distance_km: float
    approximate: bool = False


def _bundled_country_names() -> dict[str, str]:
    text = resources.files("argus_hoard.data").joinpath("country_names.tsv").read_text(encoding="utf-8")
    out = {}
    for row in csv.DictReader(io.StringIO(text), delimiter="\t"):
        out[row["code"]] = row["name"]
    return out


class ReverseGeocoder:
    def __init__(self, geodata_dir: Path | None = None):
        self._names: list[str] = []
        self._regions: list[str | None] = []
        self._country_codes: list[str] = []
        self._coords: np.ndarray
        self._country_names: dict[str, str] = {}
        self._populations: list[int] = []
        self._admin: list[tuple[str, ...]] = []
        # (country code, admin-code prefix) -> index of the most populous
        # seat of that division
        self._seats: dict[tuple[str, tuple[str, ...]], int] = {}
        self.source = "bundled-fixture"
        if geodata_dir and self._load_geonames(geodata_dir):
            self.source = "geonames-cities1000"
        else:
            self._load_bundled()

    def _load_bundled(self) -> None:
        text = resources.files("argus_hoard.data").joinpath("cities_fixture.tsv").read_text(encoding="utf-8")
        rows = list(csv.DictReader(io.StringIO(text), delimiter="\t"))
        self._names = [r["name"] for r in rows]
        # `region` means "the city this place belongs to" (see _parent);
        # the ten bundled entries are cities themselves. The file's region
        # column (Catalonia, Ile-de-France...) is an admin area, not that,
        # and would group Paris under "Ile-de-France" on the Places page.
        self._regions = [None] * len(rows)
        self._country_codes = [r["country_code"] for r in rows]
        self._coords = np.array([[float(r["lat"]), float(r["lon"])] for r in rows], dtype=np.float64)
        self._country_names = _bundled_country_names()

    def _load_geonames(self, geodata_dir: Path) -> bool:
        cities_file = geodata_dir / "cities1000.txt"
        country_file = geodata_dir / "countryInfo.txt"
        if not cities_file.exists():
            return False
        names, codes, coords, populations, feature_codes, admin = [], [], [], [], [], []
        with open(cities_file, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.rstrip("\n").split("\t")
                if len(parts) < 15:
                    continue
                names.append(parts[1])
                coords.append((float(parts[4]), float(parts[5])))
                codes.append(parts[8])
                feature_codes.append(parts[7])
                admin.append(_admin_prefix(parts[10:14]))
                try:
                    populations.append(int(parts[14]))
                except ValueError:
                    populations.append(0)
        if not names:
            return False
        self._names, self._country_codes = names, codes
        self._regions = [None] * len(names)
        self._coords = np.array(coords, dtype=np.float64)
        self._country_names = _bundled_country_names()
        self._populations, self._admin = populations, admin
        for i, fc in enumerate(feature_codes):
            level = _SEAT_LEVEL.get(fc)
            if level is None or not admin[i]:
                continue
            # a seat's own codes can be more specific than its division
            # (Kyoto, seat of prefecture 22, lists the ward its city hall
            # is in), so register it at both depths
            for prefix in {admin[i][:level], admin[i]}:
                key = (codes[i], prefix)
                if key not in self._seats or populations[i] > populations[self._seats[key]]:
                    self._seats[key] = i
        if country_file.exists():
            with open(country_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("#") or not line.strip():
                        continue
                    parts = line.split("\t")
                    if len(parts) > 4:
                        self._country_names[parts[0]] = parts[4]
        return True

    def _nearest(self, lat1: float, lon1: float, indices: np.ndarray) -> tuple[int, float]:
        """Nearest entry (by absolute index into self._coords) among
        `indices`, and its distance in km."""
        coords = self._coords[indices]
        lat1r = math.radians(lat1)
        lon1r = math.radians(lon1)
        lat2 = np.radians(coords[:, 0])
        lon2 = np.radians(coords[:, 1])
        dlat = lat2 - lat1r
        dlon = lon2 - lon1r
        a = np.sin(dlat / 2) ** 2 + math.cos(lat1r) * np.cos(lat2) * np.sin(dlon / 2) ** 2
        c = 2 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))
        distances_km = 6371.0 * c
        local = int(np.argmin(distances_km))
        return int(indices[local]), float(distances_km[local])

    def lookup(self, lat: float, lon: float) -> CityMatch | None:
        if self._coords.shape[0] == 0:
            return None
        idx, distance_km = self._nearest(lat, lon, np.arange(self._coords.shape[0]))
        code = self._country_codes[idx]
        country = self._country_names.get(code, code)

        if distance_km > NEARBY_KM:
            # B4/A11: too far to trust a specific city. cities1000 is dense
            # enough worldwide that its nearest country is still reliable;
            # the 10-city bundled fixture is not (it mislabelled a Cadiz
            # beach as Portugal), so it reports nothing rather than guess.
            if self.source == "geonames-cities1000":
                return CityMatch(city=None, region=None, country=country, distance_km=distance_km, approximate=True)
            return None

        city = self._names[idx]
        region = self._regions[idx]
        if self.source == "geonames-cities1000":
            # B4 (live report): label the town or city a neighbourhood
            # belongs to ("Restelo, Lisbon, Portugal") and match `place`
            # against it, so "Lisbon" still finds photos geocoded to a
            # neighbourhood after the world-cities download.
            region = self._parent(idx, lat, lon)
        return CityMatch(city=city, region=region, country=country, distance_km=distance_km, approximate=False)

    def _parent(self, idx: int, lat: float, lon: float) -> str | None:
        """The most populous seat of government (capital or admin-division
        seat) of a division this place belongs to (its admin codes start
        with the division's), within PARENT_KM and more populous than the
        place itself.

        The nearest "big" place is not the parent: in real GeoNames data the
        nearest place of 15,000+ people to a Lisbon neighbourhood is often
        another neighbourhood (Sao Jorge de Arroios, Algés), and a Madrid
        district's is another district. The admin codes say which
        municipality a place belongs to: Alfama (PT, 14, 1106, 110665) sits
        under Lisbon (PPLC, PT, 14, 1106); Akasaka (JP, 40, 1857091) under
        both Minato City (PPLA2) and Tokyo (PPLC, JP, 40), and Tokyo wins
        by population. Algés (PT, 14, 1110) is not under Lisbon's
        municipality (1106) but is in its district (14), 8 km away."""
        codes = self._admin[idx]
        cc = self._country_codes[idx]
        best: int | None = None
        for depth in range(1, len(codes) + 1):
            seat = self._seats.get((cc, codes[:depth]))
            if seat is None or seat == idx or self._names[seat] == self._names[idx]:
                continue
            if self._populations[seat] <= self._populations[idx]:
                continue
            if best is None or self._populations[seat] > self._populations[best]:
                best = seat
        if best is None:
            return None
        _, dist = self._nearest(lat, lon, np.array([best]))
        return self._names[best] if dist <= PARENT_KM else None


def _admin_prefix(fields: list[str]) -> tuple[str, ...]:
    """GeoNames admin1..admin4 codes up to the first empty one: the chain of
    divisions a place belongs to, most general first."""
    out: list[str] = []
    for code in fields:
        code = code.strip()
        if not code:
            break
        out.append(code)
    return tuple(out)


def download_geonames(geodata_dir: Path, timeout: float = 30.0) -> str:
    """Download and extract cities1000 + countryInfo into geodata_dir.
    Raises on any network/parse failure -- callers decide how to surface it
    (this must never block indexing)."""
    import httpx

    geodata_dir.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        resp = client.get(GEONAMES_URL)
        resp.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            zf.extract("cities1000.txt", geodata_dir)
        resp2 = client.get(COUNTRY_INFO_URL)
        resp2.raise_for_status()
        (geodata_dir / "countryInfo.txt").write_bytes(resp2.content)
    return "ok"
