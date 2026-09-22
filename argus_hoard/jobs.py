"""Background job runner: long work (indexing, downloads, caption batches)
runs off the request thread so HTTP handlers stay responsive. Progress is
polled via /api/jobs."""
from __future__ import annotations

import datetime as dt
import json
import logging
import sqlite3
import threading
import uuid
from typing import Callable

log = logging.getLogger(__name__)

JobFn = Callable[["JobHandle"], None]
ConnFactory = Callable[[], sqlite3.Connection]


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


class JobHandle:
    def __init__(self, job_id: str, conn: ConnFactory):
        self.id = job_id
        self._conn = conn

    def progress(self, fraction: float, message: str = "") -> None:
        c = self._conn()
        c.execute(
            "UPDATE jobs SET progress = ?, message = ? WHERE id = ?",
            (max(0.0, min(1.0, float(fraction))), message[:300], self.id),
        )
        c.commit()

    def set_stats(self, stats: dict) -> None:
        c = self._conn()
        c.execute("UPDATE jobs SET stats = ? WHERE id = ?", (json.dumps(stats), self.id))
        c.commit()


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    if d.get("stats"):
        try:
            d["stats"] = json.loads(d["stats"])
        except ValueError:
            pass
    return d


class JobManager:
    def __init__(self, conn: ConnFactory):
        self._conn = conn
        # A previous process may have died mid-job: its daemon thread is
        # gone, so a 'running' row would otherwise spin in the UI forever.
        c = self._conn()
        c.execute(
            "UPDATE jobs SET status = 'interrupted', finished_at = ?, "
            "message = 'the app stopped before this job finished' WHERE status = 'running'",
            (_now(),),
        )
        c.commit()

    def start(self, kind: str, fn: JobFn) -> str:
        job_id = uuid.uuid4().hex
        c = self._conn()
        c.execute(
            "INSERT INTO jobs(id, kind, status, progress, message, started_at) VALUES (?, ?, 'running', 0, '', ?)",
            (job_id, kind, _now()),
        )
        c.commit()
        handle = JobHandle(job_id, self._conn)

        def runner():
            status, message = "done", None
            try:
                fn(handle)
            except Exception as exc:  # noqa: BLE001 - surfaced to the UI, not swallowed
                log.exception("job %s (%s) failed", job_id, kind)
                status, message = "error", f"{type(exc).__name__}: {exc}"[:300]
            conn = self._conn()
            if status == "done":
                conn.execute(
                    "UPDATE jobs SET status = 'done', finished_at = ?, progress = 1.0 WHERE id = ?",
                    (_now(), job_id),
                )
            else:
                conn.execute(
                    "UPDATE jobs SET status = 'error', finished_at = ?, message = ? WHERE id = ?",
                    (_now(), message, job_id),
                )
            conn.commit()

        thread = threading.Thread(target=runner, name=f"argus-job-{kind}", daemon=True)
        thread.start()
        return job_id

    def get(self, job_id: str) -> dict | None:
        row = self._conn().execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return _row_to_dict(row) if row else None

    def list(self, limit: int = 10) -> list[dict]:
        rows = self._conn().execute(
            "SELECT * FROM jobs ORDER BY started_at DESC LIMIT ?", (max(1, min(int(limit), 100)),)
        ).fetchall()
        return [_row_to_dict(r) for r in rows]

    def running(self, kind: str | None = None) -> list[dict]:
        sql = "SELECT * FROM jobs WHERE status = 'running'"
        params: tuple = ()
        if kind:
            sql += " AND kind = ?"
            params = (kind,)
        return [_row_to_dict(r) for r in self._conn().execute(sql, params).fetchall()]
