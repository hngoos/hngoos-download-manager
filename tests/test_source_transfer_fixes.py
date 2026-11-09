"""Regressions for source routing, proxy isolation and server cooldowns."""

import tempfile
import threading
import unittest
import urllib.error
from email.message import Message
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import MagicMock, patch

from hngoos_dm.cloud import resolve
from hngoos_dm.engine import DownloadManager, Paused
from hngoos_dm.links import describe_source, resolve_source
from hngoos_dm.store import Store


def response(url, content_type="application/octet-stream"):
    result = MagicMock()
    result.__enter__.return_value = result
    result.geturl.return_value = url
    result.headers = Message()
    result.headers["Content-Type"] = content_type
    return result


class SourceTransferFixTests(unittest.TestCase):
    def test_metadata_redirect_stays_on_manual_proxy(self):
        seen = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass
            def do_GET(self):
                seen.append(self.path)
                if self.path == "http://origin.invalid/start":
                    self.send_response(302)
                    self.send_header("Location", "http://other.invalid/file")
                else:
                    self.send_response(200)
                    self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Length", "0")
                self.end_headers()
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        server.daemon_threads = True
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            proxy = {"mode": "manual", "url": f"http://127.0.0.1:{server.server_port}"}
            self.assertEqual(resolve_source("http://origin.invalid/start", proxy=proxy)[0], "file")
            self.assertEqual(seen, ["http://origin.invalid/start", "http://other.invalid/file"])
        finally:
            server.shutdown()
            server.server_close()

    def test_resolution_carries_proxy_to_cloud_and_metadata(self):
        proxy = {"mode": "manual", "url": "http://proxy.example:8080"}
        url = "https://example.com/file"
        with patch("hngoos_dm.cloud.resolve", return_value=url) as cloud, \
                patch("hngoos_dm.engine.request", return_value=response(url)) as request:
            self.assertEqual(resolve_source(url, proxy=proxy), ("file", url))
        cloud.assert_called_once_with(url, proxy=proxy)
        request.assert_called_once_with(url, {"Range": "bytes=0-0"}, proxy=proxy)

    def test_github_blob_uses_official_raw_endpoint_without_losing_encoded_path(self):
        self.assertEqual(resolve("https://github.com/owner/repo/blob/main/a%20b.txt?raw=true#L1"),
                         "https://raw.githubusercontent.com/owner/repo/main/a%20b.txt")
        url = "https://github.com/owner/repo/releases/download/v1/app.zip?token=abc"
        self.assertEqual(resolve(url), url)
        lookalike = "https://github.com.evil.example/owner/repo/blob/main/file"
        self.assertEqual(resolve(lookalike), lookalike)

    def test_manager_resolves_github_blob_when_added_without_ui(self):
        with tempfile.TemporaryDirectory() as folder:
            manager = DownloadManager(Store(Path(folder)/"db"))
            try:
                original = "https://github.com/owner/repo/blob/main/file.txt"
                job = manager.add(original, folder, "file.txt", start=False)
                self.assertEqual(manager.store.get(job)["url"],
                                 "https://raw.githubusercontent.com/owner/repo/main/file.txt")
                self.assertEqual(manager.store.get(job)["original_url"], original)
            finally:
                manager.close()

    def test_spotify_short_link_classifies_public_redirect_with_same_proxy(self):
        proxy = {"mode": "system", "url": ""}
        for path, kind in (("episode/public", "media"), ("track/music", "spotify")):
            final = "https://open.spotify.com/"+path
            with self.subTest(path=path), patch("hngoos_dm.engine.request", return_value=response(final)) as request:
                self.assertEqual(resolve_source("https://spotify.link/public", proxy=proxy), (kind, final))
                self.assertEqual(request.call_args.kwargs, {"proxy": proxy})

    def test_spotify_short_link_rejects_non_spotify_redirect(self):
        with patch("hngoos_dm.engine.request", return_value=response("https://example.com/episode/fake")), \
                self.assertRaises(ValueError):
            resolve_source("https://spotify.link/public")

    def test_spotify_preview_preserves_original_and_uses_resolved_episode(self):
        proxy = {"mode": "manual", "url": "http://proxy.example:8080"}
        final = "https://open.spotify.com/episode/public"
        with patch("hngoos_dm.engine.request", return_value=response(final)), \
                patch("hngoos_dm.media.describe_media", return_value={"title": "Podcast"}) as metadata:
            info = describe_source("https://spotify.link/public", proxy=proxy)
        self.assertEqual((info["original"], info["url"], info["kind"]),
                         ("https://spotify.link/public", final, "media"))
        metadata.assert_called_once_with(final, proxy=proxy)

    def test_retry_after_preserves_seconds_and_http_date_and_cancels_wait(self):
        for header, delay in (("120", 120), ("Sun, 08 Nov 2026 00:02:00 GMT", 120), ("invalid", 1)):
            with self.subTest(header=header), tempfile.TemporaryDirectory() as folder:
                manager = DownloadManager(Store(Path(folder)/"db"))
                try:
                    job = manager.add("https://example.com/file", folder, "file", connections=1, start=False)
                    headers = Message()
                    headers["Retry-After"] = header
                    error = urllib.error.HTTPError("https://example.com/file", 429, "Busy", headers, None)
                    stop = threading.Event()
                    with patch.object(manager, "_probe", return_value={"total": 4, "ranged": True,
                              "etag": '"v1"', "modified": "", "empty": False}), \
                            patch.object(manager, "_request", side_effect=error), \
                            patch.object(stop, "wait", return_value=True) as wait, \
                            patch("hngoos_dm.engine.time.time", return_value=1794096000):
                        with self.assertRaises(Paused):
                            manager._download(job, stop)
                        wait.assert_called_once_with(delay)
                finally:
                    manager.close()
                    manager.pool.shutdown(wait=True)
