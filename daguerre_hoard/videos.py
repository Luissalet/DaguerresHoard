"""Video support for the library: key-frame indexing and the video read API.

``VideoMixin`` is mixed into ``Library``. A video is one row in ``videos``; each of its key frames is a regular
``photos`` row (``video_id`` + ``frame_ts`` set) whose file is a JPEG under ``data/frames/<video id>/``, so frames go
through exactly the pipeline photos use (thumbnail, perceptual hash, embedding, full-text, albums, search). Frames are
hidden from the plain library grid and from photo-only statistics; search and "similar" include them.

The original video is only ever read. Re-scans are incremental: a video is re-extracted only when its size/mtime
changed (and its content did, by a cheap head+tail hash) or when the extraction settings changed.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import logging
import shutil
import uuid
from pathlib import Path
from typing import Any

from . import db as dbmod
from .hashing import content_hash
from .phash import compute_phash
from .scanning import stat_signature, walk_videos
from .thumbnails import make_thumbnail, thumb_path
from .video_frames import DEFAULT_INTERVAL_S, DEFAULT_MAX_FRAMES, FfmpegExtractor, format_ts

log = logging.getLogger(__name__)

MAX_FRAMES_CAP = 200
_HEAD_TAIL = 1024 * 1024


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def quick_hash(path: Path, size: int) -> str:
    """Cheap identity of a (possibly huge) video: its size plus the first and last megabyte."""
    h = hashlib.blake2b(digest_size=16)
    h.update(str(size).encode())
    with open(path, "rb") as fh:
        h.update(fh.read(_HEAD_TAIL))
        if size > 2 * _HEAD_TAIL:
            fh.seek(size - _HEAD_TAIL)
            h.update(fh.read(_HEAD_TAIL))
    return h.hexdigest()


class VideoMixin:
    frame_extractor: Any

    def _init_videos(self) -> None:
        self.frame_extractor = FfmpegExtractor()
        self._video_paths: dict[str, str] = {}

    # ------------------------------------------------------------------ #
    # Settings
    # ------------------------------------------------------------------ #
    def video_settings(self) -> dict:
        c = self.conn
        try:
            max_frames = int(dbmod.get_setting(c, "video_max_frames", str(DEFAULT_MAX_FRAMES)))
        except ValueError:
            max_frames = DEFAULT_MAX_FRAMES
        try:
            interval = float(dbmod.get_setting(c, "video_interval_s", str(DEFAULT_INTERVAL_S)))
        except ValueError:
            interval = DEFAULT_INTERVAL_S
        return {
            "enabled": dbmod.get_setting(c, "video_frames_enabled", "true") != "false",
            "max_frames": max(1, min(max_frames, MAX_FRAMES_CAP)),
            "interval_s": max(1.0, interval),
            "extractor": self.frame_extractor.name if self.frame_extractor.available else None,
        }

    def set_video_settings(
        self, enabled: bool | None = None, max_frames: int | None = None, interval_s: float | None = None
    ) -> dict:
        from .library import ValidationError

        if enabled is not None:
            dbmod.set_setting(self.conn, "video_frames_enabled", "true" if enabled else "false")
        if max_frames is not None:
            if not 1 <= int(max_frames) <= MAX_FRAMES_CAP:
                raise ValidationError(f"max_frames must be 1-{MAX_FRAMES_CAP}")
            dbmod.set_setting(self.conn, "video_max_frames", str(int(max_frames)))
        if interval_s is not None:
            if float(interval_s) < 1:
                raise ValidationError("interval_s must be at least 1 second")
            dbmod.set_setting(self.conn, "video_interval_s", f"{float(interval_s):g}")
        return self.video_settings()

    # ------------------------------------------------------------------ #
    # Indexing (called from the scan, between the photo pass and embedding)
    # ------------------------------------------------------------------ #
    def _index_videos(self, roots: list[dict], stats: dict, record_error, pending_embed: list[str], handle) -> None:
        for key in ("videos_seen", "videos_new", "videos_updated", "videos_unchanged", "videos_moved",
                    "videos_no_ffmpeg", "frames"):
            stats[key] = 0
        cfg = self.video_settings()
        if not cfg["enabled"]:
            return
        c = self.conn
        plan: list[tuple[dict, Path]] = []
        reachable: list[int] = []
        for root in roots:
            rp = Path(root["path"])
            if not rp.is_dir():
                continue
            reachable.append(root["id"])
            for p in walk_videos(rp, json.loads(root["excluded_globs"]), skip_dirs=self._skip_dirs):
                plan.append((root, p))
        stats["videos_seen"] = len(plan)
        params = f"{cfg['max_frames']}/{cfg['interval_s']:g}"
        for n, (root, path) in enumerate(plan, start=1):
            try:
                self._index_one_video(root, path, params, cfg, stats, pending_embed)
            except Exception as exc:  # noqa: BLE001 - one bad video must not stop the scan
                record_error(path, exc)
            handle.progress(0.85, f"videos {n}/{len(plan)}")
            handle.set_stats(stats)
        seen = {str(p) for _, p in plan}
        for rid in reachable:
            for row in c.execute("SELECT id, path FROM videos WHERE root_id = ? AND missing = 0", (rid,)).fetchall():
                if row["path"] not in seen and not Path(row["path"]).exists():
                    c.execute("UPDATE videos SET missing = 1 WHERE id = ?", (row["id"],))
                    c.execute("UPDATE photos SET missing = 1 WHERE video_id = ?", (row["id"],))
        c.commit()

    def _set_video_missing(self, video_id: str, missing: int) -> None:
        self.conn.execute("UPDATE photos SET missing = ? WHERE video_id = ?", (missing, video_id))

    def _index_one_video(self, root: dict, path: Path, params: str, cfg: dict, stats: dict, pending_embed) -> None:
        c = self.conn
        size, mtime_ns = stat_signature(path)
        row = c.execute("SELECT * FROM videos WHERE path = ?", (str(path),)).fetchone()
        extractor_ok = self.frame_extractor.available
        retry_for_ffmpeg = bool(row) and row["status"] == "no_extractor" and extractor_ok
        if (
            row and row["size"] == size and row["mtime_ns"] == mtime_ns and not row["missing"]
            and row["params"] == params and not retry_for_ffmpeg
        ):
            stats["videos_unchanged"] += 1
            return
        qhash = quick_hash(path, size)
        if row and row["quick_hash"] == qhash and row["params"] == params and not retry_for_ffmpeg:
            c.execute(
                "UPDATE videos SET size = ?, mtime_ns = ?, missing = 0, root_id = ? WHERE id = ?",
                (size, mtime_ns, root["id"], row["id"]),
            )
            self._set_video_missing(row["id"], 0)
            c.commit()
            stats["videos_unchanged"] += 1
            return
        if not row:
            for other in c.execute(
                "SELECT * FROM videos WHERE quick_hash = ? AND path != ?", (qhash, str(path))
            ).fetchall():
                if other["params"] == params and not Path(other["path"]).exists():
                    c.execute(
                        "UPDATE videos SET path = ?, root_id = ?, size = ?, mtime_ns = ?, missing = 0 WHERE id = ?",
                        (str(path), root["id"], size, mtime_ns, other["id"]),
                    )
                    c.execute("UPDATE photos SET root_id = ? WHERE video_id = ?", (root["id"], other["id"]))
                    self._set_video_missing(other["id"], 0)
                    self._video_paths.pop(other["id"], None)
                    c.commit()
                    stats["videos_moved"] += 1
                    return

        video_id = row["id"] if row else uuid.uuid4().hex
        self._drop_frames(video_id)
        base = dict(
            id=video_id, root_id=root["id"], path=str(path), size=size, mtime_ns=mtime_ns, quick_hash=qhash,
            params=params, indexed_at=_now(), missing=0,
        )
        if not extractor_ok:
            fields = dict(base, duration=None, width=None, height=None, taken_at=self._mtime_iso(mtime_ns),
                          frame_count=0, status="no_extractor",
                          error="ffmpeg was not found, so no key frames were extracted")
            stats["videos_no_ffmpeg"] += 1
            self._upsert_video(fields, bool(row))
            return

        extraction = self.frame_extractor.extract(path, self.settings.frames_dir / video_id, cfg["max_frames"], cfg["interval_s"])
        info = extraction.info
        taken_at = info.created or self._mtime_iso(mtime_ns)
        date_source = "video_tag" if info.created else "file_mtime"
        inserted = 0
        for frame in extraction.frames:
            if self._insert_frame(root["id"], video_id, path, frame, taken_at, date_source, pending_embed):
                inserted += 1
        status, error = ("ok", None) if inserted else ("error", "no key frame could be extracted from this video")
        fields = dict(base, duration=info.duration, width=info.width, height=info.height, taken_at=taken_at,
                      frame_count=inserted, status=status, error=error)
        self._upsert_video(fields, bool(row))
        stats["videos_updated" if row else "videos_new"] += 1
        stats["frames"] += inserted

    @staticmethod
    def _mtime_iso(mtime_ns: int) -> str:
        return dt.datetime.fromtimestamp(mtime_ns / 1e9, tz=dt.timezone.utc).isoformat()

    def _upsert_video(self, fields: dict, exists: bool) -> None:
        c = self.conn
        if exists:
            sets = ", ".join(f"{k} = :{k}" for k in fields if k != "id")
            c.execute(f"UPDATE videos SET {sets} WHERE id = :id", fields)
        else:
            cols = ", ".join(fields)
            c.execute(f"INSERT INTO videos ({cols}) VALUES ({', '.join(':' + k for k in fields)})", fields)
        c.commit()
        self._video_paths.pop(fields["id"], None)

    def _insert_frame(self, root_id, video_id, video_path, frame, taken_at, date_source, pending_embed) -> bool:
        from PIL import Image

        c = self.conn
        photo_id = uuid.uuid4().hex
        try:
            with Image.open(frame.path) as img:
                width, height = img.size
            st = frame.path.stat()
            make_thumbnail(frame.path, thumb_path(self.settings.thumbs_dir, photo_id))
            phash = compute_phash(frame.path)
            fhash = content_hash(frame.path)
        except Exception:  # noqa: BLE001 - a frame that cannot be read is skipped, the rest still count
            log.warning("could not index frame %s of %s", frame.path, video_path, exc_info=True)
            return False
        fields = dict(
            id=photo_id, root_id=root_id, path=str(frame.path), size=st.st_size, mtime_ns=st.st_mtime_ns,
            content_hash=fhash, phash=f"{phash:016x}", width=width, height=height, taken_at=taken_at,
            date_source=date_source, orientation=1, indexed_at=_now(), missing=0,
            video_id=video_id, frame_ts=round(float(frame.ts), 3),
        )
        cols = ", ".join(fields)
        c.execute(f"INSERT INTO photos ({cols}) VALUES ({', '.join(':' + k for k in fields)})", fields)
        # searchable by the video's name even before any caption exists
        words = " ".join(Path(video_path).stem.replace("_", " ").replace("-", " ").replace(".", " ").split())
        rowid = c.execute("SELECT rowid FROM photos WHERE id = ?", (photo_id,)).fetchone()["rowid"]
        c.execute(
            "INSERT INTO photos_fts(rowid, photo_id, caption) VALUES (?, ?, ?)", (rowid, photo_id, f"video {words}")
        )
        pending_embed.append(photo_id)
        return True

    def _drop_frames(self, video_id: str) -> None:
        """Forget a video's frame rows (index data, albums memberships, thumbnails, extracted JPEGs)."""
        c = self.conn
        ids = [r["id"] for r in c.execute("SELECT id FROM photos WHERE video_id = ?", (video_id,)).fetchall()]
        for start in range(0, len(ids), 500):
            chunk = ids[start : start + 500]
            marks = ",".join("?" * len(chunk))
            c.execute(f"DELETE FROM album_photos WHERE photo_id IN ({marks})", chunk)
            c.execute(f"DELETE FROM photos_fts WHERE rowid IN (SELECT rowid FROM photos WHERE id IN ({marks}))", chunk)
        c.execute("DELETE FROM photos WHERE video_id = ?", (video_id,))
        c.commit()
        for pid in ids:
            try:
                thumb_path(self.settings.thumbs_dir, pid).unlink(missing_ok=True)
            except OSError:
                pass
        shutil.rmtree(self.settings.frames_dir / video_id, ignore_errors=True)

    def _forget_root_videos(self, root_id: int) -> None:
        """remove_root: drop the videos of a root together with their derived frames."""
        c = self.conn
        for r in c.execute("SELECT id FROM videos WHERE root_id = ?", (root_id,)).fetchall():
            self._drop_frames(r["id"])
            self._video_paths.pop(r["id"], None)
        c.execute("DELETE FROM videos WHERE root_id = ?", (root_id,))
        c.commit()

    # ------------------------------------------------------------------ #
    # Public views
    # ------------------------------------------------------------------ #
    def _video_path(self, video_id: str) -> str | None:
        if video_id not in self._video_paths:
            row = self.conn.execute("SELECT path FROM videos WHERE id = ?", (video_id,)).fetchone()
            if not row:
                return None
            self._video_paths[video_id] = row["path"]
        return self._video_paths[video_id]

    def _frame_fields(self, row) -> dict:
        """What a frame row adds to its public dict: where in which video it comes from."""
        ts = row["frame_ts"] or 0.0
        vpath = self._video_path(row["video_id"]) or row["path"]
        return {
            "video_id": row["video_id"],
            "frame_ts": round(float(ts), 2),
            "timestamp": format_ts(ts),
            "video_name": Path(vpath).name,
            "video_path": vpath,
        }

    def _video_public(self, row, cover_id: str | None = None) -> dict:
        d = {
            "id": row["id"],
            "path": row["path"],
            "name": Path(row["path"]).name,
            "taken_at": row["taken_at"],
            "size": row["size"],
            "duration": round(row["duration"], 2) if row["duration"] is not None else None,
            "duration_label": format_ts(row["duration"]) if row["duration"] is not None else None,
            "width": row["width"],
            "height": row["height"],
            "frame_count": row["frame_count"],
            "status": row["status"],
            "thumbnail_url": f"/api/photos/{cover_id}/thumbnail" if cover_id else None,
            "stream_url": f"/api/videos/{row['id']}/stream",
        }
        if row["error"]:
            d["error"] = row["error"]
        if row["missing"]:
            d["missing"] = True
        return d

    def _resolve_video(self, video_id: str):
        from .library import ID_RE, NotFoundError

        vid = str(video_id or "").strip().lower()
        row = self.conn.execute("SELECT * FROM videos WHERE id = ?", (vid,)).fetchone() if ID_RE.match(vid) else None
        if not row:
            raise NotFoundError(f"video not found: {video_id}. Use an 'id' value returned by videos_list.")
        return row

    def list_videos(self, folder: str | None = None, limit: int = 60, offset: int = 0) -> dict:
        from .library import _clamp_limit, _like

        limit = _clamp_limit(limit, 60, maximum=200)
        offset = max(0, int(offset or 0))
        where, params = "v.missing = 0", []
        if folder and str(folder).strip():
            where += " AND replace(v.path, '\\', '/') LIKE ? ESCAPE '!'"
            params.append(_like(str(folder).strip().replace("\\", "/")[:200]))
        c = self.conn
        total = c.execute(f"SELECT COUNT(*) c FROM videos v WHERE {where}", params).fetchone()["c"]
        rows = c.execute(
            f"SELECT v.*, (SELECT p.id FROM photos p WHERE p.video_id = v.id AND p.missing = 0 "
            f"ORDER BY p.frame_ts LIMIT 1) AS cover_id FROM videos v WHERE {where} "
            f"ORDER BY v.taken_at DESC, v.path ASC LIMIT ? OFFSET ?",
            (*params, limit, offset),
        ).fetchall()
        more = offset + limit < total
        out: dict[str, Any] = {
            "count": total,
            "returned": len(rows),
            "results": [self._video_public(r, r["cover_id"]) for r in rows],
            "has_more": more,
        }
        if more:
            out["next_offset"] = offset + limit
        if not self.frame_extractor.available:
            out["note"] = "ffmpeg is not installed, so videos are listed without key frames"
        return out

    def get_video(self, video_id: str, frames_limit: int | None = None) -> dict:
        row = self._resolve_video(video_id)
        frames = self.conn.execute(
            "SELECT * FROM photos WHERE video_id = ? AND missing = 0 ORDER BY frame_ts, id", (row["id"],)
        ).fetchall()
        shown = frames if frames_limit is None else frames[: max(1, int(frames_limit))]
        out = self._video_public(row, frames[0]["id"] if frames else None)
        out["frames"] = [
            {
                "id": f["id"], "ts": round(float(f["frame_ts"] or 0), 2), "timestamp": format_ts(f["frame_ts"]),
                "width": f["width"], "height": f["height"], "caption": f["caption"],
                "thumbnail_url": f"/api/photos/{f['id']}/thumbnail",
            }
            for f in shown
        ]
        if len(shown) < len(frames):
            out["has_more_frames"] = True
        return out

    def video_file(self, video_id: str) -> Path:
        from .library import NotFoundError

        row = self._resolve_video(video_id)
        p = Path(row["path"])
        if not p.is_file():
            raise NotFoundError(f"the video file is not reachable right now: {p}")
        return p
