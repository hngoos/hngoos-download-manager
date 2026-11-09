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
    def test_source_preview_passes_explicit_cookie_file_to_media_extractor(self):
        from hngoos_dm.links import describe_source

        with tempfile.TemporaryDirectory() as folder:
            cookie = Path(folder)/"cookies.txt"
            cookie.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")
            with patch("hngoos_dm.media.describe_media", return_value={"title": "Audio", "formats": []}) as extract:
                describe_source("https://zingmp3.vn/bai-hat/example/test.html", cookie_file=str(cookie))
            self.assertEqual(extract.call_args.kwargs["cookie_file"], str(cookie))

    def test_spotify_episode_is_not_blocked_as_a_drm_music_track(self):
        self.assertEqual(link_kind("https://open.spotify.com/episode/public-podcast"), "media")
        self.assertEqual(link_kind("https://open.spotify.com/track/private-track"), "spotify")

    def test_drive_usercontent_links_are_confirmed_before_file_metadata_request(self):
        from email.message import Message
        from urllib.parse import parse_qs, urlsplit

        from hngoos_dm.links import describe_source

        headers = Message()
        headers["Content-Type"] = "application/octet-stream"
        headers["Content-Disposition"] = 'attachment; filename="archive.rar"'
        headers["Content-Range"] = "bytes 0-0/477037502"
        with patch("hngoos_dm.engine.request") as request:
            request.return_value.__enter__.return_value = SimpleNamespace(headers=headers)
            result = describe_source("https://drive.usercontent.google.com/download?id=public-file&authuser=0")
        query = parse_qs(urlsplit(request.call_args.args[0]).query)
        self.assertEqual(query["confirm"], ["t"])
        self.assertEqual(query["authuser"], ["0"])
        self.assertEqual(result["kind"], "file")
        self.assertEqual(result["filename"], "archive.rar")

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
    def test_later_file_errors_preserve_earlier_threats_and_do_not_skip_other_files(self):
        from hngoos_dm.safety_ui import scan_files

        with tempfile.TemporaryDirectory() as directory:
            paths = [Path(directory)/name for name in ("flagged.bin", "missing.bin", "failed.bin", "clean.bin")]
            for path in (paths[0], paths[2], paths[3]):
                path.write_bytes(b"ordinary test fixture")
            visited = []
            def scanner(path):
                visited.append(Path(path).name)
                if Path(path).name == "failed.bin":
                    raise OSError("Scanner unavailable")
                return subprocess.CompletedProcess([], 2 if Path(path).name == "flagged.bin" else 0, "fixture", "")
            status, detail, threats = scan_files(paths, scanner)
            self.assertEqual(status, "threat")
            self.assertEqual(threats, [str(paths[0])])
            self.assertEqual(visited, ["flagged.bin", "failed.bin", "clean.bin"])
            self.assertIn("missing.bin", detail)
            self.assertIn("Scanner unavailable", detail)

    @unittest.skipUnless(os.name == "nt", "Windows immutable scan handle")
    def test_existing_writable_mapping_cannot_bypass_the_scan_guard(self):
        import mmap

        from hngoos_dm.safety_ui import unchanged_file
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"mapped.bin"
            path.write_bytes(b"original fixture")
            with path.open("r+b") as output:
                mapping = mmap.mmap(output.fileno(), 0, access=mmap.ACCESS_WRITE)
            try:
                with self.assertRaises(PermissionError), unchanged_file(path):
                    self.fail("A writable mapping must prevent the scan from claiming immutable bytes")
            finally:
                mapping.close()

    @unittest.skipUnless(os.name == "nt", "Windows immutable scan handle")
    def test_manual_scan_locks_bytes_without_two_extra_full_file_hash_passes(self):
        from hngoos_dm.safety_ui import scan_files

        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)/"fixture.bin"
            target.write_bytes(b"unchanged fixture")
            def scanner(path):
                with self.assertRaises(PermissionError):
                    Path(path).write_bytes(b"replacement")
                return subprocess.CompletedProcess([], 0, "", "")
            with patch("hngoos_dm.safety_ui.sha256_file", side_effect=AssertionError("Unnecessary full read")):
                status, _detail, _threats = scan_files([target], scanner)
            self.assertEqual(status, "clean")
            self.assertEqual(target.read_bytes(), b"unchanged fixture")
            target.write_bytes(b"lock released")
            self.assertEqual(target.read_bytes(), b"lock released")

    def test_manual_scan_checks_all_outputs_and_identifies_only_flagged_files(self):
        from hngoos_dm.safety_ui import scan_files

        with tempfile.TemporaryDirectory() as directory:
            paths = [Path(directory)/name for name in ("flagged.bin", "clean.bin", "another-flagged.bin")]
            for path in paths:
                path.write_bytes(b"synthetic fixture")
            visited = []
            def scanner(path):
                visited.append(Path(path).name)
                return subprocess.CompletedProcess([], 0 if Path(path).name == "clean.bin" else 2, "fixture", "")
            status, _detail, threats = scan_files(paths, scanner)
            self.assertEqual(status, "threat")
            self.assertEqual(visited, [path.name for path in paths])
            self.assertEqual(threats, [str(paths[0]), str(paths[2])])

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
                outputs = download_video("https://example.com/video", root/"output", staging_root=root/"staging", high_security=True)
            self.assertEqual({path.name for path in outputs}, {"clip.mp4", "cover.jpg.chuakiemtra"})
            self.assertFalse((root/"output/cover.jpg").exists())

    def test_disabled_media_checks_do_not_inspect_or_quarantine_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def extract(_url, staging, *_args):
                (staging/"cover.jpg").write_bytes(b"MZsynthetic executable")
            with patch("hngoos_dm.media._download_video", side_effect=extract), \
                    patch("hngoos_dm.safety.inspect_download", side_effect=AssertionError("Automatic checks are off")):
                outputs = download_video("https://example.com/video", root/"output",
                                         staging_root=root/"staging", high_security=False, antivirus=False)
            self.assertEqual([path.name for path in outputs], ["cover.jpg"])

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
                assembly_connections = []
                update = store.update

                def record_update(job_id, **changes):
                    # A throttled progress report may still show live connections
                    # after the last socket has closed. Assembly must clear it.
                    if changes.get("state") == "assembling":
                        update(job_id, active_connections=7)
                    update(job_id, **changes)
                    if changes.get("state") == "assembling":
                        assembly_connections.append(store.get(job_id)["active_connections"])

                store.update = record_update
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
                    self.assertEqual(assembly_connections, [0])
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
