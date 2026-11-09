"""Exercise tail stealing and durable recovery through a real range server."""

import hashlib
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from itertools import pairwise
from pathlib import Path

from hngoos_dm.engine import DownloadManager
from hngoos_dm.store import Store


class AdaptiveDownloadTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.payload = bytes(range(256))*65536
        self.stolen = threading.Event()
        self.release_parent = threading.Event()
        self.hold_parent = False
        self.requests, self.slow = [], False
        owner = self
        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"
            def log_message(self, *_args):
                pass
            def handle(self):
                try:
                    super().handle()
                except (ConnectionResetError, ConnectionAbortedError):
                    pass  # Paused and shortened responses deliberately close early.
            def do_GET(self):
                start, end = map(int, self.headers["Range"][6:].split("-"))
                owner.requests.append((start, end))
                if 0 < start < len(owner.payload)//4:
                    owner.stolen.set()
                self.send_response(206)
                self.send_header("Content-Length", str(end-start+1))
                self.send_header("Content-Range", f"bytes {start}-{end}/{len(owner.payload)}")
                self.send_header("ETag", '"adaptive-fixture"')
                self.end_headers()
                try:
                    if owner.slow and start == 0 and end > 0:
                        self.wfile.write(owner.payload[:128*1024])
                        self.wfile.flush()
                        owner.stolen.wait(3)
                        if owner.hold_parent:
                            owner.release_parent.wait(5)
                        start = 128*1024
                    self.wfile.write(memoryview(owner.payload)[start:end+1])
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    pass
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_port}/data"
        self.store = Store(self.folder/"db")
        self.manager = DownloadManager(self.store)
        self.addCleanup(lambda: self.manager.pool.shutdown(wait=True))
        self.addCleanup(self.manager.close)

    def wait(self, job_id):
        deadline = time.monotonic()+15
        while time.monotonic() < deadline:
            job = self.store.get(job_id)
            if job["state"] in {"complete", "error", "paused"} and job_id not in self.manager.active:
                self.assertEqual(job["state"], "complete", job["error"])
                self.assertEqual(Path(job["output"]).read_bytes(), self.payload)
                self.assertEqual(job["sha256"], hashlib.sha256(self.payload).hexdigest())
                return job
            time.sleep(.02)
        self.fail(str(self.store.get(job_id)))

    def test_idle_worker_steals_a_slow_tail_and_publishes_exact_bytes(self):
        self.slow = True
        job_id = self.manager.add(self.url, self.folder/"out", "fixture.bin", 2)
        self.wait(job_id)
        self.assertTrue(self.stolen.is_set(), "The final slow range was never split")
        chunks = sorted(self.store.chunks(job_id), key=lambda chunk: chunk[1])
        self.assertGreater(len(chunks), 4)
        self.assertEqual(chunks[0][1], 0)
        self.assertEqual(chunks[-1][2], len(self.payload)-1)
        for first, second in pairwise(chunks):
            self.assertEqual(first[2]+1, second[1])

    def test_resume_truncates_excess_parent_bytes_after_a_durable_split(self):
        row = self.store.create(self.url, self.folder/"out", "fixture.bin", 2)
        job_id = row["id"]
        self.store.update(job_id, ranged=True, etag='"adaptive-fixture"', total=len(self.payload))
        self.store.set_chunks(job_id, [(0, len(self.payload)-1)])
        self.store.split_chunk(job_id, 0, 1024*1024)
        staging = self.manager.staging_path(self.store.get(job_id))
        staging.mkdir(parents=True)
        (staging/"0.part").write_bytes(self.payload[:2*1024*1024])
        self.manager.start(job_id)
        self.wait(job_id)
        self.assertNotIn((0, 1024*1024-1), self.requests)

    def test_pause_and_resume_after_tail_split_keeps_exact_byte_ownership(self):
        self.slow = self.hold_parent = True
        job_id = self.manager.add(self.url, self.folder/"out", "fixture.bin", 2)
        try:
            self.assertTrue(self.stolen.wait(5), "No durable tail split was dispatched")
            self.manager.pause(job_id)
        finally:
            self.release_parent.set()
        deadline = time.monotonic()+5
        while job_id in self.manager.active and time.monotonic() < deadline:
            time.sleep(.01)
        self.assertEqual(self.store.get(job_id)["state"], "paused")
        self.slow = False
        self.manager.start(job_id)
        self.wait(job_id)
