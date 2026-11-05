import csv
import os
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from hngoos_dm.policy import HostPolicy
from hngoos_dm.safety import hash_lookup_url, inspect_file
from hngoos_dm.store import Store


class CompletionTests(unittest.TestCase):
    def test_native_video_referrer_excludes_private_page_path_and_tokens(self):
        from hngoos_dm.bridge import handle_message
        from hngoos_dm.media import MediaOptions, ydl_options
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory)/"db")
            handle_message({"action":"download", "kind":"video", "url":"https://cdn.example/stream.m3u8",
                            "referrer":"https://source.example/private?token=secret"}, store)
            queued = store.inbox()[0][1]
            self.assertEqual(queued["referrer"], "https://source.example/")
            self.assertEqual(ydl_options(directory, MediaOptions(referrer=queued["referrer"]))["http_headers"],
                             {"Referer":"https://source.example/"})
            with self.assertRaises(ValueError):
                handle_message({"action":"download", "kind":"video", "url":"https://cdn.example/stream.m3u8",
                                "referrer":"https://source.example/\r\nCookie: secret"}, store)

    def test_host_recovery_requires_both_time_and_success_and_resets_after_penalty(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory)/"db")
            policy = HostPolicy(store, default_limit=8, recovery_seconds=300, recovery_successes=2)
            url = "https://example.com/file"
            with patch("hngoos_dm.policy.time.time", return_value=1000):
                policy.penalize(url, retry_after=0)
                policy.succeeded(url)
                policy.succeeded(url)
            self.assertEqual(policy.limits[policy.key(url)], 4)
            policy = HostPolicy(store, default_limit=8, recovery_seconds=300, recovery_successes=2)
            with patch("hngoos_dm.policy.time.time", return_value=1301):
                policy.succeeded(url)
            self.assertEqual(policy.limits[policy.key(url)], 5)
            with patch("hngoos_dm.policy.time.time", return_value=1302):
                policy.penalize(url, retry_after=0)
            self.assertEqual(policy.limits[policy.key(url)], 2)

    def test_batch_report_preserves_order_and_excludes_urls_and_tokens(self):
        from hngoos_dm.batch_ui import export_batch_report
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = Store(root/"db")
            for index in range(2):
                job = store.create("https://example.com/file?token=private", root, "=FORMULA.csv")
                store.update(job["id"], batch_id="fixture", batch_row=index+1)
            export_batch_report(store, root/"report.csv")
            report = (root/"report.csv").read_text(encoding="utf-8-sig")
            self.assertNotIn("private", report)
            self.assertNotIn("https://", report)
            rows = list(csv.reader(report.splitlines()))
            self.assertEqual([row[1] for row in rows[1:]], ["1", "2"])
            self.assertTrue(rows[1][2].startswith("'="))

    def test_hash_services_validate_digest_and_never_accept_upload_paths(self):
        for service in ("VirusTotal", "MetaDefender", "Kaspersky"):
            self.assertIn("a"*64, hash_lookup_url("a"*64, service))
        for value in ("a"*63, "C:/private.txt", "a"*64+"?secret"):
            with self.assertRaises(ValueError):
                hash_lookup_url(value)

    def test_high_security_never_accepts_unsigned_executable(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)/"setup.exe"
            source.write_bytes(b"MZsynthetic fixture")
            with patch("hngoos_dm.safety.authenticode", return_value={"status":"NotSigned"}):
                reasons = inspect_file(source, source.name, high_security=True)
            self.assertTrue(any("An toàn cao" in reason for reason in reasons))

    @unittest.skipUnless(os.name == "nt", "Bundled Windows archive tools")
    def test_real_encrypted_7z_detects_disguised_program_and_wrong_password(self):
        from hngoos_dm.archive_tools import executable
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/"photo.jpg").write_bytes(b"MZsynthetic fixture")
            archive = root/"locked.7z"
            subprocess.run([executable(), "a", "-pfixture-test", "-mhe=on", str(archive), str(root/"photo.jpg")],
                           check=True, capture_output=True, timeout=20)
            self.assertTrue(any("photo.jpg" in reason for reason in inspect_file(archive, archive.name, "fixture-test")))
            self.assertTrue(inspect_file(archive, archive.name, "wrong-password"))

    def test_media_is_published_only_after_success_and_does_not_export_cookie_files(self):
        from hngoos_dm.media import MediaOptions, download_video
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            destination = root/"cloud"
            def download(_url, staging, *_args):
                self.assertNotEqual(staging, destination)
                self.assertFalse(destination.exists())
                (staging/"movie.mp4").write_bytes(b"completed video")
            with patch("hngoos_dm.media._download_video", side_effect=download), patch(
                    "hngoos_dm.paths.data_directory", return_value=root/"data"):
                outputs = download_video("https://example.com/video", destination,
                                         options=MediaOptions(), stop=threading.Event())
            self.assertEqual(outputs[0].read_bytes(), b"completed video")
            self.assertEqual([p.name for p in destination.iterdir() if ":" not in p.name], ["movie.mp4"])
