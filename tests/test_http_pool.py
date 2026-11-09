"""HTTP/1.1 reuse must preserve normal request and response boundaries."""

import ssl
import tempfile
import threading
import time
import unittest
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch


class PoolTests(unittest.TestCase):
    def test_shutdown_does_not_block_ui_on_an_active_response_read(self):
        from hngoos_dm.http_pool import HTTPPool
        ready, reading, release, finished = (threading.Event() for _ in range(4))
        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"
            def log_message(self, *_args):
                pass
            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Length", "100")
                self.end_headers()
                self.wfile.flush()
                ready.set()
                release.wait(8)
                self.close_connection = True
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        server.daemon_threads = True
        threading.Thread(target=server.serve_forever, daemon=True).start()
        pool = HTTPPool()
        errors = []
        def read():
            try:
                with pool.request(f"http://127.0.0.1:{server.server_port}/") as response:
                    reading.set()
                    response.read(100)
            except (OSError, urllib.error.URLError) as error:
                errors.append(error)
            finally:
                finished.set()
        worker = threading.Thread(target=read, daemon=True)
        try:
            worker.start()
            self.assertTrue(ready.wait(5))
            self.assertTrue(reading.wait(5))
            began = time.monotonic()
            pool.close()
            self.assertLess(time.monotonic()-began, 1, "Closing connections blocked on a response read")
            release.set()
            self.assertTrue(finished.wait(2), "Download did not release its closed connection")
            self.assertFalse(pool.connections)
        finally:
            release.set()
            worker.join(5)
            pool.close()
            server.shutdown()
            server.server_close()

    def setUp(self):
        self.received = []
        owner = self
        class Server(ThreadingHTTPServer):
            daemon_threads = True
            accepted = 0
            def get_request(server):
                connection = super().get_request()
                server.accepted += 1
                return connection
            def handle_error(server, *_args):
                pass  # An intentionally discarded unread response resets its socket.
        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"
            def log_message(self, *_args):
                pass
            def do_GET(self):
                owner.received.append((self.path, self.headers.get("Authorization"), self.headers.get("Cookie")))
                if self.path == "/truncated":
                    self.send_response(200)
                    self.send_header("Content-Length", "100")
                    self.end_headers()
                    self.wfile.write(b"short")
                    self.close_connection = True
                    return
                if self.path == "/chunked":
                    self.send_response(200)
                    self.send_header("Transfer-Encoding", "chunked")
                    self.end_headers()
                    self.wfile.write(b"5\r\nhello\r\n0\r\n\r\n")
                    return
                if self.path in {"/redirect", "/other-host", "/loop"}:
                    self.send_response(302)
                    self.send_header("Location", f"http://localhost:{self.server.server_port}/file" if self.path == "/other-host"
                                     else "/loop" if self.path == "/loop" else "/file")
                    body = b"redirect"
                elif self.path == "/missing":
                    self.send_response(404)
                    body = b"missing"
                else:
                    self.send_response(200)
                    body = b"ordinary bytes"
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Content-Type", "application/octet-stream")
                self.end_headers()
                self.wfile.write(body)
                if self.path == "/stale":
                    self.close_connection = True
        self.server = Server(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def pool(self):
        from hngoos_dm.http_pool import HTTPPool
        pool = HTTPPool()
        self.addCleanup(pool.close)
        return pool

    def test_fully_consumed_responses_reuse_one_connection(self):
        pool = self.pool()
        for _ in range(5):
            with pool.request(self.base+"/file") as response:
                self.assertEqual(response.read(), b"ordinary bytes")
                self.assertEqual(response.headers.get_content_type(), "application/octet-stream")
        self.assertEqual(self.server.accepted, 1)

    def test_download_manager_uses_pooled_direct_connections(self):
        from hngoos_dm.engine import DownloadManager
        from hngoos_dm.store import Store
        with tempfile.TemporaryDirectory() as folder:
            manager = DownloadManager(Store(Path(folder)/"db"))
            try:
                for _ in range(5):
                    with manager._request(self.base+"/file") as response:
                        self.assertEqual(response.read(), b"ordinary bytes")
            finally:
                manager.close()
        self.assertEqual(self.server.accepted, 1)

    def test_early_close_discards_unread_response_before_the_next_request(self):
        pool = self.pool()
        with pool.request(self.base+"/file") as response:
            self.assertEqual(response.read(1), b"o")
        with pool.request(self.base+"/file") as response:
            self.assertEqual(response.read(), b"ordinary bytes")
        self.assertEqual(self.server.accepted, 2)

    def test_truncated_response_is_never_reused(self):
        pool = self.pool()
        with pool.request(self.base+"/truncated") as response:
            self.assertEqual(response.read(100), b"short")
            self.assertEqual(response.read(100), b"")
        self.assertFalse(pool.idle[next(iter(pool.idle))])
        with pool.request(self.base+"/file") as response:
            self.assertEqual(response.read(), b"ordinary bytes")

    def test_chunked_response_reuses_only_after_terminating_chunk(self):
        pool = self.pool()
        with pool.request(self.base+"/chunked") as response:
            self.assertEqual(response.read(), b"hello")
        with pool.request(self.base+"/file") as response:
            self.assertEqual(response.read(), b"ordinary bytes")
        self.assertEqual(self.server.accepted, 1)

    def test_stale_idle_socket_reconnects_without_replaying_consumed_bytes(self):
        pool = self.pool()
        with pool.request(self.base+"/stale") as response:
            self.assertEqual(response.read(), b"ordinary bytes")
        with pool.request(self.base+"/file") as response:
            self.assertEqual(response.read(), b"ordinary bytes")
        self.assertEqual(self.server.accepted, 2)

    def test_cross_origin_redirect_strips_account_headers_and_loops_are_bounded(self):
        pool = self.pool()
        with pool.request(self.base+"/other-host", {"Authorization": "secret", "Cookie": "account=session"}) as response:
            self.assertEqual(response.read(), b"ordinary bytes")
        self.assertEqual(self.received[-1], ("/file", None, None))
        with self.assertRaises(urllib.error.HTTPError):
            pool.request(self.base+"/loop")
        self.assertLessEqual(len(self.received), 13)

    def test_closed_pool_cannot_start_new_requests(self):
        pool = self.pool()
        pool.close()
        with self.assertRaises(OSError):
            pool.request(self.base+"/file")

    def test_shutdown_between_acquire_and_connect_cannot_reopen_a_socket(self):
        pool = self.pool()
        acquire = pool.acquire
        def close_before_request(key):
            lease = acquire(key)
            pool.close()
            return lease
        with patch.object(pool, "acquire", side_effect=close_before_request), \
                self.assertRaises((OSError, urllib.error.URLError)):
            pool.request(self.base+"/file")
        self.assertEqual(self.received, [])

    def test_redirects_and_http_errors_preserve_urllib_contract(self):
        pool = self.pool()
        with pool.request(self.base+"/redirect") as response:
            self.assertEqual(response.geturl(), self.base+"/file")
            self.assertEqual(response.read(), b"ordinary bytes")
        with self.assertRaises(urllib.error.HTTPError) as failure:
            pool.request(self.base+"/missing")
        self.assertEqual(failure.exception.code, 404)
        with pool.request(self.base+"/file") as response:
            self.assertEqual(response.read(), b"ordinary bytes")

    def test_tls_certificate_failures_never_fall_back_to_http(self):
        pool = self.pool()
        with patch("hngoos_dm.http_pool.http.client.HTTPSConnection") as https, \
                patch("hngoos_dm.http_pool.http.client.HTTPConnection") as http:
            https.return_value.request.side_effect = ssl.SSLCertVerificationError("untrusted certificate")
            with self.assertRaises((ssl.SSLCertVerificationError, urllib.error.URLError)):
                pool.request("https://example.com/file")
        http.assert_not_called()
