"""Durable job and completed-range metadata. URLs stay on the local machine."""

import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path


class Store:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, data TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS chunks (job TEXT, idx INTEGER, start INTEGER, "
                       "end INTEGER, done INTEGER DEFAULT 0, PRIMARY KEY(job, idx))")
            db.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, job TEXT, "
                       "time REAL, kind TEXT, message TEXT)")
            db.execute("CREATE TABLE IF NOT EXISTS inbox (id TEXT PRIMARY KEY, data TEXT NOT NULL, "
                       "created REAL, state TEXT DEFAULT 'pending')")

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=30)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def create(self, url, directory, filename, connections=8, expected_sha256=""):
        job = {"id": uuid.uuid4().hex, "url": url, "directory": str(directory), "filename": filename,
               "connections": max(1, min(32, int(connections))), "expected_sha256": expected_sha256.lower(),
               "state": "paused", "total": 0, "downloaded": 0, "speed": 0, "error": "", "created": time.time(),
               "etag": "", "modified": "", "ranged": False, "sha256": "", "output": ""}
        job.update(mirrors=[], mirror_fallback=False, scheduled_at=0, category="", checksums={})
        with self.connect() as db:
            db.execute("INSERT INTO jobs VALUES (?, ?)", (job["id"], json.dumps(job)))
        return job

    def get(self, job_id):
        with self.connect() as db:
            row = db.execute("SELECT data FROM jobs WHERE id=?", (job_id,)).fetchone()
        if row is None:
            raise KeyError(job_id)
        return json.loads(row[0])

    def update(self, job_id, **changes):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            job = json.loads(db.execute("SELECT data FROM jobs WHERE id=?", (job_id,)).fetchone()[0])
            job.update(changes)
            db.execute("UPDATE jobs SET data=? WHERE id=?", (json.dumps(job), job_id))
        return job

    def all(self):
        with self.connect() as db:
            return [json.loads(row[0]) for row in db.execute("SELECT data FROM jobs ORDER BY rowid DESC")]

    def chunks(self, job_id):
        with self.connect() as db:
            return db.execute("SELECT idx,start,end,done FROM chunks WHERE job=? ORDER BY idx", (job_id,)).fetchall()

    def set_chunks(self, job_id, ranges):
        with self.connect() as db:
            db.execute("DELETE FROM chunks WHERE job=?", (job_id,))
            db.executemany("INSERT INTO chunks(job,idx,start,end) VALUES(?,?,?,?)",
                           [(job_id, i, start, end) for i, (start, end) in enumerate(ranges)])

    def mark_chunk(self, job_id, idx):
        with self.connect() as db:
            db.execute("UPDATE chunks SET done=1 WHERE job=? AND idx=?", (job_id, idx))

    def recover(self):
        with self.connect() as db:
            db.execute("UPDATE inbox SET state='pending' WHERE state='reviewing'")
        for job in self.all():
            if job["state"] in {"queued", "downloading", "verifying"}:
                self.update(job["id"], state="paused", speed=0)

    def setting(self, key, default=None):
        with self.connect() as db:
            row = db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def set_setting(self, key, value):
        with self.connect() as db:
            db.execute("INSERT INTO settings VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                       (key, json.dumps(value)))

    def event(self, job_id, kind, message):
        with self.connect() as db:
            db.execute("INSERT INTO events(job,time,kind,message) VALUES(?,?,?,?)",
                       (job_id, time.time(), kind, message))

    def events(self, job_id):
        with self.connect() as db:
            return db.execute("SELECT time,kind,message FROM events WHERE job=? ORDER BY id", (job_id,)).fetchall()

    def enqueue(self, request_id, data):
        with self.connect() as db:
            cursor = db.execute("INSERT OR IGNORE INTO inbox(id,data,created) VALUES(?,?,?)",
                                (request_id, json.dumps(data), time.time()))
            return cursor.rowcount == 1

    def inbox(self):
        with self.connect() as db:
            return [(row[0], json.loads(row[1])) for row in db.execute(
                "SELECT id,data FROM inbox WHERE state='pending' ORDER BY created LIMIT 20")]

    def acknowledge(self, request_id, state="accepted"):
        with self.connect() as db:
            db.execute("UPDATE inbox SET state=? WHERE id=?", (state, request_id))
            if state in {"accepted", "cancelled"}:
                row = db.execute("SELECT data FROM inbox WHERE id=?", (request_id,)).fetchone()
                if row:
                    data = json.loads(row[0])
                    data.pop("session_dpapi", None)
                    data.pop("html", None)
                    db.execute("UPDATE inbox SET data=? WHERE id=?", (json.dumps(data), request_id))
