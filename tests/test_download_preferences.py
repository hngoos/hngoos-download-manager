import tempfile
import time
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from hngoos_dm.engine import DownloadManager
from hngoos_dm.store import Store


class DownloadPreferenceTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.store = Store(Path(self.folder.name)/"jobs.sqlite3")
        self.manager = DownloadManager(self.store)
        self.manager.scheduler_stop.set()
        self.manager.scheduler.join()
        self.addCleanup(lambda: self.manager.pool.shutdown(wait=True))
        self.addCleanup(self.manager.close)

    def job(self, name, state="complete"):
        path = Path(self.folder.name)/name
        path.write_bytes(b"keep these bytes")
        job = self.store.create("https://example.com/"+name, path.parent, name)
        return self.store.update(job["id"], state=state, output=str(path)), path

    def test_direct_drive_download_is_confirmed_when_added_without_a_preview(self):
        url = "https://drive.usercontent.google.com/download?id=public-file&authuser=0"
        direct = url+"&confirm=t"
        with patch("hngoos_dm.cloud.resolve", return_value=direct) as resolve:
            job_id = self.manager.add(url, self.folder.name, "archive.rar", start=False)
        resolve.assert_called_once_with(url)
        self.assertEqual(self.store.get(job_id)["url"], direct)
        self.assertEqual(self.store.get(job_id)["original_url"], url)

    def test_journal_preserves_missing_completed_and_quarantined_files_even_with_legacy_cleanup_enabled(self):
        missing, path = self.job("missing.txt")
        path.unlink()
        existing, kept = self.job("kept.txt")
        quarantine, unsafe = self.job("unsafe.chuakiemtra", "quarantined")
        unsafe.unlink()
        self.store.set_setting("remove_missing", True)
        self.store.set_setting("remove_completed", True)
        self.manager.maintain_history()
        self.assertEqual({job["id"] for job in self.store.all()}, {missing["id"], existing["id"], quarantine["id"]})
        self.assertEqual(kept.read_bytes(), b"keep these bytes")

    def test_transient_failure_gets_bounded_retry_but_security_or_auth_failure_does_not(self):
        for error, retry in ((TimeoutError("offline"), True),
                             (urllib.error.HTTPError("https://example.com", 503, "busy", {}, None), True),
                             (urllib.error.HTTPError("https://example.com", 403, "denied", {}, None), False),
                             (ValueError("hash mismatch"), False)):
            with self.subTest(error=error):
                job = self.store.create("https://example.com/file", self.folder.name, "file")
                import threading
                with patch.object(self.manager, "_download", side_effect=error):
                    self.manager._run(job["id"], threading.Event())
                failed = self.store.get(job["id"])
                self.assertEqual(failed["state"], "error")
                self.assertEqual(failed.get("retry_at", 0) > time.time(), retry)
                if retry:
                    self.store.update(job["id"], retry_count=3)
                    with patch.object(self.manager, "_download", side_effect=error):
                        self.manager._run(job["id"], threading.Event())
                    self.assertEqual(self.store.get(job["id"]).get("retry_at", 0), 0)

    def test_due_retry_respects_disabled_setting_and_user_pause(self):
        job = self.store.create("https://example.com/file", self.folder.name, "file")
        self.store.update(job["id"], state="error", retry_at=1)
        self.store.set_setting("retry_failed", False)
        self.manager._schedule_once(time.time())
        self.assertEqual(self.store.get(job["id"])["state"], "error")
        self.manager.pause(job["id"])
        self.store.set_setting("retry_failed", True)
        self.manager._schedule_once(time.time())
        self.assertEqual(self.store.get(job["id"])["state"], "paused")
        self.assertEqual(self.store.get(job["id"]).get("retry_at", 0), 0)

    def test_scheduled_snapshot_cannot_restart_a_removed_download(self):
        job = self.store.create("https://example.com/file", self.folder.name, "file")
        self.store.update(job["id"], state="scheduled", scheduled_at=1)
        snapshot = self.store.all()
        self.store.delete(job["id"])
        with patch.object(self.store, "all", return_value=snapshot):
            self.manager._schedule_once(time.time())
        self.assertEqual(self.manager.active, {})
        self.assertEqual(self.store.all(), [])

    def test_due_retry_restarts_the_download_and_retains_retry_budget(self):
        job = self.store.create("https://example.com/file", self.folder.name, "file")
        self.store.update(job["id"], state="error", retry_at=1, retry_count=2)
        def complete(job_id, _stop):
            self.store.update(job_id, state="complete")
        with patch.object(self.manager, "_download", side_effect=complete):
            self.manager._schedule_once(time.time())
            limit = time.monotonic()+3
            while self.store.get(job["id"])["state"] != "complete" and time.monotonic() < limit:
                time.sleep(.01)
        self.assertEqual(self.store.get(job["id"])["state"], "complete")
        self.assertEqual(self.store.get(job["id"])["retry_count"], 2)
