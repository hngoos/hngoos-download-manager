"""Concurrent updates cannot corrupt the active downloader or share a partial file."""

import hashlib
import io
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from hngoos_dm import toolchain


@unittest.skipUnless(__import__("os").name == "nt", "Standalone video downloader updates are Windows-only")
class ToolchainTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.content = b"MZsynthetic updater fixture"
        self.digest = hashlib.sha256(self.content).hexdigest()
        self.release = {"tag_name": "2026.11.06", "assets": [{"name": "yt-dlp.exe", "size": len(self.content),
            "digest": "sha256:"+self.digest, "browser_download_url": "https://github.com/yt-dlp/yt-dlp/releases/download/test/yt-dlp.exe"}]}

    def response(self, request, **_kwargs):
        return io.BytesIO(json.dumps(self.release).encode() if request.full_url.startswith("https://api.github.com/")
                          else self.content)

    def test_update_does_not_use_a_shared_partial_filename(self):
        # Simulate another process holding the old fixed partial path on Windows.
        partial = self.root/"yt-dlp.exe.download"
        partial.write_bytes(b"another operation owns this data")
        with partial.open("rb") as held, patch.object(toolchain, "root", return_value=self.root), \
                patch.object(toolchain.urllib.request, "urlopen", side_effect=self.response):
            self.assertEqual(toolchain.update_ytdlp(), "2026.11.06")
            self.assertEqual(held.read(), b"another operation owns this data")
        self.assertEqual((self.root/"yt-dlp.exe").read_bytes(), self.content)
        self.assertEqual(partial.read_bytes(), b"another operation owns this data")
        metadata = json.loads((self.root/"yt-dlp.json").read_text())
        self.assertEqual(metadata["sha256"], self.digest)

    def test_checksum_failure_preserves_the_existing_tool(self):
        (self.root/"yt-dlp.exe").write_bytes(b"previous version")
        self.release["assets"][0]["digest"] = "sha256:"+"0"*64
        with patch.object(toolchain, "root", return_value=self.root), \
                patch.object(toolchain.urllib.request, "urlopen", side_effect=self.response), \
                self.assertRaisesRegex(ValueError, "SHA-256"):
            toolchain.update_ytdlp()
        self.assertEqual((self.root/"yt-dlp.exe").read_bytes(), b"previous version")

    def test_current_verified_binary_is_not_downloaded_again(self):
        (self.root/"yt-dlp.exe").write_bytes(self.content)
        (self.root/"yt-dlp.json").write_text(json.dumps({"version": "2026.11.06", "sha256": self.digest}))
        with patch.object(toolchain, "root", return_value=self.root), \
                patch.object(toolchain.urllib.request, "urlopen", side_effect=self.response) as request:
            self.assertEqual(toolchain.update_ytdlp(), "2026.11.06")
        self.assertEqual(request.call_count, 1)
        self.assertEqual((self.root/"yt-dlp.exe").read_bytes(), self.content)

    def test_second_update_is_rejected_before_it_can_touch_the_first_download(self):
        started, release = threading.Event(), threading.Event()
        errors = []
        def response(request, **kwargs):
            if request.full_url.startswith("https://api.github.com/"):
                started.set()
                if not release.wait(5):
                    raise TimeoutError("fixture timed out")
            return self.response(request, **kwargs)
        def run():
            try:
                toolchain.update_ytdlp()
            except Exception as error:  # noqa: BLE001 -- Propagate any worker failure to the test thread.
                errors.append(error)
        with patch.object(toolchain, "root", return_value=self.root), \
                patch.object(toolchain.urllib.request, "urlopen", side_effect=response):
            worker = threading.Thread(target=run)
            worker.start()
            try:
                self.assertTrue(started.wait(2))
                with self.assertRaisesRegex(ValueError, "đang được cập nhật"):
                    toolchain.update_ytdlp()
            finally:
                release.set()
                worker.join(5)
        self.assertEqual(errors, [])
        self.assertEqual((self.root/"yt-dlp.exe").read_bytes(), self.content)
