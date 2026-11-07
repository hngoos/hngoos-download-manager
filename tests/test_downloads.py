import hashlib
import json
import re
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import ClassVar

from hngoos_dm.batch import parse_text
from hngoos_dm.engine import DownloadManager
from hngoos_dm.instance import InstanceLock
from hngoos_dm.safety import safe_filename, validate_url
from hngoos_dm.store import Store

PAYLOAD = bytes(range(256)) * 20000
OTHER = bytes(reversed(range(256))) * 20000


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    seen: ClassVar[list] = []
    dropped = False
    dropped_ranges: ClassVar[list] = []
    throttled = False

    def log_message(self, *_args):
        pass

    def do_GET(self):
        type(self).seen.append((self.path, self.headers.get("Range")))
        data = OTHER if self.path.startswith("/changed") else (b"MZ" + PAYLOAD if self.path == "/disguised" else PAYLOAD)
        if self.path == "/empty":
            self.send_response(416)
            self.send_header("Content-Range", "bytes */0")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if self.path == "/expired":
            self.send_response(403)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        etag = '"changed"' if self.path.startswith("/changed") and self.path != "/changed-same-etag" else '"original"'
        if self.headers.get("If-Match") and self.headers["If-Match"] != etag:
            self.send_response(412)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        ranged = self.path not in {"/sequential", "/unknown"}
        match = re.fullmatch(r"bytes=(\d+)-(\d+)", self.headers.get("Range", "")) if ranged else None
        start, end = map(int, match.groups()) if match else (0, len(data)-1)
        end = min(end, len(data)-1)
        if self.path == "/throttle" and end > 0 and not type(self).throttled:
            type(self).throttled = True
            self.send_response(429)
            self.send_header("Content-Length", "0")
            self.send_header("Retry-After", "0")
            self.end_headers()
            return
        self.send_response(206 if match else 200)
        if self.path != "/unknown":
            self.send_header("Content-Length", str(end-start+1))
        else:
            self.send_header("Connection", "close")
            self.close_connection = True
        if self.path != "/noetag":
            self.send_header("ETag", etag)
        if match:
            self.send_header("Content-Range", f"bytes {start}-{end}/{len(data)}" if self.path != "/bad-range" or end == 0
                             else f"bytes 0-0/{len(data)}")
        self.end_headers()
        if self.path == "/drop" and end > 0 and not type(self).dropped:
            type(self).dropped = True
            type(self).dropped_ranges.append((start, end))
            self.wfile.write(data[start:start + 1024])
            self.wfile.flush()
            self.close_connection = True
            return
        try:
            for pos in range(start, end+1, 32768):
                self.wfile.write(data[pos:min(end+1, pos+32768)])
                if self.path in {"/slow", "/changed-slow"} and end > 0:
                    time.sleep(0.008)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass


class DownloadsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.server.daemon_threads = True
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)
        self.store = Store(self.folder / "db.sqlite3")
        self.manager = DownloadManager(self.store)

    def tearDown(self):
        self.manager.close()
        self.manager.pool.shutdown(wait=True)
        self.manager.safety_pool.shutdown(wait=True)
        self.temp.cleanup()

    def add(self, path="/file", filename="file.bin", **kw):
        return self.manager.add(self.base+path, self.folder / "output", filename, 4, **kw)

    def wait(self, job_id, states=("complete", "quarantined", "error", "paused"), timeout=15):
        until = time.monotonic()+timeout
        while time.monotonic() < until:
            job = self.store.get(job_id)
            if job["state"] in states and job_id not in self.manager.active:
                return job
            time.sleep(0.02)
        self.fail("Timeout: " + json.dumps(self.store.get(job_id)))

    def assert_payload(self, job, payload=PAYLOAD):
        self.assertEqual(job["state"], "complete", job["error"])
        self.assertEqual(Path(job["output"]).read_bytes(), payload)
        self.assertEqual(job["sha256"], hashlib.sha256(payload).hexdigest())

    def test_parallel_exact_bytes(self):
        Handler.seen = []
        self.assert_payload(self.wait(self.add()))
        ranges = {value for path, value in Handler.seen if path == "/file"}
        self.assertGreater(len(ranges), 3)

    @unittest.skipUnless(sys.platform == "win32", "Windows Defender integration")
    def test_slow_defender_does_not_hold_completed_download_or_next_download(self):
        import subprocess
        from unittest.mock import patch
        self.manager.close()
        self.manager.pool.shutdown(wait=True)
        self.manager = DownloadManager(self.store, simultaneous=1)
        entered, release = threading.Event(), threading.Event()
        def scan(_path, stop=None):
            entered.set()
            release.wait(8)
            return subprocess.CompletedProcess([], 0, "", "")
        self.store.set_setting("auto_defender", True)
        try:
            with patch("hngoos_dm.safety.scan_defender", side_effect=scan):
                job_id = self.add()
                self.assertTrue(entered.wait(4))
                job = self.wait(job_id, timeout=1)
                self.assert_payload(job)
                self.assertEqual(job["safety_check"]["status"], "scanning")
                self.store.set_setting("auto_defender", False)
                self.assert_payload(self.wait(self.add(filename="next.bin"), timeout=2))
                release.set()
                until = time.monotonic()+3
                while self.store.get(job_id).get("safety_check", {}).get("status") == "scanning" and time.monotonic()<until:
                    time.sleep(.02)
                self.assertEqual(self.store.get(job_id)["safety_check"]["status"], "clean")
        finally:
            release.set()

    def test_no_range_support(self):
        self.assert_payload(self.wait(self.add("/sequential")))

    def test_unknown_content_length(self):
        self.assert_payload(self.wait(self.add("/unknown")))

    def test_no_etag_uses_one_full_range(self):
        Handler.seen = []
        self.assert_payload(self.wait(self.add("/noetag")))
        self.assertEqual([r for p, r in Handler.seen if p == "/noetag"],
                         ["bytes=0-0", f"bytes=0-{len(PAYLOAD)-1}"])

    def test_incorrect_content_range_fails(self):
        job = self.wait(self.add("/bad-range"))
        self.assertEqual(job["state"], "error")
        self.assertFalse(job["output"])

    def test_retry_after_truncated_response(self):
        Handler.dropped = False
        Handler.dropped_ranges = []
        Handler.seen = []
        self.assert_payload(self.wait(self.add("/drop")))
        self.assertTrue(Handler.dropped)
        for start, end in Handler.dropped_ranges:
            self.assertIn(("/drop", f"bytes={start+1024}-{end}"), Handler.seen)

    def test_retry_rate_limit(self):
        Handler.throttled = False
        self.assert_payload(self.wait(self.add("/throttle")))

    def test_empty_file(self):
        self.assert_payload(self.wait(self.add("/empty")), b"")

    def test_hash_mismatch_quarantines(self):
        job = self.wait(self.add(expected_sha256="0" * 64))
        self.assertEqual(job["state"], "quarantined")
        self.assertTrue(job["output"].endswith(".chuakiemtra"))
        self.assertEqual(Path(job["output"]).read_bytes(), PAYLOAD)

    def test_disguised_executable_quarantines(self):
        job = self.wait(self.add("/disguised", "photo.jpg"))
        self.assertEqual(job["state"], "quarantined")
        self.assertIn("MZ", job["error"])

    def test_macro_extension_quarantines(self):
        self.assertEqual(self.wait(self.add(filename="invoice.xlsm"))["state"], "quarantined")

    def test_never_overwrites_existing_file(self):
        folder = self.folder / "output"
        folder.mkdir()
        (folder / "file.bin").write_bytes(b"keep me")
        job = self.wait(self.add())
        self.assert_payload(job)
        self.assertEqual((folder / "file.bin").read_bytes(), b"keep me")

    def pause_after_a_chunk(self):
        job_id = self.add("/slow")
        until = time.monotonic()+10
        while time.monotonic() < until:
            if any(c[3] for c in self.store.chunks(job_id)):
                self.manager.pause(job_id)
                job = self.wait(job_id)
                self.assertEqual(job["state"], "paused")
                return job_id
            time.sleep(0.01)
        self.fail("No completed range before timeout")

    def test_resume_after_reopening_database(self):
        job_id = self.pause_after_a_chunk()
        completed = {f"bytes={start}-{end}" for _, start, end, done in self.store.chunks(job_id) if done}
        self.assertTrue(completed)
        self.manager.close()
        self.manager.pool.shutdown(wait=True)
        self.manager = DownloadManager(Store(self.store.path))
        Handler.seen = []
        self.manager.start(job_id)
        self.assert_payload(self.wait(job_id))
        fetched = {r for p, r in Handler.seen if p == "/slow"}
        self.assertFalse(completed & fetched)

    def test_replacement_link_with_same_bytes_completes(self):
        job_id = self.pause_after_a_chunk()
        self.manager.replace_url(job_id, self.base+"/file")
        self.manager.start(job_id)
        self.assert_payload(self.wait(job_id))

    def test_replacement_changed_identity_restarts(self):
        job_id = self.pause_after_a_chunk()
        self.manager.replace_url(job_id, self.base+"/changed")
        self.manager.start(job_id)
        self.assert_payload(self.wait(job_id), OTHER)

    def test_expired_url_can_be_replaced(self):
        job_id = self.add("/expired")
        self.assertEqual(self.wait(job_id)["state"], "error")
        self.manager.replace_url(job_id, self.base+"/file")
        self.manager.start(job_id)
        self.assert_payload(self.wait(job_id))

    def test_replacement_url_does_not_mix_resources_with_the_same_etag_and_size(self):
        job_id = self.pause_after_a_chunk()
        self.manager.replace_url(job_id, self.base+"/changed-same-etag")
        self.manager.start(job_id)
        result = self.wait(job_id)
        self.assertEqual(result["state"], "complete", result["error"])
        self.assertEqual(hashlib.sha256(Path(result["output"]).read_bytes()).hexdigest(),
                         hashlib.sha256(OTHER).hexdigest())

    def test_mirror_same_bytes_and_different_etag(self):
        job_id = self.add(expected_sha256=hashlib.sha256(PAYLOAD).hexdigest(), mirrors=[self.base+"/slow"])
        self.assert_payload(self.wait(job_id))
        self.assertFalse(self.store.get(job_id)["mirror_fallback"])

    def test_wrong_mirror_is_discarded_and_primary_retried(self):
        Handler.seen.clear()
        job_id = self.add(expected_sha256=hashlib.sha256(PAYLOAD).hexdigest(), mirrors=[self.base+"/changed"])
        self.assert_payload(self.wait(job_id))
        self.assertTrue(self.store.get(job_id)["mirror_fallback"])
        self.assertTrue(any(kind == "mirror_integrity" for _, kind, _ in self.store.events(job_id)))
        primary_ranges = [value for path, value in Handler.seen if path == "/file" and value != "bytes=0-0"]
        self.assertEqual(len(primary_ranges), len(set(primary_ranges)), "Primary-source chunks must not be downloaded twice")

    def test_mirror_without_independent_hash_is_rejected(self):
        with self.assertRaises(ValueError):
            self.add(mirrors=[self.base+"/file"])

    def test_expected_md5_mismatch_is_quarantined(self):
        job = self.wait(self.add(expected_hashes={"md5": "0"*32}))
        self.assertEqual(job["state"], "quarantined")
        self.assertIn("MD5", job["error"])

    def test_schedule_starts_at_due_time(self):
        job_id = self.add(scheduled_at=time.time()+0.7)
        self.assertEqual(self.store.get(job_id)["state"], "scheduled")
        self.assert_payload(self.wait(job_id, states=("complete", "error")))

    def test_active_destination_change_keeps_download_and_resumes(self):
        job_id = self.add("/slow")
        until = time.monotonic()+10
        while not self.store.chunks(job_id) and time.monotonic() < until:
            time.sleep(0.01)
        destination = self.folder/"new-place"
        self.manager.relocate(job_id, destination)
        job = self.wait(job_id, states=("complete", "error"))
        self.assert_payload(job)
        self.assertEqual(Path(job["output"]).parent.resolve(), destination.resolve())

    def test_adopt_browser_prefix_verifies_all_bytes_and_keeps_original(self):
        original = self.folder/"browser.bin.crdownload"
        prefix = PAYLOAD[:1500000]
        original.write_bytes(prefix)
        job_id = self.manager.adopt_partial(self.base+"/file", original, self.folder/"output", "adopted.bin", 4)
        self.assert_payload(self.wait(job_id))
        self.assertEqual(original.read_bytes(), prefix)

    def test_adoption_rejects_wrong_prefix_even_if_end_overlap_matches(self):
        original = self.folder/"browser.crdownload"
        prefix = bytearray(PAYLOAD[:1500000])
        prefix[100] ^= 0xff
        original.write_bytes(prefix)
        with self.assertRaises(ValueError):
            self.manager.adopt_partial(self.base+"/file", original, self.folder/"output", "bad.bin", 4)


class InputTest(unittest.TestCase):
    def test_only_one_process_owns_database(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "instance.lock"
            owner = InstanceLock(path)
            try:
                with self.assertRaises(RuntimeError):
                    InstanceLock(path)
            finally:
                owner.close()
            replacement = InstanceLock(path)
            replacement.close()

    def test_xlsx_hyperlink_and_numbering(self):
        from openpyxl import Workbook

        from hngoos_dm.batch import read_batch
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "links.xlsx"
            book = Workbook()
            sheet = book.active
            sheet.append(["link", "tên tệp"])
            sheet.append(["Nhấn để tải", "Tài liệu.pdf"])
            sheet["A2"].hyperlink = "https://example.com/document.pdf"
            sheet.append(["https://example.com/image.png"])
            book.save(path)
            book.close()
            self.assertEqual(read_batch(path), [("https://example.com/document.pdf", "Tài liệu.pdf"),
                                               ("https://example.com/image.png", "002.png")])

    def test_windows_filenames_and_traversal(self):
        self.assertNotIn("/", safe_filename("../../picture.jpg"))
        self.assertNotIn("\\", safe_filename("..\\..\\evil.exe"))
        self.assertEqual(safe_filename("CON.txt"), "_CON.txt")

    def test_local_file_and_credentials_are_rejected(self):
        for url in ("file:///C:/private", "javascript:alert(1)", "https://a:b@example.com/x"):
            with self.assertRaises(ValueError):
                validate_url(url)

    def test_batch_headers_unicode_names_and_numbering(self):
        self.assertEqual(parse_text("link\ttên tệp\nhttps://example.com/a.jpg\tẢnh đẹp.jpg\nhttps://example.com/b.pdf\t"),
                         [("https://example.com/a.jpg", "Ảnh đẹp.jpg"), ("https://example.com/b.pdf", "002.pdf")])

    def test_invalid_batch_reports_line(self):
        with self.assertRaisesRegex(ValueError, "Dòng 2"):
            parse_text("https://example.com/a\nfile:///private")


if __name__ == "__main__":
    unittest.main()
