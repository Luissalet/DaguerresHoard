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
_BIG_PLACE_CODES = {"PPLC", "PPLA", "PPLA2"}
_BIG_PLACE_MIN_POPULATION = 15_000


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
        self._big_idx: np.ndarray = np.zeros(0, dtype=np.int64)
        self.source = "bundled-fixture"
        if geodata_dir and self._load_geonames(geodata_dir):
            self.source = "geonames-cities1000"
        else:
            self._load_bundled()

    def _load_bundled(self) -> None:
        text = resources.files("argus_hoard.data").joinpath("cities_fixture.tsv").read_text(encoding="utf-8")
        rows = list(csv.DictReader(io.StringIO(text), delimiter="\t"))
        self._names = [r["name"] for r in rows]
        self._regions = [r["region"] for r in rows]
        self._country_codes = [r["country_code"] for r in rows]
        self._coords = np.array([[float(r["lat"]), float(r["lon"])] for r in rows], dtype=np.float64)
        self._country_names = _bundled_country_names()

    def _load_geonames(self, geodata_dir: Path) -> bool:
        cities_file = geodata_dir / "cities1000.txt"
        country_file = geodata_dir / "countryInfo.txt"
        if not cities_file.exists():
            return False
        names, codes, coords, populations, feature_codes = [], [], [], [], []
        with open(cities_file, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.rstrip("\n").split("\t")
                if len(parts) < 15:
                    continue
                names.append(parts[1])
                coords.append((float(parts[4]), float(parts[5])))
                codes.append(parts[8])
                feature_codes.append(parts[7])
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
        populations_arr = np.array(populations, dtype=np.int64)
        is_big = (populations_arr >= _BIG_PLACE_MIN_POPULATION) | np.array(
            [fc in _BIG_PLACE_CODES for fc in feature_codes]
        )
        self._big_idx = np.where(is_big)[0]
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
        if self.source == "geonames-cities1000" and self._big_idx.size:
            # B4: label the parent municipality/admin area next to the
            # neighbourhood ("Restelo, Lisbon, Portugal"), and match `place`
            # against it too, so "Lisbon" still finds photos geocoded to a
            # neighbourhood after the world-cities download.
            parent_idx, _ = self._nearest(lat, lon, self._big_idx)
            parent_name = self._names[parent_idx]
            if parent_name != city:
                region = parent_name
        return CityMatch(city=city, region=region, country=country, distance_km=distance_km, approximate=False)


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
