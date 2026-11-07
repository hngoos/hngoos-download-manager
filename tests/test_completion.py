import csv
import hashlib
import os
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from hngoos_dm.policy import HostPolicy
from hngoos_dm.safety import hash_lookup_url, inspect_file
from hngoos_dm.store import Store


class BackgroundSafetyTests(unittest.TestCase):
    def setUp(self):
        from hngoos_dm.engine import DownloadManager
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root/"file.zip"
        self.source.write_bytes(b"safety fixture")
        self.digest = hashlib.sha256(self.source.read_bytes()).hexdigest()
        self.store = Store(self.root/"db")
        row = self.store.create("https://example.com/file.zip", self.root, self.source.name)
        self.job_id = row["id"]
        self.store.update(self.job_id, state="complete", output=str(self.source),
                          safety_check={"provider": "defender", "status": "scanning"})
        self.manager = DownloadManager.__new__(DownloadManager)
        self.manager.store = self.store
        self.manager.closed = False
        self.manager.scheduler_stop = threading.Event()
        self.manager._extract_completed = MagicMock()

    def scan(self, returncode=0, side_effect=None):
        with patch("hngoos_dm.safety.scan_defender", side_effect=side_effect,
                   return_value=subprocess.CompletedProcess([], returncode, "scan result", "")):
            self.manager._scan_completed(self.job_id, self.source, self.digest, False)

    def test_clean_scan_allows_extraction_and_records_result(self):
        self.scan()
        self.assertEqual(self.store.get(self.job_id)["safety_check"]["status"], "clean")
        self.manager._extract_completed.assert_called_once_with(self.job_id, self.source)

    def test_scan_risk_preserves_file_in_quarantine_and_does_not_extract(self):
        self.scan(returncode=2)
        row = self.store.get(self.job_id)
        self.assertEqual(row["state"], "quarantined")
        self.assertEqual(row["safety_check"]["status"], "threat")
        self.assertEqual(Path(row["output"]).read_bytes(), b"safety fixture")
        self.manager._extract_completed.assert_not_called()

    def test_unavailable_scanner_changed_file_and_rename_failure_never_report_safe(self):
        self.scan(side_effect=FileNotFoundError("Scanner unavailable"))
        self.assertEqual(self.store.get(self.job_id)["safety_check"]["status"], "error")
        self.source.write_bytes(b"changed")
        self.scan()
        self.assertEqual(self.store.get(self.job_id)["safety_check"]["status"], "error")
        self.source.write_bytes(b"safety fixture")
        with patch("hngoos_dm.engine.deliver", side_effect=PermissionError("File locked")):
            self.scan(returncode=2)
        self.assertEqual(self.store.get(self.job_id)["safety_check"]["status"], "error")
        self.manager._extract_completed.assert_not_called()

    def test_removing_history_during_scan_does_not_recreate_entry(self):
        def remove(*_args, **_kwargs):
            self.store.delete(self.job_id)
            return subprocess.CompletedProcess([], 0, "", "")
        self.scan(side_effect=remove)
        self.assertEqual(self.store.all(), [])
        self.assertTrue(self.source.exists())
        with self.assertRaises(KeyError):
            self.store.update(self.job_id, state="complete")

    def test_interrupted_scan_recovery_keeps_completed_download(self):
        self.store.recover()
        row = self.store.get(self.job_id)
        self.assertEqual(row["state"], "complete")
        self.assertEqual(row["safety_check"]["status"], "error")
        self.assertEqual(row["output"], str(self.source))

    def test_cancelling_defender_reaps_only_its_own_launcher(self):
        from hngoos_dm.policy import TransferCancelled
        from hngoos_dm.safety import scan_defender
        stop = threading.Event()
        process = MagicMock()
        process.__enter__.return_value = process
        process.poll.return_value = None
        def pending(*_args, **_kwargs):
            if not stop.is_set():
                stop.set()
                raise subprocess.TimeoutExpired("scan", .25)
            return "", ""
        process.communicate.side_effect = pending
        with patch("hngoos_dm.safety.Path.is_file", return_value=True), \
                patch("hngoos_dm.safety.subprocess.Popen", return_value=process), \
                self.assertRaises(TransferCancelled):
            scan_defender(self.source, stop=stop)
        process.kill.assert_called_once()
        self.assertEqual(process.communicate.call_count, 2)


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
