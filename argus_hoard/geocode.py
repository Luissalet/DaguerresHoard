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


@dataclass
class CityMatch:
    city: str
    region: str | None
    country: str | None
    distance_km: float


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
        names, regions, codes, coords = [], [], [], []
        with open(cities_file, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.rstrip("\n").split("\t")
                if len(parts) < 9:
                    continue
                names.append(parts[1])
                coords.append((float(parts[4]), float(parts[5])))
                codes.append(parts[8])
                regions.append(None)
        if not names:
            return False
        self._names, self._regions, self._country_codes = names, regions, codes
        self._coords = np.array(coords, dtype=np.float64)
        self._country_names = _bundled_country_names()
        if country_file.exists():
            with open(country_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("#") or not line.strip():
                        continue
                    parts = line.split("\t")
                    if len(parts) > 4:
                        self._country_names[parts[0]] = parts[4]
        return True

    def lookup(self, lat: float, lon: float) -> CityMatch | None:
        if self._coords.shape[0] == 0:
            return None
        lat1 = math.radians(lat)
        lon1 = math.radians(lon)
        lat2 = np.radians(self._coords[:, 0])
        lon2 = np.radians(self._coords[:, 1])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = np.sin(dlat / 2) ** 2 + math.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
        c = 2 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))
        distances_km = 6371.0 * c
        idx = int(np.argmin(distances_km))
        code = self._country_codes[idx]
        return CityMatch(
            city=self._names[idx],
            region=self._regions[idx],
            country=self._country_names.get(code, code),
            distance_km=float(distances_km[idx]),
        )


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
