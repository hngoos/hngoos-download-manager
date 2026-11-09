import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from hngoos_dm.engine import DownloadManager
from hngoos_dm.store import Store


class ProxyPreferencesTests(unittest.TestCase):
    def test_new_and_reset_settings_use_no_proxy_for_http_and_media(self):
        from hngoos_dm.network import media_proxy, validate_proxy
        from hngoos_dm.preferences import defaults
        self.assertEqual(validate_proxy({}), {"mode": "direct", "url": ""})
        self.assertEqual(defaults()["proxy"], {"mode": "direct", "url": ""})
        self.assertEqual(media_proxy(None), "")

    def test_media_extractor_honors_explicit_direct_or_manual_proxy(self):
        from hngoos_dm.media import MediaOptions, ydl_options
        direct = ydl_options(Path.cwd(), MediaOptions(proxy={"mode": "direct"}))
        self.assertEqual(direct["proxy"], "")
        manual = ydl_options(Path.cwd(), MediaOptions(proxy={"mode": "manual", "url": "http://localhost:8080"}))
        self.assertEqual(manual["proxy"], "http://localhost:8080")

    def test_manual_proxy_carries_metadata_and_all_downloaded_bytes(self):
        payload = b"download via configured proxy"*100
        seen = []
        class Proxy(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass
            def do_GET(self):
                seen.append(self.path)
                value = self.headers.get("Range", "bytes=0-0").split("=", 1)[1]
                start, end = map(int, value.split("-"))
                end = min(end, len(payload)-1)
                self.send_response(206)
                self.send_header("Content-Range", f"bytes {start}-{end}/{len(payload)}")
                self.send_header("Content-Length", str(end-start+1))
                self.send_header("ETag", '"proxy-fixture"')
                self.end_headers()
                self.wfile.write(payload[start:end+1])
        server = ThreadingHTTPServer(("127.0.0.1", 0), Proxy)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with tempfile.TemporaryDirectory() as folder:
                store = Store(Path(folder)/"db")
                store.set_setting("proxy", {"mode": "manual", "url": f"http://127.0.0.1:{server.server_port}"})
                manager = DownloadManager(store)
                try:
                    job_id = manager.add("http://hdm-fixture.invalid/file.txt", folder, "file.txt", start=False)
                    manager._download(job_id, threading.Event())
                    job = store.get(job_id)
                    self.assertEqual(job["state"], "complete", job["error"])
                    self.assertEqual(Path(job["output"]).read_bytes(), payload)
                    self.assertGreaterEqual(len(seen), 2)
                    self.assertEqual(set(seen), {"http://hdm-fixture.invalid/file.txt"})
                finally:
                    manager.close()
        finally:
            server.shutdown()
            server.server_close()

    def test_direct_mode_ignores_environment_proxy_and_media_receives_same_policy(self):
        from hngoos_dm.network import media_proxy, validate_proxy
        self.assertEqual(media_proxy({"mode": "direct", "url": ""}), "")
        self.assertIsNone(media_proxy({"mode": "system", "url": ""}))
        self.assertEqual(media_proxy({"mode": "manual", "url": "http://localhost:8888"}), "http://localhost:8888")
        for value in ({"mode": "unknown"}, {"mode": "manual", "url": "file:///tmp/p"},
                      {"mode": "manual", "url": "http://localhost:99999"},
                      {"mode": "manual", "url": "http://localhost/path"}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_proxy(value)
        import urllib.error
        import urllib.request

        from hngoos_dm.network import open_url
        with patch("urllib.request.build_opener", wraps=urllib.request.build_opener) as build:
            with self.assertRaises(urllib.error.URLError):
                open_url("http://127.0.0.1:1", timeout=.1, proxy={"mode": "direct"})
            self.assertEqual(build.call_args.args[0].proxies, {})
