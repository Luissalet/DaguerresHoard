"""A completed worker must not look like an abandoned job after a stale read."""
import sqlite3

import pytest

from daguerre_hoard.jobs import JobManager


@pytest.mark.parametrize('read', ['get', 'list'])
@pytest.mark.parametrize('status', ['done', 'error', 'interrupted'])
def test_completion_between_select_and_public_state_keeps_terminal_status(read, status):
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    conn.execute('CREATE TABLE jobs(id TEXT,status TEXT,message TEXT,finished_at TEXT,started_at TEXT,progress REAL)')
    conn.execute("INSERT INTO jobs VALUES('job','running','',NULL,'today',0)")
    manager = JobManager(lambda: conn, recover=False)
    manager._active.add('job')
    class Cursor:
        def __init__(self, cursor): self.cursor = cursor
        def finish(self):
            conn.execute('UPDATE jobs SET status=?,message=?,finished_at=?,progress=? WHERE id=?',
                         (status,'Terminal message','finished',1,'job'))
            conn.commit()
            with manager._lock: manager._active.discard('job')
        def fetchone(self):
            row = self.cursor.fetchone()
            self.finish()
            return row
        def fetchall(self):
            rows = self.cursor.fetchall()
            self.finish()
            return rows
    class SnapshotConnection:
        def execute(self, *args): return Cursor(conn.execute(*args))
    calls = []
    def connection():
        calls.append(True)
        return SnapshotConnection() if len(calls)==1 else conn
    manager._conn = connection
    try:
        result = manager.get('job') if read=='get' else manager.list()[0]
        assert result['status']==status and result['finished_at']=='finished'
        assert result['message']=='Terminal message' and 'original_status' not in result
    finally:
        conn.close()


@pytest.mark.parametrize('active', [True, False])
def test_current_running_job_and_previous_lifetime_remain_distinct(active):
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    conn.execute('CREATE TABLE jobs(id TEXT,status TEXT,started_at TEXT)')
    conn.execute("INSERT INTO jobs VALUES('job','running','today')")
    manager = JobManager(lambda: conn, recover=False)
    if active: manager._active.add('job')
    try:
        result = manager.get('job')
        assert result['status']==('running' if active else 'held')
        assert conn.execute("SELECT status FROM jobs WHERE id='job'").fetchone()[0]=='running'
        assert manager._active==({'job'} if active else set())
    finally:
        conn.close()
