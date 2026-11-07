import os
import plistlib
import subprocess
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from hngoos_dm.engine import DownloadManager
from hngoos_dm.links import clipboard_link, link_kind, resolve_source
from hngoos_dm.media import MediaOptions, download_video, ydl_options
from hngoos_dm.safety import inspect_download
from hngoos_dm.startup import set_enabled
from hngoos_dm.store import Store


class LinkTests(unittest.TestCase):
    def test_video_selector_accepts_unknown_resolution_and_honors_known_limit(self):
        from yt_dlp import YoutubeDL
        settings = ydl_options("out", MediaOptions(height=720), ffmpeg="ffmpeg")
        with YoutubeDL({"quiet": True}) as downloader:
            selector = downloader.build_format_selector(settings["format"])
            unknown = {"format_id": "direct", "ext": "mp4", "vcodec": "h264", "acodec": "aac",
                       "url": "https://example.com/file.mp4"}
            self.assertEqual(downloader._select_formats([unknown], selector)[0]["format_id"], "direct")
            low = dict(unknown, format_id="low", height=360)
            high = dict(unknown, format_id="high", height=1080)
            self.assertEqual(downloader._select_formats([low, high], selector)[0]["format_id"], "low")

    def test_media_metadata_reports_real_heights_and_visible_error_instead_of_blank_name(self):
        from hngoos_dm.links import describe_source
        from hngoos_dm.media import describe_media
        url = "https://youtu.be/example"
        info = {"title": "A video", "formats": [
            {"height": 720, "vcodec": "avc1"}, {"height": 360, "vcodec": "avc1"},
            {"height": 1080, "vcodec": "avc1", "has_drm": True}, {"vcodec": "none"}]}
        with patch("yt_dlp.YoutubeDL") as extractor:
            extractor.return_value.__enter__.return_value.extract_info.return_value = info
            metadata = describe_media(url)
            self.assertEqual(metadata["heights"], [360, 720])
            self.assertFalse(extractor.call_args.args[0]["extract_flat"])
        with patch("hngoos_dm.media.describe_media", return_value=metadata):
            description = describe_source(url)
            self.assertEqual(description["filename"], "A video.mp4")
            self.assertEqual(description["heights"], [360, 720])
        with patch("hngoos_dm.media.describe_media", side_effect=ValueError("Sign in required")):
            description = describe_source(url)
            self.assertTrue(description["filename"])
            self.assertEqual(description["metadata_error"], "Sign in required")

    def test_enter_metadata_uses_server_filename_and_full_range_size_without_saving_a_file(self):
        from email.message import Message

        from hngoos_dm.links import describe_source
        headers = Message()
        headers["Content-Type"] = "application/pdf"
        headers["Content-Disposition"] = 'attachment; filename="Invoice 2026.pdf"'
        headers["Content-Range"] = "bytes 0-0/4096"
        headers["Content-Length"] = "1"
        with patch("hngoos_dm.engine.request") as request:
            request.return_value.__enter__.return_value = SimpleNamespace(headers=headers)
            result = describe_source("https://example.com/get?id=private-token")
            self.assertEqual(result["filename"], "Invoice 2026.pdf")
            self.assertEqual(result["size"], 4096)
            self.assertEqual(result["kind"], "file")
            request.assert_called_once_with("https://example.com/get?id=private-token", {"Range": "bytes=0-0"})

    def test_clipboard_accepts_links_without_network_and_rejects_text_and_credentials(self):
        with patch("urllib.request.urlopen", side_effect=AssertionError("Clipboard must stay local")):
            self.assertEqual(clipboard_link(" https://youtu.be/example "), "https://youtu.be/example")
            self.assertEqual(link_kind("https://youtube.com/watch?v=test"), "media")
            self.assertEqual(link_kind("https://youtube.com.attacker.example/file.zip"), "file")
            self.assertEqual(link_kind("https://cdn.example/live.m3u8?token=x"), "media")
            self.assertEqual(link_kind("https://open.spotify.com/track/example"), "spotify")
            for text in ("some copied text", "https://a.example https://b.example", "file:///C:/test",
                         "https://user:password@example.com/file", "https://example.com/\nsecret"):
                self.assertIsNone(clipboard_link(text))

    def test_html_is_routed_to_media_and_direct_files_stay_files(self):
        from email.message import Message
        for content_type, expected in (("text/html", "media"), ("application/octet-stream", "file")):
            headers = Message()
            headers["Content-Type"] = content_type
            response = SimpleNamespace(headers=headers)
            with patch("hngoos_dm.engine.request") as request:
                request.return_value.__enter__.return_value = response
                self.assertEqual(resolve_source("https://example.com/resource")[0], expected)


class SafetyPipelineTests(unittest.TestCase):
    def test_antivirus_error_and_unavailable_are_not_reported_as_clean(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"photo.jpg"
            path.write_bytes(b"ordinary fixture")
            with patch("hngoos_dm.safety.scan_defender", side_effect=FileNotFoundError):
                result = inspect_download(path, path.name, antivirus=True)
                self.assertEqual(result["safety_note"], "Sơ bộ · Defender chưa quét")
            with patch("hngoos_dm.safety.scan_defender", return_value=subprocess.CompletedProcess([], 2)):
                self.assertTrue(inspect_download(path, path.name, antivirus=True)["reasons"])
            with patch("hngoos_dm.safety.scan_defender", return_value=subprocess.CompletedProcess([], 0)):
                self.assertEqual(inspect_download(path, path.name, antivirus=True)["safety_note"], "Sơ bộ + Defender")

    def test_media_publication_checks_every_output_including_unreported_sidecars(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def extract(_url, staging, *_args):
                (staging/"clip.mp4").write_bytes(b"video fixture")
                (staging/"cover.jpg").write_bytes(b"MZsynthetic executable")
            with patch("hngoos_dm.media._download_video", side_effect=extract):
                outputs = download_video("https://example.com/video", root/"output", staging_root=root/"staging")
            self.assertEqual({path.name for path in outputs}, {"clip.mp4", "cover.jpg.chuakiemtra"})
            self.assertFalse((root/"output/cover.jpg").exists())

    def test_media_options_bound_fragment_workers_and_keep_custom_name_literal(self):
        options = ydl_options("/output", MediaOptions(connections=100, filename="100% holiday.mp4"))
        self.assertEqual(options["concurrent_fragment_downloads"], 32)
        self.assertIn("100%% holiday.%(ext)s", options["outtmpl"])
        self.assertFalse(options["allow_unplayable_formats"])


class ParallelTransferTests(unittest.TestCase):
    def test_thirty_two_live_connections_publish_exact_content(self):
        import hashlib
        total = 32*1024*1024
        payload = b"x"*(1024*1024)
        gate, lock = threading.Event(), threading.Lock()
        live = [0, 0]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_GET(self):
                start, end = map(int, self.headers["Range"][6:].split("-"))
                if end:
                    with lock:
                        live[0] += 1
                        live[1] = max(live)
                        if live[0] == 32:
                            gate.set()
                    gate.wait(12)
                try:
                    self.send_response(206)
                    self.send_header("Content-Length", str(end-start+1))
                    self.send_header("Content-Range", f"bytes {start}-{end}/{total}")
                    self.send_header("ETag", '"fixed-fixture"')
                    self.end_headers()
                    self.wfile.write(payload[:end-start+1])
                finally:
                    if end:
                        with lock:
                            live[0] -= 1
        class Server(ThreadingHTTPServer):
            request_queue_size = 128
            daemon_threads = True
        server = Server(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                store = Store(root/"jobs.sqlite3")
                manager = DownloadManager(store)
                try:
                    job_id = manager.add(f"http://127.0.0.1:{server.server_port}/data.bin", root/"out", "data.bin")
                    deadline = time.monotonic()+30
                    while time.monotonic() < deadline:
                        job = store.get(job_id)
                        if job["state"] in {"complete", "error"} and job_id not in manager.active:
                            break
                        time.sleep(0.02)
                    self.assertEqual(job["state"], "complete", job["error"])
                    self.assertEqual(live[1], 32)
                    self.assertEqual(job["peak_connections"], 32)
                    self.assertEqual(job["active_connections"], 0)
                    self.assertEqual(job["filename"], "data.bin")
                    self.assertEqual(job["sha256"], hashlib.sha256(payload*32).hexdigest())
                finally:
                    gate.set()
                    manager.close()
                    manager.pool.shutdown(wait=True)
        finally:
            gate.set()
            server.shutdown()
            server.server_close()


class StartupTests(unittest.TestCase):
    def test_linux_and_macos_enable_disable_only_per_user_files(self):
        for platform in ("linux", "darwin"):
            with self.subTest(platform=platform), tempfile.TemporaryDirectory() as directory, \
                    patch("hngoos_dm.startup.sys.platform", platform), \
                    patch("hngoos_dm.startup.Path.home", return_value=Path(directory)), \
                    patch.dict(os.environ, {"XDG_CONFIG_HOME": str(Path(directory)/"config")}), \
                    patch("hngoos_dm.startup.launch_command", return_value=["/app with spaces/HDM", "--safe"]):
                from hngoos_dm.startup import startup_file
                set_enabled(True)
                path = startup_file()
                self.assertTrue(path.is_file())
                if platform == "darwin":
                    value = plistlib.loads(path.read_bytes())
                    self.assertEqual(value["ProgramArguments"], ["/app with spaces/HDM", "--safe"])
                    self.assertTrue(value["RunAtLoad"])
                else:
                    self.assertIn('Exec="/app with spaces/HDM" "--safe"', path.read_text())
                set_enabled(False)
                self.assertFalse(path.exists())

    @unittest.skipUnless(os.name == "nt", "Windows startup registry")
    def test_windows_quotes_path_and_changes_only_hdm_value(self):
        import winreg
        with patch("winreg.CreateKey") as create, patch("winreg.SetValueEx") as write, \
                patch("winreg.DeleteValue") as delete, \
                patch("hngoos_dm.startup.launch_command", return_value=[r"C:\App with spaces\HDM.exe"]):
            set_enabled(True)
            self.assertEqual(create.call_args.args[0], winreg.HKEY_CURRENT_USER)
            self.assertEqual(write.call_args.args[1], "HDM")
            self.assertEqual(write.call_args.args[-1], '"C:\\App with spaces\\HDM.exe"')
            set_enabled(False)
            self.assertEqual(delete.call_args.args[1], "HDM")
