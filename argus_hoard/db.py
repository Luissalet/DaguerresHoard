"""SQLite schema and connection helper. WAL mode, stdlib sqlite3 only."""
from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS roots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT UNIQUE NOT NULL,
    excluded_globs TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    added_by TEXT NOT NULL DEFAULT 'user'
);

CREATE TABLE IF NOT EXISTS photos (
    id TEXT PRIMARY KEY,
    root_id INTEGER NOT NULL REFERENCES roots(id),
    path TEXT UNIQUE NOT NULL,
    size INTEGER NOT NULL,
    mtime_ns INTEGER NOT NULL,
    content_hash TEXT NOT NULL,
    phash TEXT,
    width INTEGER,
    height INTEGER,
    taken_at TEXT,
    date_source TEXT,
    make TEXT,
    model TEXT,
    lens TEXT,
    f_number REAL,
    exposure_time TEXT,
    iso INTEGER,
    focal_length REAL,
    orientation INTEGER,
    gps_lat REAL,
    gps_lon REAL,
    city TEXT,
    region TEXT,
    country TEXT,
    caption TEXT,
    embed_row INTEGER,
    embed_model TEXT,
    indexed_at TEXT NOT NULL,
    missing INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_photos_hash ON photos(content_hash);
CREATE INDEX IF NOT EXISTS idx_photos_phash ON photos(phash);
CREATE INDEX IF NOT EXISTS idx_photos_taken ON photos(taken_at);
CREATE INDEX IF NOT EXISTS idx_photos_root ON photos(root_id);

CREATE VIRTUAL TABLE IF NOT EXISTS photos_fts USING fts5(
    photo_id UNINDEXED, caption, tokenize='porter unicode61'
);

CREATE TABLE IF NOT EXISTS albums (
    id TEXT PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    created_at TEXT NOT NULL,
    created_by TEXT NOT NULL DEFAULT 'user'
);

CREATE TABLE IF NOT EXISTS album_photos (
    album_id TEXT NOT NULL REFERENCES albums(id),
    photo_id TEXT NOT NULL REFERENCES photos(id),
    added_at TEXT NOT NULL,
    PRIMARY KEY (album_id, photo_id)
);

CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    status TEXT NOT NULL,
    progress REAL NOT NULL DEFAULT 0,
    message TEXT,
    stats TEXT,
    started_at TEXT NOT NULL,
    finished_at TEXT
);

CREATE TABLE IF NOT EXISTS agent_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tool TEXT NOT NULL,
    args_summary TEXT,
    ok INTEGER NOT NULL,
    duration_ms REAL NOT NULL,
    error TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


def _migrate(conn: sqlite3.Connection) -> None:
    """Bring databases created by earlier builds up to the current schema."""
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(photos)").fetchall()}
    if "embed_model" not in cols:
        # Vectors written before this column existed have an unknown origin:
        # leave embed_model NULL so the next scan re-embeds them.
        conn.execute("ALTER TABLE photos ADD COLUMN embed_model TEXT")
    fts_sql = conn.execute(
        "SELECT sql FROM sqlite_master WHERE name = 'photos_fts'"
    ).fetchone()
    if fts_sql and "content=''" in (fts_sql["sql"] or ""):
        # A contentless FTS table cannot return photo_id nor delete rows,
        # which silently disabled hybrid search. Rebuild it from photos.
        conn.execute("DROP TABLE photos_fts")
        conn.executescript(SCHEMA)
        conn.execute(
            "INSERT INTO photos_fts(rowid, photo_id, caption) "
            "SELECT rowid, id, caption FROM photos WHERE caption IS NOT NULL"
        )


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), check_same_thread=False, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=10000")
    conn.executescript(SCHEMA)
    _migrate(conn)
    conn.commit()
    return conn


class ThreadLocalConnections:
    """One sqlite3 connection per thread (WAL lets them run concurrently).

    The HTTP thread pool, the background job threads and the tests all go
    through `Library.conn`; sharing a single connection between threads
    interleaves their transactions, so each thread gets its own."""

    def __init__(self, db_path: Path):
        import threading

        self.db_path = db_path
        self._local = threading.local()
        self._lock = threading.Lock()
        self._all: list[sqlite3.Connection] = []
        self.get()  # create the schema eagerly, in the constructing thread

    def get(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = connect(self.db_path)
            self._local.conn = conn
            with self._lock:
                self._all.append(conn)
        return conn

    def close_all(self) -> None:
        with self._lock:
            for conn in self._all:
                try:
                    conn.close()
                except sqlite3.Error:
                    pass
            self._all.clear()


def get_setting(conn: sqlite3.Connection, key: str, default: str | None = None) -> str | None:
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO settings(key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    conn.commit()
