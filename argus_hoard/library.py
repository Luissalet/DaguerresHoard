"""The core engine: indexing pipeline plus every read/write operation used
by both the HTTP API and the MCP adapter. No FastAPI imports here -- this
module is plain Python so it can be unit-tested directly.
"""
from __future__ import annotations

import base64
import datetime as dt
import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from . import db as dbmod
from .captions import DEFAULT_BASE_URL, DEFAULT_MODEL, OllamaCaptioner
from .config import EMBED_DIM, Settings
from .contact_sheet import ContactSheetItem, render_contact_sheet
from .duplicates import PhotoRow, exact_duplicate_groups, near_duplicate_groups
from .embeddings import ClipEmbedder, Embedder, FakeEmbedder, VectorStore
from .geocode import ReverseGeocoder
from .hashing import content_hash
from .jobs import JobHandle, JobManager
from .metadata import extract_metadata
from .phash import compute_phash
from .scanning import stat_signature, walk_images
from .thumbnails import make_thumbnail, thumb_path

EMBED_BATCH = 32


class NotFoundError(Exception):
    pass


class ValidationError(Exception):
    pass


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def select_embedder(settings: Settings) -> Embedder:
    try:
        if ClipEmbedder.is_cached(settings.models_dir):
            return ClipEmbedder(settings.models_dir)
    except Exception:
        pass
    return FakeEmbedder()


class Library:
    def __init__(self, settings: Settings, conn: sqlite3.Connection | None = None, embedder: Embedder | None = None):
        settings.ensure_dirs()
        self.settings = settings
        self.conn = conn or dbmod.connect(settings.db_path)
        self.embedder = embedder or select_embedder(settings)
        self.vectors = VectorStore(settings.vectors_path, dim=EMBED_DIM)
        self.geocoder = ReverseGeocoder(settings.geodata_dir if any(settings.geodata_dir.glob("*.txt")) else None)
        self.jobs = JobManager(self.conn)

    # ------------------------------------------------------------------ #
    # Roots / indexing
    # ------------------------------------------------------------------ #
    def add_root(self, path: str, added_by: str = "user", excluded_globs: list[str] | None = None) -> dict:
        p = Path(path).expanduser()
        if not p.is_absolute():
            raise ValidationError(f"path must be absolute: {path}")
        if not p.is_dir():
            raise ValidationError(f"not a directory: {path}")
        cur = self.conn.execute(
            "INSERT OR IGNORE INTO roots(path, excluded_globs, created_at, added_by) VALUES (?, ?, ?, ?)",
            (str(p), json.dumps(excluded_globs or []), _now(), added_by),
        )
        self.conn.commit()
        row = self.conn.execute("SELECT * FROM roots WHERE path = ?", (str(p),)).fetchone()
        return dict(row)

    def remove_root(self, root_id: int) -> None:
        """UI-only (human) operation -- never exposed as an agent tool."""
        self.conn.execute("DELETE FROM photos WHERE root_id = ?", (root_id,))
        self.conn.execute("DELETE FROM roots WHERE id = ?", (root_id,))
        self.conn.commit()

    def list_roots(self) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM roots ORDER BY id").fetchall()
        out = []
        for r in rows:
            count = self.conn.execute(
                "SELECT COUNT(*) c FROM photos WHERE root_id = ? AND missing = 0", (r["id"],)
            ).fetchone()["c"]
            d = dict(r)
            d["excluded_globs"] = json.loads(d["excluded_globs"])
            d["photo_count"] = count
            out.append(d)
        return out

    def start_scan(self, root_id: int | None = None) -> str:
        return self.jobs.start("index", lambda handle: self._run_index(root_id, handle))

    def _run_index(self, root_id: int | None, handle: JobHandle) -> None:
        query = "SELECT * FROM roots"
        params: tuple = ()
        if root_id is not None:
            query += " WHERE id = ?"
            params = (root_id,)
        roots = [dict(r) for r in self.conn.execute(query, params).fetchall()]
        plan: list[tuple[dict, Path]] = []
        for root in roots:
            excluded = json.loads(root["excluded_globs"])
            for path in walk_images(Path(root["path"]), excluded):
                plan.append((root, path))
        seen_paths: set[str] = {str(p) for _, p in plan}
        total = len(plan) or 1
        pending_embed: list[tuple[str, Path]] = []  # (photo_id, thumb_path)
        for i, (root, path) in enumerate(plan):
            photo_id = self._index_one(root, path, pending_embed)
            if i % 4 == 0 or i == total - 1:
                handle.progress(0.85 * (i + 1) / total, f"{i + 1}/{total} files in {root['path']}")

        # Batch-embed everything that needs it.
        for start in range(0, len(pending_embed), EMBED_BATCH):
            batch = pending_embed[start : start + EMBED_BATCH]
            vecs = self.embedder.embed_images([tp for _, tp in batch])
            for (photo_id, _), vec in zip(batch, vecs):
                self._store_embedding(photo_id, vec)
            handle.progress(0.85 + 0.15 * min(1.0, (start + len(batch)) / max(1, len(pending_embed))), "embedding")

        # Mark rows under scanned roots whose file disappeared and was not
        # matched as moved elsewhere.
        for root in roots:
            rows = self.conn.execute(
                "SELECT id, path FROM photos WHERE root_id = ? AND missing = 0", (root["id"],)
            ).fetchall()
            for row in rows:
                if row["path"] not in seen_paths and not Path(row["path"]).exists():
                    self.conn.execute("UPDATE photos SET missing = 1 WHERE id = ?", (row["id"],))
        self.conn.commit()
        handle.progress(1.0, f"indexed {len(plan)} files")

    def _index_one(self, root: dict, path: Path, pending_embed: list[tuple[str, Path]]) -> str:
        size, mtime_ns = stat_signature(path)
        existing = self.conn.execute("SELECT * FROM photos WHERE path = ?", (str(path),)).fetchone()
        if existing and existing["size"] == size and existing["mtime_ns"] == mtime_ns and not existing["missing"]:
            return existing["id"]  # unchanged: skip entirely, no hashing needed

        file_hash = content_hash(path)

        if existing and existing["content_hash"] == file_hash:
            self.conn.execute(
                "UPDATE photos SET size = ?, mtime_ns = ?, missing = 0 WHERE id = ?",
                (size, mtime_ns, existing["id"]),
            )
            self.conn.commit()
            return existing["id"]

        moved = self.conn.execute(
            "SELECT * FROM photos WHERE content_hash = ? AND path != ?", (file_hash, str(path))
        ).fetchall()
        for m in moved:
            if not Path(m["path"]).exists():
                self.conn.execute(
                    "UPDATE photos SET path = ?, root_id = ?, size = ?, mtime_ns = ?, missing = 0 WHERE id = ?",
                    (str(path), root["id"], size, mtime_ns, m["id"]),
                )
                self.conn.commit()
                return m["id"]

        photo_id = existing["id"] if existing else uuid.uuid4().hex
        meta = extract_metadata(path)
        dest = thumb_path(self.settings.thumbs_dir, photo_id)
        make_thumbnail(path, dest)
        phash_val = compute_phash(path)

        city = region = country = None
        if meta.gps_lat is not None and meta.gps_lon is not None:
            match = self.geocoder.lookup(meta.gps_lat, meta.gps_lon)
            if match:
                city, region, country = match.city, match.region, match.country

        fields = dict(
            id=photo_id,
            root_id=root["id"],
            path=str(path),
            size=size,
            mtime_ns=mtime_ns,
            content_hash=file_hash,
            phash=f"{phash_val:016x}",
            width=meta.width,
            height=meta.height,
            taken_at=meta.taken_at,
            date_source=meta.date_source,
            make=meta.make,
            model=meta.model,
            lens=meta.lens,
            f_number=meta.f_number,
            exposure_time=meta.exposure_time,
            iso=meta.iso,
            focal_length=meta.focal_length,
            orientation=meta.orientation,
            gps_lat=meta.gps_lat,
            gps_lon=meta.gps_lon,
            city=city,
            region=region,
            country=country,
            embed_row=existing["embed_row"] if existing else None,
            indexed_at=_now(),
            missing=0,
        )
        if existing:
            set_clause = ", ".join(f"{k} = :{k}" for k in fields if k not in ("id",))
            self.conn.execute(f"UPDATE photos SET {set_clause} WHERE id = :id", fields)
        else:
            cols = ", ".join(fields)
            placeholders = ", ".join(f":{k}" for k in fields)
            self.conn.execute(f"INSERT INTO photos ({cols}) VALUES ({placeholders})", fields)
        self.conn.commit()
        pending_embed.append((photo_id, dest))
        return photo_id

    def _store_embedding(self, photo_id: str, vec) -> None:
        row = self.conn.execute("SELECT embed_row FROM photos WHERE id = ?", (photo_id,)).fetchone()
        if row and row["embed_row"] is not None:
            self.vectors.update(row["embed_row"], vec)
        else:
            new_row = self.vectors.append(vec)
            self.conn.execute("UPDATE photos SET embed_row = ? WHERE id = ?", (new_row, photo_id))
        self.conn.commit()

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
            d["score"] = round(score, 4)
        return d

    def _filtered_rows(self, filters: dict) -> list[sqlite3.Row]:
        clauses = ["missing = 0"]
        params: list[Any] = []
        if filters.get("taken_after"):
            clauses.append("taken_at >= ?")
            params.append(filters["taken_after"])
        if filters.get("taken_before"):
            clauses.append("taken_at <= ?")
            params.append(filters["taken_before"])
        if filters.get("year"):
            clauses.append("substr(taken_at, 1, 4) = ?")
            params.append(str(filters["year"]))
        if filters.get("month"):
            clauses.append("substr(taken_at, 6, 2) = ?")
            params.append(f"{int(filters['month']):02d}")
        if filters.get("place"):
            clauses.append("(city LIKE ? OR country LIKE ?)")
            like = f"%{filters['place']}%"
            params += [like, like]
        if filters.get("folder"):
            clauses.append("path LIKE ?")
            params.append(f"%{filters['folder']}%")
        if filters.get("camera"):
            clauses.append("(model LIKE ? OR make LIKE ?)")
            like = f"%{filters['camera']}%"
            params += [like, like]
        if filters.get("orientation") == "landscape":
            clauses.append("width >= height")
        elif filters.get("orientation") == "portrait":
            clauses.append("height > width")
        if filters.get("min_megapixels"):
            clauses.append("(width * height) >= ?")
            params.append(float(filters["min_megapixels"]) * 1_000_000)
        if filters.get("has_gps"):
            clauses.append("gps_lat IS NOT NULL")
        sql = f"SELECT * FROM photos WHERE {' AND '.join(clauses)}"
        return self.conn.execute(sql, params).fetchall()

    def list_photos(self, filters: dict | None = None, limit: int = 60, offset: int = 0) -> dict:
        """Plain chronological grid listing for the UI (no embedding search)."""
        filters = filters or {}
        rows = self._filtered_rows(filters)
        rows = sorted(rows, key=lambda r: r["taken_at"] or "", reverse=True)
        total = len(rows)
        page = rows[offset : offset + limit]
        return {
            "count": total,
            "results": [self._public(r) for r in page],
            "truncated": offset + limit < total,
            "next_offset": offset + limit if offset + limit < total else None,
        }

    # ------------------------------------------------------------------ #
    # Search / similar / show / describe
    # ------------------------------------------------------------------ #
    def search(self, query: str, filters: dict | None = None, limit: int = 12, contact_sheet: bool = True) -> dict:
        filters = filters or {}
        rows = [r for r in self._filtered_rows(filters) if r["embed_row"] is not None]
        if not rows:
            return {"query": query, "count": 0, "results": [], "truncated": False, "contact_sheet_jpeg_base64": None}

        qvec = self.embedder.embed_text(query)
        row_by_embed = {r["embed_row"]: r for r in rows}
        cosine_hits = self.vectors.search(qvec, row_by_embed.keys(), limit=max(limit * 4, limit))

        has_captions = any(r["caption"] for r in rows)
        bm25_scores: dict[str, float] = {}
        if has_captions and query.strip():
            try:
                safe_query = " OR ".join(f'"{w}"' for w in query.split() if w)
                if safe_query:
                    for r in self.conn.execute(
                        "SELECT photo_id, bm25(photos_fts) AS s FROM photos_fts WHERE photos_fts MATCH ?",
                        (safe_query,),
                    ).fetchall():
                        bm25_scores[r["photo_id"]] = r["s"]
            except sqlite3.OperationalError:
                bm25_scores = {}

        scored = []
        cos_values = [c for _, c in cosine_hits] or [0.0]
        cmin, cmax = min(cos_values), max(cos_values)
        bm_values = list(bm25_scores.values()) or [0.0]
        bmin, bmax = min(bm_values), max(bm_values)
        for embed_row, cos in cosine_hits:
            r = row_by_embed[embed_row]
            cos_norm = (cos - cmin) / (cmax - cmin) if cmax > cmin else 1.0
            if has_captions and r["id"] in bm25_scores:
                raw = bm25_scores[r["id"]]
                bm_norm = 1.0 - ((raw - bmin) / (bmax - bmin) if bmax > bmin else 0.0)
                final = 0.8 * cos_norm + 0.2 * bm_norm
            else:
                final = cos_norm if not has_captions else 0.8 * cos_norm
            scored.append((final, r))
        scored.sort(key=lambda t: -t[0])
        top = scored[:limit]

        results = [self._public(r, score=s) for s, r in top]
        payload: dict[str, Any] = {
            "query": query,
            "count": len(scored),
            "results": results,
            "truncated": len(scored) > limit,
        }
        payload["contact_sheet_jpeg_base64"] = (
            self._contact_sheet_for(top) if contact_sheet and top else None
        )
        return payload

    def similar(self, photo_id: str | None = None, path: str | None = None, limit: int = 12, contact_sheet: bool = True) -> dict:
        row = self._resolve_photo(photo_id, path)
        if row["embed_row"] is None:
            raise ValidationError("photo has no embedding yet (still indexing?)")
        qvec = self.vectors.get(row["embed_row"])
        all_rows = self.conn.execute("SELECT * FROM photos WHERE missing = 0 AND embed_row IS NOT NULL").fetchall()
        row_by_embed = {r["embed_row"]: r for r in all_rows}
        hits = self.vectors.search(qvec, row_by_embed.keys(), limit=limit + 1)
        hits = [(er, s) for er, s in hits if row_by_embed[er]["id"] != row["id"]][:limit]
        results = [self._public(row_by_embed[er], score=s) for er, s in hits]
        payload = {"photo_id": row["id"], "count": len(results), "results": results}
        payload["contact_sheet_jpeg_base64"] = (
            self._contact_sheet_for([(s, row_by_embed[er]) for er, s in hits]) if contact_sheet and results else None
        )
        return payload

    def _resolve_photo(self, photo_id: str | None, path: str | None) -> sqlite3.Row:
        if photo_id:
            row = self.conn.execute("SELECT * FROM photos WHERE id = ?", (photo_id,)).fetchone()
        elif path:
            row = self.conn.execute("SELECT * FROM photos WHERE path = ?", (str(Path(path)),)).fetchone()
        else:
            raise ValidationError("photo_id or path is required")
        if not row:
            raise NotFoundError(f"photo not found: {photo_id or path}")
        return row

    def _contact_sheet_for(self, scored_rows: list[tuple[float, sqlite3.Row]], cols: int = 5, cell: int = 220) -> str | None:
        items = []
        for i, (_, row) in enumerate(scored_rows, start=1):
            tp = thumb_path(self.settings.thumbs_dir, row["id"])
            caption = row["taken_at"][:10] if row["taken_at"] else ""
            if row["city"]:
                caption = f"{caption} · {row['city']}"
            items.append(ContactSheetItem(thumb_path=tp, index=i, caption=caption))
        if not items:
            return None
        jpeg = render_contact_sheet(items, cols=cols, cell=cell)
        return base64.b64encode(jpeg).decode("ascii")

    def show(self, ids: list[str], size: int = 768) -> list[dict]:
        out = []
        for pid in ids[:4]:
            row = self.conn.execute("SELECT * FROM photos WHERE id = ?", (pid,)).fetchone()
            if not row:
                continue
            from PIL import Image, ImageOps

            src = Path(row["path"])
            if not src.exists():
                continue
            with Image.open(src) as img:
                img = ImageOps.exif_transpose(img).convert("RGB")
                img.thumbnail((size, size))
                import io

                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=85)
                out.append({"id": pid, "jpeg_base64": base64.b64encode(buf.getvalue()).decode("ascii")})
        return out

    def describe(self, photo_id: str, caption: bool = False) -> dict:
        row = self._resolve_photo(photo_id, None)
        d = dict(row)
        d.pop("embed_row", None)
        if caption and not row["caption"]:
            captioner = self._captioner()
            result = captioner.caption(Path(row["path"]))
            if result.ok:
                self.conn.execute("UPDATE photos SET caption = ? WHERE id = ?", (result.caption, photo_id))
                photo_rowid = self.conn.execute(
                    "SELECT rowid FROM photos WHERE id = ?", (photo_id,)
                ).fetchone()["rowid"]
                self.conn.execute("DELETE FROM photos_fts WHERE rowid = ?", (photo_rowid,))
                self.conn.execute(
                    "INSERT INTO photos_fts(rowid, photo_id, caption) VALUES (?, ?, ?)",
                    (photo_rowid, photo_id, result.caption),
                )
                self.conn.commit()
                d["caption"] = result.caption
            else:
                d["caption_error"] = result.error
        return self._public(row) | {
            k: d.get(k)
            for k in (
                "make", "model", "lens", "f_number", "exposure_time", "iso", "focal_length",
                "orientation", "gps_lat", "gps_lon", "region", "country", "city", "caption",
                "date_source", "content_hash", "indexed_at",
            )
        } | ({"caption_error": d["caption_error"]} if "caption_error" in d else {})

    def _captioner(self) -> OllamaCaptioner:
        base_url = dbmod.get_setting(self.conn, "ollama_base_url", DEFAULT_BASE_URL)
        model = dbmod.get_setting(self.conn, "ollama_model", DEFAULT_MODEL)
        return OllamaCaptioner(base_url=base_url, model=model)

    # ------------------------------------------------------------------ #
    # Duplicates / timeline / library status
    # ------------------------------------------------------------------ #
    def duplicates(self, kind: str = "exact", limit: int = 10) -> dict:
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
        groups = groups[:limit]
        out = []
        for g in groups:
            out.append(
                {
                    "kind": g.kind,
                    "keeper_id": g.keeper_id,
                    "max_distance": g.max_distance,
                    "photos": [self._public(by_id[pid]) for pid in g.photo_ids],
                }
            )
        return {"kind": kind, "count": len(out), "groups": out}

    def timeline(self, year: int | None = None) -> dict:
        rows = self.conn.execute(
            "SELECT substr(taken_at,1,4) y, substr(taken_at,6,2) m, COUNT(*) c FROM photos "
            "WHERE missing = 0 AND taken_at IS NOT NULL GROUP BY y, m ORDER BY y, m"
        ).fetchall()
        by_year: dict[str, dict[str, int]] = {}
        for r in rows:
            by_year.setdefault(r["y"], {})[r["m"]] = r["c"]
        on_this_day = []
        today = dt.date.today()
        month_day = f"{today.month:02d}-{today.day:02d}"
        for r in self.conn.execute(
            "SELECT id, taken_at, city, country FROM photos WHERE missing = 0 AND "
            "substr(taken_at,6,5) = ? ORDER BY taken_at",
            (month_day,),
        ).fetchall():
            on_this_day.append({"id": r["id"], "taken_at": r["taken_at"], "place": r["city"]})
        result = {"years": by_year, "on_this_day": on_this_day}
        if year:
            result["year"] = by_year.get(str(year), {})
        return result

    def library_status(self) -> dict:
        total = self.conn.execute("SELECT COUNT(*) c FROM photos WHERE missing = 0").fetchone()["c"]
        missing = self.conn.execute("SELECT COUNT(*) c FROM photos WHERE missing = 1").fetchone()["c"]
        recent_jobs = self.jobs.list(limit=5)
        return {
            "roots": self.list_roots(),
            "photo_count": total,
            "missing_count": missing,
            "embedder": {"name": self.embedder.name, "dim": self.embedder.dim},
            "geocoder_source": self.geocoder.source,
            "recent_jobs": recent_jobs,
            "ollama": {
                "base_url": dbmod.get_setting(self.conn, "ollama_base_url", DEFAULT_BASE_URL),
                "model": dbmod.get_setting(self.conn, "ollama_model", DEFAULT_MODEL),
            },
        }

    # ------------------------------------------------------------------ #
    # Albums
    # ------------------------------------------------------------------ #
    def album(self, name: str, photo_ids: list[str]) -> dict:
        row = self.conn.execute("SELECT * FROM albums WHERE name = ?", (name,)).fetchone()
        if row:
            album_id = row["id"]
        else:
            album_id = uuid.uuid4().hex
            self.conn.execute(
                "INSERT INTO albums(id, name, created_at, created_by) VALUES (?, ?, ?, 'agent')",
                (album_id, name, _now()),
            )
        added = 0
        for pid in photo_ids:
            if self.conn.execute("SELECT 1 FROM photos WHERE id = ?", (pid,)).fetchone():
                cur = self.conn.execute(
                    "INSERT OR IGNORE INTO album_photos(album_id, photo_id, added_at) VALUES (?, ?, ?)",
                    (album_id, pid, _now()),
                )
                added += cur.rowcount
        self.conn.commit()
        return self.get_album(album_id) | {"added": added}

    def list_albums(self) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM albums ORDER BY created_at DESC").fetchall()
        out = []
        for r in rows:
            count = self.conn.execute(
                "SELECT COUNT(*) c FROM album_photos WHERE album_id = ?", (r["id"],)
            ).fetchone()["c"]
            out.append({"id": r["id"], "name": r["name"], "created_at": r["created_at"], "photo_count": count})
        return out

    def get_album(self, album_id: str) -> dict:
        row = self.conn.execute("SELECT * FROM albums WHERE id = ?", (album_id,)).fetchone()
        if not row:
            raise NotFoundError(f"album not found: {album_id}")
        photos = self.conn.execute(
            "SELECT p.* FROM photos p JOIN album_photos ap ON ap.photo_id = p.id "
            "WHERE ap.album_id = ? ORDER BY ap.added_at DESC",
            (album_id,),
        ).fetchall()
        return {
            "id": row["id"],
            "name": row["name"],
            "created_at": row["created_at"],
            "photos": [self._public(p) for p in photos],
        }

    # ------------------------------------------------------------------ #
    # Agent audit log
    # ------------------------------------------------------------------ #
    def log_agent_call(self, tool: str, args_summary: str, ok: bool, duration_ms: float, error: str | None) -> None:
        self.conn.execute(
            "INSERT INTO agent_calls(tool, args_summary, ok, duration_ms, error, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (tool, args_summary[:500], 1 if ok else 0, duration_ms, error, _now()),
        )
        self.conn.commit()

    def recent_agent_calls(self, limit: int = 20) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM agent_calls ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
