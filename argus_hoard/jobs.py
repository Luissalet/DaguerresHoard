"""Background job runner: long work (indexing, scans) runs off the request
thread so HTTP handlers stay responsive. Progress is polled via /api/jobs."""
from __future__ import annotations

import datetime as dt
import json
import sqlite3
import threading
import uuid
from dataclasses import dataclass
from typing import Callable

JobFn = Callable[["JobHandle"], None]


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


@dataclass
class JobHandle:
    id: str
    _conn: sqlite3.Connection
    _lock: threading.Lock

    def progress(self, fraction: float, message: str = "") -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE jobs SET progress = ?, message = ? WHERE id = ?",
                (max(0.0, min(1.0, fraction)), message, self.id),
            )
            self._conn.commit()


class JobManager:
    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn
        self._lock = threading.Lock()

    def start(self, kind: str, fn: JobFn) -> str:
        job_id = uuid.uuid4().hex
        with self._lock:
            self._conn.execute(
                "INSERT INTO jobs(id, kind, status, progress, message, started_at) VALUES (?, ?, 'running', 0, '', ?)",
                (job_id, kind, _now()),
            )
            self._conn.commit()
        handle = JobHandle(id=job_id, _conn=self._conn, _lock=self._lock)

        def runner():
            try:
                fn(handle)
                status, message, stats = "done", "", None
            except Exception as exc:  # noqa: BLE001 - surfaced to the UI, not swallowed
                status, message, stats = "error", str(exc), None
            with self._lock:
                self._conn.execute(
                    "UPDATE jobs SET status = ?, message = ?, finished_at = ?, progress = ? WHERE id = ?",
                    (status, message, _now(), 1.0 if status == "done" else None, job_id),
                )
                self._conn.commit()

        thread = threading.Thread(target=runner, name=f"argus-job-{kind}", daemon=True)
        thread.start()
        return job_id

    def get(self, job_id: str) -> dict | None:
        row = self._conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return dict(row) if row else None

    def list(self, limit: int = 10) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM jobs ORDER BY started_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
