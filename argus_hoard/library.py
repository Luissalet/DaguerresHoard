"""The core engine: indexing pipeline plus every read/write operation used
by both the HTTP API and the MCP adapter. No FastAPI imports here -- this
module is plain Python so it can be unit-tested directly.

Hard invariant: nothing in this module opens an original photo for
writing, renames, moves or deletes it. Originals are only ever read.
"""
from __future__ import annotations

import base64
import datetime as dt
import json
import logging
import os
import re
import sqlite3
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import db as dbmod
from .backend import Backend
from .captions import DEFAULT_BASE_URL, DEFAULT_MODEL, LinkCaptioner
from .config import EMBED_DIM, Settings
from .contact_sheet import MAX_ITEMS as SHEET_MAX_ITEMS
from .contact_sheet import ContactSheetItem, encode_jpeg_under, render_contact_sheet
from .duplicates import PhotoRow, exact_duplicate_groups, near_duplicate_groups
from .embeddings import ClipEmbedder, Embedder, FakeEmbedder, VectorStore
from .formats import HEIF_AVAILABLE
from .geocode import ReverseGeocoder, download_geonames
from .hashing import content_hash
from .hoard_link import BackendError, Unavailable
from .jobs import JobHandle, JobManager
from .lang import detect_non_english
from .metadata import extract_metadata
from .phash import compute_phash
from .scanning import stat_signature, walk_images
from .thumbnails import make_thumbnail, thumb_path

log = logging.getLogger(__name__)

EMBED_BATCH = 32
CHUNK = 64  # files prepared in parallel per step
MAX_LIMIT = 50
SHOW_MAX_IDS = 4
SHOW_MAX_BYTES = 200 * 1024
ID_RE = re.compile(r"^[0-9a-f]{32}$")

FILTER_NAMES = (
    "taken_after", "taken_before", "year", "month", "place", "folder",
    "camera", "orientation", "min_megapixels", "has_gps",
)
FAKE_EMBEDDER_NOTE = (
    "The semantic image model is not installed, so search only understands "
    "colour words (red, orange, yellow, green, blue, purple, pink, white, black). "
    "Tell the owner they can download it in Argus Settings (about 600 MB) for "
    "content search, and do not trust the ranking for anything else."
)


class NotFoundError(Exception):
    pass


class ValidationError(Exception):
    pass


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _clamp_limit(limit: Any, default: int, maximum: int = MAX_LIMIT) -> int:
    try:
        value = int(limit if limit is not None else default)
    except (TypeError, ValueError):
        raise ValidationError(f"limit must be an integer between 1 and {maximum}") from None
    if value < 1:
        raise ValidationError(f"limit must be between 1 and {maximum}, got {value}")
    return min(value, maximum)


def _like(value: str) -> str:
    """A LIKE pattern matching `value` as a literal substring (escape '!')."""
    escaped = value.replace("!", "!!").replace("%", "!%").replace("_", "!_")
    return f"%{escaped}%"


def _parse_date_filter(name: str, value: Any) -> str:
    text = str(value).strip()
    try:
        if len(text) == 10:
            dt.date.fromisoformat(text)
        else:
            dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        raise ValidationError(
            f"{name} must be an ISO date like 2024-03-31 (or 2024-03-31T18:00), got {value!r}"
        ) from None
    return text


def select_embedder(settings: Settings) -> Embedder:
    try:
        if ClipEmbedder.is_cached(settings.models_dir):
            return ClipEmbedder(settings.models_dir, local_only=True)
    except Exception:  # noqa: BLE001 - a broken cache falls back, it does not stop the app
        log.exception("could not load the cached CLIP model; using the fallback embedder")
    return FakeEmbedder()


@dataclass
class _Prepared:
    """The CPU/IO-heavy part of indexing one file, computed off the DB thread."""

    photo_id: str
    path: Path
    size: int
    mtime_ns: int
    content_hash: str
    meta: Any = None
    phash: int | None = None
    error: str | None = None


class Library:
    def __init__(self, settings: Settings, conn: sqlite3.Connection | None = None, embedder: Embedder | None = None):
        settings.ensure_dirs()
        self.settings = settings
        self._conns = dbmod.ThreadLocalConnections(settings.db_path)
        if conn is not None:  # tests may inject a connection for the constructing thread
            self._conns._local.conn = conn
        self.embedder = embedder or select_embedder(settings)
        self.vectors = VectorStore(settings.vectors_path, dim=EMBED_DIM)
        self.geocoder = ReverseGeocoder(settings.geodata_dir if (settings.geodata_dir / "cities1000.txt").exists() else None)
        self.jobs = JobManager(self._conns.get)
        self.backend = Backend(settings.data_dir, self.conn)
        self._index_lock = threading.Lock()
        self._model_lock = threading.Lock()

    @property
    def conn(self) -> sqlite3.Connection:
        return self._conns.get()

    def close(self) -> None:
        self.backend.close()
        self._conns.close_all()

    @property
    def _skip_dirs(self) -> list[Path]:
        s = self.settings
        return [s.thumbs_dir, s.models_dir, s.geodata_dir, s.logs_dir]

    # ------------------------------------------------------------------ #
    # Roots / indexing
    # ------------------------------------------------------------------ #
    def add_root(self, path: str, added_by: str = "user", excluded_globs: list[str] | None = None) -> dict:
        if not isinstance(path, str) or not path.strip():
            raise ValidationError("path is required: an absolute folder path such as C:\\Users\\me\\Pictures")
        p = Path(path.strip()).expanduser()
        if not p.is_absolute():
            raise ValidationError(f"path must be absolute (for example C:\\Users\\me\\Pictures), got: {path}")
        if not p.is_dir():
            raise ValidationError(f"not an existing folder: {path}")
        p = Path(os.path.abspath(p))
        for managed in self._skip_dirs + [self.settings.data_dir / "argus.db"]:
            try:
                p.relative_to(managed)
                raise ValidationError(f"{path} is inside Argus's own data folder and cannot be a photo root")
            except ValueError:
                pass
        globs = [g.strip() for g in (excluded_globs or []) if isinstance(g, str) and g.strip()][:50]
        c = self.conn
        c.execute(
            "INSERT OR IGNORE INTO roots(path, excluded_globs, created_at, added_by) VALUES (?, ?, ?, ?)",
            (str(p), json.dumps(globs), _now(), added_by),
        )
        c.commit()
        row = c.execute("SELECT * FROM roots WHERE path = ?", (str(p),)).fetchone()
        return self._root_dict(row)

    def update_root_excludes(self, root_id: int, excluded_globs: list[str]) -> dict:
        globs = [g.strip() for g in excluded_globs if isinstance(g, str) and g.strip()][:50]
        c = self.conn
        cur = c.execute("UPDATE roots SET excluded_globs = ? WHERE id = ?", (json.dumps(globs), root_id))
        c.commit()
        if cur.rowcount == 0:
            raise NotFoundError(f"root not found: {root_id}")
        return self._root_dict(c.execute("SELECT * FROM roots WHERE id = ?", (root_id,)).fetchone())

    def remove_root(self, root_id: int) -> None:
        """UI-only (human) operation -- never exposed as an agent tool.
        Forgets the folder and Argus's own derived data (index rows, album
        memberships, captions, thumbnails). The original files are untouched."""
        c = self.conn
        ids = [r["id"] for r in c.execute("SELECT id FROM photos WHERE root_id = ?", (root_id,)).fetchall()]
        for start in range(0, len(ids), 500):
            chunk = ids[start : start + 500]
            marks = ",".join("?" * len(chunk))
            c.execute(f"DELETE FROM album_photos WHERE photo_id IN ({marks})", chunk)
            c.execute(
                f"DELETE FROM photos_fts WHERE rowid IN (SELECT rowid FROM photos WHERE id IN ({marks}))", chunk
            )
        c.execute("DELETE FROM photos WHERE root_id = ?", (root_id,))
        c.execute("DELETE FROM roots WHERE id = ?", (root_id,))
        c.commit()
        for pid in ids:
            try:
                thumb_path(self.settings.thumbs_dir, pid).unlink(missing_ok=True)
            except OSError:
                pass

    def _root_dict(self, r: sqlite3.Row) -> dict:
        d = dict(r)
        d["excluded_globs"] = json.loads(d["excluded_globs"])
        d["photo_count"] = self.conn.execute(
            "SELECT COUNT(*) c FROM photos WHERE root_id = ? AND missing = 0", (r["id"],)
        ).fetchone()["c"]
        d["exists"] = Path(d["path"]).is_dir()
        return d

    def list_roots(self) -> list[dict]:
        return [self._root_dict(r) for r in self.conn.execute("SELECT * FROM roots ORDER BY id").fetchall()]

    def start_scan(self, root_id: int | None = None) -> str:
        if root_id is not None and not self.conn.execute("SELECT 1 FROM roots WHERE id = ?", (root_id,)).fetchone():
            raise NotFoundError(f"root not found: {root_id}")
        return self.jobs.start("index", lambda handle: self._run_index(root_id, handle))

    def _run_index(self, root_id: int | None, handle: JobHandle) -> None:
        # One index run at a time: parallel runs over the same rows raced on
        # inserts and appended duplicate vectors. Later requests queue here.
        if not self._index_lock.acquire(blocking=False):
            handle.progress(0.0, "waiting for the scan already in progress")
            self._index_lock.acquire()
        try:
            self._run_index_locked(root_id, handle)
        finally:
            self._index_lock.release()

    def _run_index_locked(self, root_id: int | None, handle: JobHandle) -> None:
        c = self.conn
        query, params = "SELECT * FROM roots", ()
        if root_id is not None:
            query, params = query + " WHERE id = ?", (root_id,)
        roots = [dict(r) for r in c.execute(query, params).fetchall()]
        stats = {"files_seen": 0, "new": 0, "updated": 0, "moved": 0, "unchanged": 0,
                 "embedded": 0, "errors": 0, "error_samples": []}

        def record_error(path: Path, exc: BaseException | str) -> None:
            stats["errors"] += 1
            if len(stats["error_samples"]) < 5:
                msg = exc if isinstance(exc, str) else f"{type(exc).__name__}: {exc}"
                stats["error_samples"].append(f"{path}: {msg}"[:300])

        handle.progress(0.0, "listing files")
        plan: list[tuple[dict, Path]] = []
        for root in roots:
            root_path = Path(root["path"])
            if not root_path.is_dir():
                record_error(root_path, "folder is not reachable (unplugged drive or renamed?)")
                continue
            for path in walk_images(root_path, json.loads(root["excluded_globs"]), skip_dirs=self._skip_dirs):
                plan.append((root, path))
        stats["files_seen"] = len(plan)
        seen_paths = {str(p) for _, p in plan}
        reachable_root_ids = {r["id"] for r in roots if Path(r["path"]).is_dir()}

        pending_embed: list[str] = []
        total = len(plan)
        started = time.monotonic()
        workers = max(2, min(8, (os.cpu_count() or 2)))
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="argus-decode") as pool:
            for start in range(0, total, CHUNK):
                chunk = plan[start : start + CHUNK]
                self._index_chunk(chunk, pool, pending_embed, stats, record_error)
                done = start + len(chunk)
                rate = done / max(1e-6, time.monotonic() - started)
                eta = (total - done) / rate if rate > 0 else 0
                handle.progress(
                    0.85 * done / max(1, total),
                    f"{done}/{total} files · {rate:.1f} files/s · ETA {int(eta)}s",
                )
                handle.set_stats(stats)

        # Photos whose vector is missing or came from another embedder
        # (e.g. indexed before the CLIP model was downloaded) are re-embedded
        # from their thumbnail: vectors from two models are not comparable.
        pending_set = set(pending_embed)
        root_ids = [r["id"] for r in roots]
        if root_ids:
            marks = ",".join("?" * len(root_ids))
            for r in c.execute(
                f"SELECT id FROM photos WHERE missing = 0 AND root_id IN ({marks}) "
                "AND (embed_row IS NULL OR embed_model IS NULL OR embed_model != ?)",
                (*root_ids, self.embedder.name),
            ).fetchall():
                if r["id"] not in pending_set:
                    pending_embed.append(r["id"])
                    pending_set.add(r["id"])

        self._embed_pending(pending_embed, handle, stats, record_error)

        # Rows under reachable roots whose file disappeared (and was not
        # recognised as moved) are flagged missing -- never deleted, so an
        # unplugged drive does not lose albums or captions.
        for rid in reachable_root_ids:
            for row in c.execute("SELECT id, path FROM photos WHERE root_id = ? AND missing = 0", (rid,)).fetchall():
                if row["path"] not in seen_paths and not Path(row["path"]).exists():
                    c.execute("UPDATE photos SET missing = 1 WHERE id = ?", (row["id"],))
        c.commit()
        handle.set_stats(stats)
        summary = f"indexed {total} files: {stats['new']} new, {stats['updated']} changed, {stats['moved']} moved"
        if stats["errors"]:
            summary += f", {stats['errors']} could not be read"
        handle.progress(1.0, summary)

    def _index_chunk(self, chunk, pool, pending_embed, stats, record_error) -> None:
        c = self.conn
        # 1) cheap: stat + "unchanged?" check against the DB
        candidates: list[tuple[dict, Path, int, int, sqlite3.Row | None]] = []
        for root, path in chunk:
            try:
                size, mtime_ns = stat_signature(path)
            except OSError as exc:
                record_error(path, exc)
                continue
            existing = c.execute("SELECT * FROM photos WHERE path = ?", (str(path),)).fetchone()
            if existing and existing["size"] == size and existing["mtime_ns"] == mtime_ns and not existing["missing"]:
                stats["unchanged"] += 1
                continue
            candidates.append((root, path, size, mtime_ns, existing))
        if not candidates:
            return

        # 2) parallel: stream-hash the candidates
        def safe_hash(path: Path):
            try:
                return content_hash(path), None
            except OSError as exc:
                return None, exc

        hashes = list(pool.map(safe_hash, [cand[1] for cand in candidates]))

        # 3) decide per file: same bytes, moved file, or needs full work
        work: list[tuple[dict, _Prepared, sqlite3.Row | None]] = []
        for (root, path, size, mtime_ns, existing), (file_hash, err) in zip(candidates, hashes):
            if err is not None:
                record_error(path, err)
                continue
            if existing and existing["content_hash"] == file_hash:
                c.execute(
                    "UPDATE photos SET size = ?, mtime_ns = ?, missing = 0, root_id = ? WHERE id = ?",
                    (size, mtime_ns, root["id"], existing["id"]),
                )
                stats["unchanged"] += 1
                continue
            if not existing:
                moved_id = None
                for m in c.execute(
                    "SELECT id, path FROM photos WHERE content_hash = ? AND path != ?", (file_hash, str(path))
                ).fetchall():
                    if not Path(m["path"]).exists():
                        moved_id = m["id"]
                        break
                if moved_id:
                    # same bytes, new path: keep id, embedding, caption, albums
                    c.execute(
                        "UPDATE photos SET path = ?, root_id = ?, size = ?, mtime_ns = ?, missing = 0 WHERE id = ?",
                        (str(path), root["id"], size, mtime_ns, moved_id),
                    )
                    stats["moved"] += 1
                    continue
            photo_id = existing["id"] if existing else uuid.uuid4().hex
            work.append((root, _Prepared(photo_id, path, size, mtime_ns, file_hash), existing))
        c.commit()
        if not work:
            return

        # 4) parallel: metadata, thumbnail, perceptual hash (Pillow releases the GIL)
        def prepare(item: _Prepared) -> _Prepared:
            try:
                item.meta = extract_metadata(item.path)
                make_thumbnail(item.path, thumb_path(self.settings.thumbs_dir, item.photo_id))
                item.phash = compute_phash(item.path)
            except Exception as exc:  # noqa: BLE001 - one bad file must not stop the scan
                item.error = f"{type(exc).__name__}: {exc}"
            return item

        prepared = list(pool.map(prepare, [w[1] for w in work]))

        # 5) sequential: write rows
        for (root, _, existing), item in zip(work, prepared):
            if item.error:
                record_error(item.path, item.error)
                continue
            meta = item.meta
            city = region = country = None
            if meta.gps_lat is not None and meta.gps_lon is not None:
                match = self.geocoder.lookup(meta.gps_lat, meta.gps_lon)
                if match:
                    city, region, country = match.city, match.region, match.country
            fields = dict(
                id=item.photo_id, root_id=root["id"], path=str(item.path), size=item.size,
                mtime_ns=item.mtime_ns, content_hash=item.content_hash, phash=f"{item.phash:016x}",
                width=meta.width, height=meta.height, taken_at=meta.taken_at, date_source=meta.date_source,
                make=meta.make, model=meta.model, lens=meta.lens, f_number=meta.f_number,
                exposure_time=meta.exposure_time, iso=meta.iso, focal_length=meta.focal_length,
                orientation=meta.orientation, gps_lat=meta.gps_lat, gps_lon=meta.gps_lon,
                city=city, region=region, country=country,
                embed_row=existing["embed_row"] if existing else None,
                indexed_at=_now(), missing=0,
            )
            if existing:
                # new content at the same path: the old caption described other pixels
                fields["caption"] = None
                set_clause = ", ".join(f"{k} = :{k}" for k in fields if k != "id")
                c.execute(f"UPDATE photos SET {set_clause}, embed_model = NULL WHERE id = :id", fields)
                c.execute("DELETE FROM photos_fts WHERE photo_id = ?", (item.photo_id,))
                stats["updated"] += 1
            else:
                cols = ", ".join(fields)
                placeholders = ", ".join(f":{k}" for k in fields)
                c.execute(f"INSERT INTO photos ({cols}) VALUES ({placeholders})", fields)
                stats["new"] += 1
            pending_embed.append(item.photo_id)
        c.commit()

    def _embed_pending(self, photo_ids: list[str], handle: JobHandle, stats: dict, record_error) -> None:
        c = self.conn
        total = len(photo_ids)
        for start in range(0, total, EMBED_BATCH):
            batch: list[tuple[str, Path]] = []
            for pid in photo_ids[start : start + EMBED_BATCH]:
                tp = thumb_path(self.settings.thumbs_dir, pid)
                if not tp.exists():
                    row = c.execute("SELECT path FROM photos WHERE id = ?", (pid,)).fetchone()
                    try:
                        make_thumbnail(Path(row["path"]), tp)
                    except Exception as exc:  # noqa: BLE001
                        record_error(Path(row["path"]) if row else tp, exc)
                        continue
                batch.append((pid, tp))
            if not batch:
                continue
            try:
                vecs = self.embedder.embed_images([tp for _, tp in batch])
            except Exception as exc:  # noqa: BLE001 - fall back to one-by-one to isolate the bad file
                vecs = []
                good = []
                for pid, tp in batch:
                    try:
                        vecs.append(self.embedder.embed_images([tp])[0])
                        good.append((pid, tp))
                    except Exception as inner:  # noqa: BLE001
                        record_error(tp, inner)
                batch = good
                if not batch:
                    log.warning("embedding batch failed: %s", exc)
                    continue
            for (pid, _), vec in zip(batch, vecs):
                self._store_embedding(pid, vec)
                stats["embedded"] += 1
            c.commit()
            done = min(total, start + EMBED_BATCH)
            handle.progress(0.85 + 0.15 * done / max(1, total), f"embedding {done}/{total} with {self.embedder.name}")

    def _store_embedding(self, photo_id: str, vec) -> None:
        c = self.conn
        row = c.execute("SELECT embed_row FROM photos WHERE id = ?", (photo_id,)).fetchone()
        if row and row["embed_row"] is not None and row["embed_row"] < self.vectors.count:
            self.vectors.update(row["embed_row"], vec)
            c.execute("UPDATE photos SET embed_model = ? WHERE id = ?", (self.embedder.name, photo_id))
        else:
            new_row = self.vectors.append(vec)
            c.execute(
                "UPDATE photos SET embed_row = ?, embed_model = ? WHERE id = ?",
                (new_row, self.embedder.name, photo_id),
            )

    # ------------------------------------------------------------------ #
    # Public photo dict + filtering
    # ------------------------------------------------------------------ #
    def _public(self, row: sqlite3.Row, score: float | None = None) -> dict:
        place = None
        if row["city"]:
            place = f"{row['city']}, {row['country']}" if row["country"] else row["city"]
        d = {
            "id": row["id"],
            "path": row["path"],
            "taken_at": row["taken_at"],
            "place": place,
            "size": row["size"],
            "width": row["width"],
            "height": row["height"],
            "thumbnail_url": f"/api/photos/{row['id']}/thumbnail",
        }
        if score is not None:
            d["score"] = round(float(score), 4)
        return d

    def validate_filters(self, filters: dict | None) -> dict:
        """Normalise agent/UI filters; unknown names and bad values are
        errors that say exactly what is accepted (a 27B model can fix those)."""
        if not filters:
            return {}
        if not isinstance(filters, dict):
            raise ValidationError("filters must be an object")
        unknown = sorted(set(filters) - set(FILTER_NAMES))
        if unknown:
            raise ValidationError(
                f"unknown filter(s): {', '.join(unknown)}. Valid filters: {', '.join(FILTER_NAMES)}"
            )
        out: dict[str, Any] = {}
        for key, value in filters.items():
            if value is None or value == "":
                continue
            if key in ("taken_after", "taken_before"):
                out[key] = _parse_date_filter(key, value)
            elif key == "year":
                try:
                    year = int(value)
                except (TypeError, ValueError):
                    raise ValidationError(f"year must be a number like 2024, got {value!r}") from None
                if not 1800 <= year <= 2200:
                    raise ValidationError(f"year out of range: {year}")
                out[key] = year
            elif key == "month":
                try:
                    month = int(value)
                except (TypeError, ValueError):
                    raise ValidationError(f"month must be 1-12, got {value!r}") from None
                if not 1 <= month <= 12:
                    raise ValidationError(f"month must be 1-12, got {month}")
                out[key] = month
            elif key == "orientation":
                if value not in ("landscape", "portrait"):
                    raise ValidationError(f"orientation must be 'landscape' or 'portrait', got {value!r}")
                out[key] = value
            elif key == "min_megapixels":
                try:
                    mp = float(value)
                except (TypeError, ValueError):
                    raise ValidationError(f"min_megapixels must be a number, got {value!r}") from None
                if mp < 0:
                    raise ValidationError("min_megapixels must be >= 0")
                out[key] = mp
            elif key == "has_gps":
                if isinstance(value, str):
                    if value.lower() not in ("true", "false", "1", "0"):
                        raise ValidationError(f"has_gps must be true or false, got {value!r}")
                    value = value.lower() in ("true", "1")
                out[key] = bool(value)
            else:  # place, folder, camera: substrings
                out[key] = str(value).strip()[:200]
        return out

    def _where(self, filters: dict) -> tuple[str, list[Any]]:
        f = self.validate_filters(filters)
        clauses = ["missing = 0"]
        params: list[Any] = []
        for key, op in (("taken_after", ">="), ("taken_before", "<=")):
            if key in f:
                value = f[key]
                if len(value) == 10:  # a plain date covers that whole day
                    clauses.append(f"substr(taken_at, 1, 10) {op} ?")
                else:
                    clauses.append(f"taken_at {op} ?")
                params.append(value)
        if "year" in f:
            clauses.append("substr(taken_at, 1, 4) = ?")
            params.append(f"{f['year']:04d}")
        if "month" in f:
            clauses.append("substr(taken_at, 6, 2) = ?")
            params.append(f"{f['month']:02d}")
        if "place" in f:
            clauses.append("(city LIKE ? ESCAPE '!' OR country LIKE ? ESCAPE '!' OR region LIKE ? ESCAPE '!')")
            params += [_like(f["place"])] * 3
        if "folder" in f:
            # accept either slash direction for Windows paths
            clauses.append("replace(path, '\\', '/') LIKE ? ESCAPE '!'")
            params.append(_like(f["folder"].replace("\\", "/")))
        if "camera" in f:
            clauses.append("(model LIKE ? ESCAPE '!' OR make LIKE ? ESCAPE '!')")
            params += [_like(f["camera"])] * 2
        if f.get("orientation") == "landscape":
            clauses.append("width >= height")
        elif f.get("orientation") == "portrait":
            clauses.append("height > width")
        if "min_megapixels" in f:
            clauses.append("(width * height) >= ?")
            params.append(f["min_megapixels"] * 1_000_000)
        if "has_gps" in f:
            clauses.append("gps_lat IS NOT NULL" if f["has_gps"] else "gps_lat IS NULL")
        return " AND ".join(clauses), params

    def _filtered_rows(self, filters: dict) -> list[sqlite3.Row]:
        where, params = self._where(filters)
        return self.conn.execute(f"SELECT * FROM photos WHERE {where}", params).fetchall()

    def list_photos(self, filters: dict | None = None, limit: int = 60, offset: int = 0) -> dict:
        """Chronological grid listing for the UI (no embedding search)."""
        where, params = self._where(filters or {})
        limit = _clamp_limit(limit, 60, maximum=500)
        offset = max(0, int(offset or 0))
        c = self.conn
        total = c.execute(f"SELECT COUNT(*) c FROM photos WHERE {where}", params).fetchone()["c"]
        rows = c.execute(
            f"SELECT * FROM photos WHERE {where} ORDER BY taken_at DESC, path ASC LIMIT ? OFFSET ?",
            (*params, limit, offset),
        ).fetchall()
        more = offset + limit < total
        return {
            "count": total,
            "results": [self._public(r) for r in rows],
            "truncated": more,
            "next_offset": offset + limit if more else None,
        }

    # ------------------------------------------------------------------ #
    # Search / similar / show / describe
    # ------------------------------------------------------------------ #
    def _embedded_rows(self, filters: dict) -> list[sqlite3.Row]:
        where, params = self._where(filters)
        return self.conn.execute(
            f"SELECT * FROM photos WHERE {where} AND embed_row IS NOT NULL AND embed_model = ?",
            (*params, self.embedder.name),
        ).fetchall()

    def _agent_notes(self, payload: dict) -> dict:
        payload["embedder"] = self.embedder.name
        if isinstance(self.embedder, FakeEmbedder):
            payload["note"] = FAKE_EMBEDDER_NOTE
        else:
            stale = self.conn.execute(
                "SELECT COUNT(*) c FROM photos WHERE missing = 0 AND "
                "(embed_row IS NULL OR embed_model IS NULL OR embed_model != ?)",
                (self.embedder.name,),
            ).fetchone()["c"]
            if stale:
                payload["note"] = (
                    f"{stale} photos are not analysed with the current model yet (indexing may be "
                    "running); they are missing from these results. Check photos_library for progress."
                )
        return payload

    def search(self, query: str, filters: dict | None = None, limit: int = 12, contact_sheet: bool = True) -> dict:
        if not isinstance(query, str) or not query.strip():
            raise ValidationError("query is required: describe the photo in English, e.g. 'dog on a beach'")
        query = query.strip()[:300]
        limit = _clamp_limit(limit, 12)
        rows = self._embedded_rows(filters or {})
        if not rows:
            return self._agent_notes({"query": query, "count": 0, "results": [], "has_more": False,
                                      "contact_sheet_jpeg_base64": None})

        qvec = self.embedder.embed_text(query)
        row_by_embed = {r["embed_row"]: r for r in rows}
        embed_rows, cos = self.vectors.scores(qvec, row_by_embed.keys())

        bm25: dict[str, float] = {}
        words = re.findall(r"\w+", query.lower())
        if words:
            safe_query = " OR ".join(f'"{w}"' for w in words)
            try:
                for r in self.conn.execute(
                    "SELECT photo_id, bm25(photos_fts) AS s FROM photos_fts WHERE photos_fts MATCH ?",
                    (safe_query,),
                ).fetchall():
                    bm25[r["photo_id"]] = r["s"]
            except sqlite3.OperationalError:
                bm25 = {}

        # hybrid = 0.8 * cosine_norm + 0.2 * bm25_norm (bm25: lower is better)
        cmin, cmax = (float(cos.min()), float(cos.max())) if len(cos) else (0.0, 0.0)
        bvals = list(bm25.values())
        bmin, bmax = (min(bvals), max(bvals)) if bvals else (0.0, 0.0)
        scored = []
        for er, cosine in zip(embed_rows, cos):
            r = row_by_embed[er]
            final = float(cosine)
            if bm25:
                cos_norm = (float(cosine) - cmin) / (cmax - cmin) if cmax > cmin else 1.0
                bm_norm = 0.0
                if r["id"] in bm25:
                    bm_norm = 1.0 - ((bm25[r["id"]] - bmin) / (bmax - bmin) if bmax > bmin else 0.0)
                final = 0.8 * cos_norm + 0.2 * bm_norm if r["id"] in bm25 else 0.8 * cos_norm
            scored.append((final, float(cosine), r))
        scored.sort(key=lambda t: (-t[0], t[2]["path"]))
        top = scored[:limit]

        results = []
        for n, (_, cosine, r) in enumerate(top, start=1):
            item = {"n": n, **self._public(r, score=cosine)}
            if r["id"] in bm25:
                item["caption_match"] = True
            results.append(item)
        payload: dict[str, Any] = {
            "query": query,
            "count": len(scored),
            "results": results,
            "has_more": len(scored) > limit,
        }
        payload["contact_sheet_jpeg_base64"] = (
            self._contact_sheet_for([r for _, _, r in top]) if contact_sheet and top else None
        )
        if contact_sheet and len(top) > SHEET_MAX_ITEMS:
            payload["contact_sheet_covers"] = SHEET_MAX_ITEMS
        return self._agent_notes(payload)

    # -- UI-only: translate a non-English query before embedding it -------- #
    TRANSLATE_PROMPT = (
        "Translate the following photo search query to a short, literal English "
        "CLIP search phrase. Reply with only the translated phrase, no quotes, "
        "no punctuation, no explanation.\n\nQuery: {text}"
    )

    def translate_search_enabled(self) -> bool:
        return dbmod.get_setting(self.conn, "translate_search", "true") != "false"

    def set_translate_search(self, enabled: bool) -> None:
        dbmod.set_setting(self.conn, "translate_search", "true" if enabled else "false")

    def search_translated(self, query: str, filters: dict | None = None, limit: int = 12, contact_sheet: bool = True) -> dict:
        """UI-only entry point: `search()` with an automatic English
        translation of a non-English query through the `llm` capability,
        when enabled. The MCP tool tells the agent to translate the query
        itself, so agent calls go straight to `search()` and are never
        translated twice."""
        original = query.strip() if isinstance(query, str) else query
        translated: str | None = None
        translate_error: str | None = None
        if isinstance(original, str) and original and self.translate_search_enabled():
            lang = detect_non_english(original)
            if lang:
                try:
                    result = self.backend.link.sync.chat(
                        [{"role": "user", "content": self.TRANSLATE_PROMPT.format(text=original)}],
                        max_tokens=60,
                        temperature=0.0,
                        capability="llm",
                    )
                    candidate = (result.text or "").strip().strip('"').strip("'")
                    if candidate:
                        translated = candidate
                except (Unavailable, BackendError) as exc:
                    translate_error = str(exc)
        payload = self.search(translated or query, filters, limit, contact_sheet)
        if translated:
            payload["original_query"] = original
            payload["translated_query"] = translated
        elif translate_error:
            payload["translate_error"] = translate_error
        return payload

    def similar(self, photo_id: str | None = None, path: str | None = None, limit: int = 12, contact_sheet: bool = True) -> dict:
        row = self._resolve_photo(photo_id, path)
        limit = _clamp_limit(limit, 12)
        if row["embed_row"] is None or row["embed_model"] != self.embedder.name:
            raise ValidationError("this photo has no embedding for the current model yet; wait for indexing to finish (see photos_library)")
        qvec = self.vectors.get(row["embed_row"])
        others = [r for r in self._embedded_rows({}) if r["id"] != row["id"]]
        row_by_embed = {r["embed_row"]: r for r in others}
        hits = self.vectors.search(qvec, row_by_embed.keys(), limit=limit)
        results = [{"n": n, **self._public(row_by_embed[er], score=s)} for n, (er, s) in enumerate(hits, start=1)]
        payload = {"photo_id": row["id"], "count": len(results), "results": results,
                   "has_more": len(others) > len(results)}
        payload["contact_sheet_jpeg_base64"] = (
            self._contact_sheet_for([row_by_embed[er] for er, _ in hits]) if contact_sheet and results else None
        )
        return self._agent_notes(payload)

    def _resolve_photo(self, photo_id: str | None, path: str | None) -> sqlite3.Row:
        c = self.conn
        if photo_id:
            photo_id = str(photo_id).strip().lower()
            row = c.execute("SELECT * FROM photos WHERE id = ?", (photo_id,)).fetchone() if ID_RE.match(photo_id) else None
            if not row:
                raise NotFoundError(
                    f"photo not found: {photo_id}. Use an 'id' value returned by photos_search or photos_similar."
                )
            return row
        if path:
            p = str(Path(os.path.abspath(Path(str(path).strip()).expanduser())))
            row = c.execute("SELECT * FROM photos WHERE path = ?", (p,)).fetchone()
            if not row and sys.platform == "win32":
                row = c.execute("SELECT * FROM photos WHERE path = ? COLLATE NOCASE", (p,)).fetchone()
            if not row:
                raise NotFoundError(f"no indexed photo at path: {path}")
            return row
        raise ValidationError("photo_id or path is required")

    def _contact_sheet_for(self, rows: list[sqlite3.Row], cols: int = 5, cell: int = 220) -> str | None:
        items = []
        for i, row in enumerate(rows[:SHEET_MAX_ITEMS], start=1):
            caption = row["taken_at"][:10] if row["taken_at"] else ""
            if row["city"]:
                caption = f"{caption} · {row['city']}"
            items.append(ContactSheetItem(thumb_path=thumb_path(self.settings.thumbs_dir, row["id"]), index=i, caption=caption))
        if not items:
            return None
        return base64.b64encode(render_contact_sheet(items, cols=cols, cell=cell)).decode("ascii")

    def render_preview(self, photo_id: str, size: int = 1600, max_bytes: int | None = None) -> bytes:
        """A JPEG of the original, orientation-corrected, long side <= size.
        Reads the original; never writes it."""
        from PIL import Image, ImageOps

        row = self._resolve_photo(photo_id, None)
        src = Path(row["path"])
        if not src.exists():
            raise NotFoundError(f"the original file is not reachable right now: {src}")
        size = max(64, min(int(size), 4096))
        with Image.open(src) as img:
            try:
                img.draft("RGB", (size, size))
            except Exception:  # noqa: BLE001
                pass
            img = ImageOps.exif_transpose(img)
            img = img.convert("RGB")
            img.thumbnail((size, size), Image.LANCZOS)
            if max_bytes:
                return encode_jpeg_under(img, max_bytes)
            import io

            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=88)
            return buf.getvalue()

    def show(self, ids: list[str], size: int = 768) -> dict:
        if not isinstance(ids, list) or not ids:
            raise ValidationError("ids is required: a list of 1-4 photo ids from photos_search")
        try:
            size = max(128, min(int(size), 1024))
        except (TypeError, ValueError):
            raise ValidationError("size must be a number of pixels (128-1024)") from None
        images, not_found, unreachable = [], [], []
        seen: list[str] = []
        for pid in ids:
            pid = str(pid).strip().lower()
            if pid not in seen:
                seen.append(pid)
        for pid in seen[:SHOW_MAX_IDS]:
            try:
                row = self._resolve_photo(pid, None)
                jpeg = self.render_preview(pid, size=size, max_bytes=SHOW_MAX_BYTES)
            except NotFoundError as exc:
                (unreachable if "not reachable" in str(exc) else not_found).append(pid)
                continue
            except Exception as exc:  # noqa: BLE001 - unreadable file: report, continue
                log.warning("photos_show could not render %s: %s", pid, exc)
                unreachable.append(pid)
                continue
            images.append({
                "id": pid,
                "path": row["path"],
                "taken_at": row["taken_at"],
                "jpeg_base64": base64.b64encode(jpeg).decode("ascii"),
            })
        out: dict[str, Any] = {"images": images, "not_found": not_found}
        if unreachable:
            out["unreadable"] = unreachable
        if len(seen) > SHOW_MAX_IDS:
            out["ignored_ids"] = seen[SHOW_MAX_IDS:]
        return out

    def describe(self, photo_id: str, caption: bool = False) -> dict:
        row = self._resolve_photo(photo_id, None)
        photo_id = row["id"]
        d = dict(row)
        caption_error = None
        if caption and not row["caption"]:
            result = self._captioner().caption(Path(row["path"]))
            if result.ok:
                self._store_caption(photo_id, result.caption)
                d["caption"] = result.caption
            else:
                caption_error = result.error
        out = self._public(row)
        for k in (
            "make", "model", "lens", "f_number", "exposure_time", "iso", "focal_length",
            "orientation", "gps_lat", "gps_lon", "city", "region", "country", "caption",
            "date_source",
        ):
            if d.get(k) is not None:
                out[k] = d[k]
        if caption_error:
            out["caption_error"] = caption_error
        if row["missing"]:
            out["missing"] = True
        return out

    def _store_caption(self, photo_id: str, text: str) -> None:
        c = self.conn
        c.execute("UPDATE photos SET caption = ? WHERE id = ?", (text, photo_id))
        rowid = c.execute("SELECT rowid FROM photos WHERE id = ?", (photo_id,)).fetchone()["rowid"]
        c.execute("DELETE FROM photos_fts WHERE photo_id = ?", (photo_id,))
        c.execute("INSERT INTO photos_fts(rowid, photo_id, caption) VALUES (?, ?, ?)", (rowid, photo_id, text))
        c.commit()

    def _captioner(self) -> LinkCaptioner:
        """The seam tests monkeypatch. Captions through Hoard Link's `vision`
        capability -- see argus_hoard/backend.py for how the legacy Ollama
        URL/model settings become that capability's explicit override."""
        return LinkCaptioner(lambda: self.backend.link)

    def start_caption_batch(self, limit: int = 500) -> str:
        limit = max(1, min(int(limit), 5000))
        WAIT_ROUND_S = 30.0
        MAX_WAIT_ROUNDS = 20  # ~10 minutes total before captioning anyway

        def run(handle: JobHandle) -> None:
            captioner = self._captioner()
            probe = captioner.test_connection()
            if not probe.ok:
                raise RuntimeError(probe.error)
            rows = self.conn.execute(
                "SELECT id, path FROM photos WHERE missing = 0 AND caption IS NULL ORDER BY taken_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            done = failed = 0
            for i, r in enumerate(rows, start=1):
                # Good citizen: a batch job yields to whatever the owner is
                # doing with the shared model, instead of racing it.
                for _ in range(MAX_WAIT_ROUNDS):
                    if self.backend.link.sync.wait_idle("vision", max_wait_s=WAIT_ROUND_S):
                        break
                    handle.progress(
                        (i - 1) / max(1, len(rows)),
                        f"the shared vision model is busy; waiting ({done}/{len(rows)} captioned so far)",
                    )
                result = captioner.caption(Path(r["path"]))
                if result.ok:
                    self._store_caption(r["id"], result.caption)
                    done += 1
                else:
                    failed += 1
                handle.progress(i / max(1, len(rows)), f"captioned {done}/{len(rows)}, {failed} failed")
            handle.set_stats({"captioned": done, "failed": failed})

        return self.jobs.start("captions", run)

    # ------------------------------------------------------------------ #
    # Shared model backend (Hoard Link)
    # ------------------------------------------------------------------ #
    def backend_status(self) -> dict:
        """GET /api/backend: Hoard Link's resolution for every capability,
        plus the one thing it does not know about -- the CLIP image search
        model, which is always local and never shared (it is not a chat/
        embeddings-text model Hoard Link's capabilities cover)."""
        status = self.backend.status()
        status["image_search"] = {
            "engine": "local CLIP (ONNX Runtime), not part of the shared backend",
            "active": self.embedder.name,
            "semantic": not isinstance(self.embedder, FakeEmbedder),
        }
        return status

    # ------------------------------------------------------------------ #
    # Model and geodata (explicit, user-triggered downloads)
    # ------------------------------------------------------------------ #
    def model_status(self) -> dict:
        state = ClipEmbedder.cache_state(self.settings.models_dir)
        return {
            "active": self.embedder.name,
            "clip_downloaded": state["image"] and state["text"],
            "cache_bytes": state["bytes"],
            "download_size_hint_mb": 600,
            "downloading": bool(self.jobs.running("model_download")),
        }

    def start_model_download(self) -> str:
        running = self.jobs.running("model_download")
        if running:
            return running[0]["id"]

        def run(handle: JobHandle) -> None:
            with self._model_lock:
                handle.progress(0.05, "downloading the CLIP model from Hugging Face (about 600 MB)")
                clip = ClipEmbedder(self.settings.models_dir, local_only=False)
            handle.progress(0.9, "model ready; waiting for any running scan, then re-embedding")
            # Swap only between index runs: a run in progress keeps the
            # embedder it started with, so its vectors are never labelled
            # with the other model's name.
            with self._index_lock:
                self.embedder = clip
            self._run_index(None, handle)

        return self.jobs.start("model_download", run)

    def start_geodata_download(self) -> str:
        def run(handle: JobHandle) -> None:
            handle.progress(0.05, "downloading GeoNames cities1000 (about 10 MB)")
            download_geonames(self.settings.geodata_dir)
            self.geocoder = ReverseGeocoder(self.settings.geodata_dir)
            handle.progress(0.6, "re-geocoding photos with GPS")
            c = self.conn
            rows = c.execute("SELECT id, gps_lat, gps_lon FROM photos WHERE gps_lat IS NOT NULL").fetchall()
            for r in rows:
                m = self.geocoder.lookup(r["gps_lat"], r["gps_lon"])
                if m:
                    c.execute(
                        "UPDATE photos SET city = ?, region = ?, country = ? WHERE id = ?",
                        (m.city, m.region, m.country, r["id"]),
                    )
            c.commit()
            handle.set_stats({"regeocoded": len(rows)})

        return self.jobs.start("geodata_download", run)

    # ------------------------------------------------------------------ #
    # Duplicates / timeline / places / library status
    # ------------------------------------------------------------------ #
    def duplicates(self, kind: str = "exact", limit: int = 10) -> dict:
        if kind not in ("exact", "near"):
            raise ValidationError(f"kind must be 'exact' or 'near', got {kind!r}")
        limit = _clamp_limit(limit, 10)
        rows = self.conn.execute("SELECT * FROM photos WHERE missing = 0").fetchall()
        photo_rows = [
            PhotoRow(
                id=r["id"], path=r["path"], size=r["size"], width=r["width"], height=r["height"],
                taken_at=r["taken_at"], content_hash=r["content_hash"],
                phash=int(r["phash"], 16) if r["phash"] else None,
            )
            for r in rows
        ]
        by_id = {r["id"]: r for r in rows}
        groups = exact_duplicate_groups(photo_rows) if kind == "exact" else near_duplicate_groups(photo_rows)

        def reclaim(g) -> int:
            return sum(by_id[p]["size"] for p in g.photo_ids if p != g.keeper_id)

        groups.sort(key=lambda g: (-reclaim(g), by_id[g.keeper_id]["path"]))
        out = []
        for g in groups[:limit]:
            keeper_first = [g.keeper_id] + [p for p in g.photo_ids if p != g.keeper_id]
            out.append({
                "kind": g.kind,
                "keeper_id": g.keeper_id,
                "max_distance": g.max_distance,
                "reclaimable_bytes": reclaim(g),
                "photos": [self._public(by_id[pid]) for pid in keeper_first],
            })
        return {
            "kind": kind,
            "count": len(out),
            "total_groups": len(groups),
            "has_more": len(groups) > limit,
            "reclaimable_bytes_total": sum(reclaim(g) for g in groups),
            "groups": out,
        }

    def timeline(self, year: int | None = None, samples: int = 0) -> dict:
        if year is not None:
            year = self.validate_filters({"year": year})["year"]
        c = self.conn
        rows = c.execute(
            "SELECT substr(taken_at,1,4) y, substr(taken_at,6,2) m, COUNT(*) c FROM photos "
            "WHERE missing = 0 AND taken_at IS NOT NULL GROUP BY y, m ORDER BY y, m"
        ).fetchall()
        by_year: dict[str, dict[str, int]] = {}
        for r in rows:
            by_year.setdefault(r["y"], {})[r["m"]] = r["c"]
        today = dt.date.today()
        month_day = f"{today.month:02d}-{today.day:02d}"
        otd_rows = c.execute(
            "SELECT * FROM photos WHERE missing = 0 AND substr(taken_at,6,5) = ? "
            "AND substr(taken_at,1,4) < ? ORDER BY taken_at DESC",
            (month_day, f"{today.year:04d}"),
        ).fetchall()
        result: dict[str, Any] = {
            "on_this_day": [
                {"id": r["id"], "taken_at": r["taken_at"], "place": r["city"],
                 "thumbnail_url": f"/api/photos/{r['id']}/thumbnail"}
                for r in otd_rows[:10]
            ],
            "on_this_day_count": len(otd_rows),
        }
        if year is None:
            result["years"] = {y: sum(m.values()) for y, m in by_year.items()}
            result["months"] = by_year
        else:
            result["year"] = year
            result["months"] = {str(year): by_year.get(f"{year:04d}", {})}
            result["total"] = sum(result["months"][str(year)].values())
        if samples:
            sample_map: dict[str, list[str]] = {}
            for y, months in result["months"].items():
                for m in months:
                    ids = c.execute(
                        "SELECT id FROM photos WHERE missing = 0 AND substr(taken_at,1,7) = ? "
                        "ORDER BY taken_at LIMIT ?",
                        (f"{y}-{m}", int(samples)),
                    ).fetchall()
                    sample_map[f"{y}-{m}"] = [r["id"] for r in ids]
            result["samples"] = sample_map
        return result

    def places(self) -> dict:
        rows = self.conn.execute(
            "SELECT country, city, COUNT(*) c, MIN(id) sample_id FROM photos "
            "WHERE missing = 0 AND city IS NOT NULL GROUP BY country, city ORDER BY country, c DESC"
        ).fetchall()
        by_country: dict[str, list[dict]] = {}
        for r in rows:
            by_country.setdefault(r["country"] or "?", []).append(
                {"city": r["city"], "count": r["c"], "sample_thumbnail_url": f"/api/photos/{r['sample_id']}/thumbnail"}
            )
        return {"countries": by_country}

    def library_status(self, compact: bool = False) -> dict:
        c = self.conn
        total = c.execute("SELECT COUNT(*) c FROM photos WHERE missing = 0").fetchone()["c"]
        missing = c.execute("SELECT COUNT(*) c FROM photos WHERE missing = 1").fetchone()["c"]
        stale = c.execute(
            "SELECT COUNT(*) c FROM photos WHERE missing = 0 AND "
            "(embed_row IS NULL OR embed_model IS NULL OR embed_model != ?)",
            (self.embedder.name,),
        ).fetchone()["c"]
        jobs = self.jobs.list(limit=5)
        status = {
            "roots": self.list_roots(),
            "photo_count": total,
            "missing_count": missing,
            "embedder": {
                "name": self.embedder.name,
                "dim": self.embedder.dim,
                "semantic": not isinstance(self.embedder, FakeEmbedder),
                "stale_photos": stale,
            },
            "geocoder_source": self.geocoder.source,
            "heic_support": HEIF_AVAILABLE,
            "indexing": any(j["status"] == "running" and j["kind"] in ("index", "model_download") for j in jobs),
            "recent_jobs": jobs,
            "ollama": {
                "base_url": dbmod.get_setting(c, "ollama_base_url", DEFAULT_BASE_URL),
                "model": dbmod.get_setting(c, "ollama_model", DEFAULT_MODEL),
            },
        }
        if compact:
            status["roots"] = [
                {"id": r["id"], "path": r["path"], "photo_count": r["photo_count"], "exists": r["exists"]}
                for r in status["roots"]
            ]
            status["recent_jobs"] = [
                {k: j.get(k) for k in ("id", "kind", "status", "progress", "message")} for j in jobs[:3]
            ]
            status.pop("ollama")
            if isinstance(self.embedder, FakeEmbedder):
                status["note"] = FAKE_EMBEDDER_NOTE
        return status

    # ------------------------------------------------------------------ #
    # Albums
    # ------------------------------------------------------------------ #
    def album(self, name: str, photo_ids: list[str] | None = None, created_by: str = "agent") -> dict:
        if not isinstance(name, str) or not name.strip():
            raise ValidationError("name is required: a short album title such as 'Lisbon 2024'")
        name = " ".join(name.split())[:100]
        photo_ids = list(photo_ids or [])
        if len(photo_ids) > 500:
            raise ValidationError("at most 500 photo_ids per call; call again to add more")
        c = self.conn
        row = c.execute("SELECT * FROM albums WHERE name = ? COLLATE NOCASE", (name,)).fetchone()
        created = False
        if row:
            album_id = row["id"]
        else:
            album_id = uuid.uuid4().hex
            created = True
            c.execute(
                "INSERT INTO albums(id, name, created_at, created_by) VALUES (?, ?, ?, ?)",
                (album_id, name, _now(), "user" if created_by == "user" else "agent"),
            )
        added, unknown = 0, []
        for pid in photo_ids:
            pid_norm = str(pid).strip().lower()
            if ID_RE.match(pid_norm) and c.execute("SELECT 1 FROM photos WHERE id = ?", (pid_norm,)).fetchone():
                cur = c.execute(
                    "INSERT OR IGNORE INTO album_photos(album_id, photo_id, added_at) VALUES (?, ?, ?)",
                    (album_id, pid_norm, _now()),
                )
                added += cur.rowcount
            else:
                unknown.append(str(pid))
        c.commit()
        album = self.get_album(album_id, limit=10)
        album.update({"created": created, "added": added, "unknown_ids": unknown})
        return album

    def remove_from_album(self, album_id: str, photo_ids: list[str]) -> dict:
        """UI-only: the agent can create and extend albums, not shrink them."""
        c = self.conn
        for pid in photo_ids:
            c.execute("DELETE FROM album_photos WHERE album_id = ? AND photo_id = ?", (album_id, pid))
        c.commit()
        return self.get_album(album_id)

    def delete_album(self, album_id: str) -> None:
        """UI-only. Deletes the collection, never the photos in it."""
        c = self.conn
        c.execute("DELETE FROM album_photos WHERE album_id = ?", (album_id,))
        c.execute("DELETE FROM albums WHERE id = ?", (album_id,))
        c.commit()

    def list_albums(self) -> list[dict]:
        rows = self.conn.execute(
            "SELECT a.*, (SELECT COUNT(*) FROM album_photos ap JOIN photos p ON p.id = ap.photo_id "
            "WHERE ap.album_id = a.id) AS photo_count, "
            "(SELECT ap.photo_id FROM album_photos ap WHERE ap.album_id = a.id ORDER BY ap.added_at LIMIT 1) AS cover_id "
            "FROM albums a ORDER BY a.created_at DESC"
        ).fetchall()
        return [
            {
                "id": r["id"], "name": r["name"], "created_at": r["created_at"], "created_by": r["created_by"],
                "photo_count": r["photo_count"],
                "cover_thumbnail_url": f"/api/photos/{r['cover_id']}/thumbnail" if r["cover_id"] else None,
            }
            for r in rows
        ]

    def get_album(self, album_id: str, limit: int | None = None) -> dict:
        c = self.conn
        row = c.execute("SELECT * FROM albums WHERE id = ?", (album_id,)).fetchone()
        if not row:
            raise NotFoundError(f"album not found: {album_id}")
        photos = c.execute(
            "SELECT p.* FROM photos p JOIN album_photos ap ON ap.photo_id = p.id "
            "WHERE ap.album_id = ? ORDER BY ap.added_at DESC",
            (album_id,),
        ).fetchall()
        shown = photos if limit is None else photos[:limit]
        out = {
            "id": row["id"],
            "name": row["name"],
            "created_at": row["created_at"],
            "created_by": row["created_by"],
            "photo_count": len(photos),
            "photos": [self._public(p) for p in shown],
        }
        if limit is not None:
            out["has_more"] = len(photos) > limit
        return out

    # ------------------------------------------------------------------ #
    # Agent audit log
    # ------------------------------------------------------------------ #
    def log_agent_call(self, tool: str, args_summary: str, ok: bool, duration_ms: float, error: str | None) -> None:
        c = self.conn
        c.execute(
            "INSERT INTO agent_calls(tool, args_summary, ok, duration_ms, error, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (tool, args_summary[:500], 1 if ok else 0, duration_ms, (error or None) and error[:500], _now()),
        )
        c.commit()

    def recent_agent_calls(self, limit: int = 20) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM agent_calls ORDER BY id DESC LIMIT ?", (max(1, min(int(limit), 200)),)
        ).fetchall()
        return [dict(r) for r in rows]
