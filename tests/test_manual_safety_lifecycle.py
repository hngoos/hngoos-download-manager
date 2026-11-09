"""Keep manual scan results accurate when journal rows or outputs change."""

import queue
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from hngoos_dm.app import App
from hngoos_dm.files import deliver
from hngoos_dm.store import Store


class ManualSafetyLifecycleTests(unittest.TestCase):
    def test_file_changed_after_scan_before_ui_callback_is_not_reported_safe(self):
        source = self.folder/"changed-after-scan.bin"
        source.write_bytes(b"clean original")
        job = self.app.store.create("https://example.com/file", self.folder, source.name)
        self.app.store.update(job["id"], state="complete", output=str(source))
        with patch("hngoos_dm.safety_ui.scan_files", return_value=("clean", "", [])):
            self.app.check_selected_safety(job["id"])
            self.app.background_threads[-1].join(5)
        source.write_bytes(b"replacement content after Defender finished")
        self.app.events.get(timeout=5)()
        current = self.app.store.get(job["id"])
        self.assertEqual(current["safety_check"]["status"], "error")
        self.assertTrue(source.is_file())

    def test_deleted_output_while_scan_result_is_queued_is_not_reported_safe(self):
        source = self.folder/"deleted-after-scan.bin"
        source.write_bytes(b"clean original")
        job = self.app.store.create("https://example.com/file", self.folder, source.name)
        self.app.store.update(job["id"], state="complete", output=str(source))
        with patch("hngoos_dm.safety_ui.scan_files", return_value=("clean", "", [])):
            self.app.check_selected_safety(job["id"])
            self.app.background_threads[-1].join(5)
        source.unlink()
        self.app.events.get(timeout=5)()
        current = self.app.store.get(job["id"])
        self.assertEqual(current["safety_check"]["status"], "error")
        self.assertEqual(current["state"], "complete")

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.app = App.__new__(App)
        self.app.store = Store(self.folder / "journal.sqlite3")
        self.app.events = queue.Queue()
        self.app.background_threads = []
        self.app.manager = SimpleNamespace(scheduler_stop=threading.Event())
        self.app.update_safety_buttons = lambda: None

    def test_deleted_journal_entry_does_not_break_queued_scan_callback(self):
        job = self.app.store.create("https://example.com/file", self.folder, "file")
        self.app.store.delete(job["id"])
        self.app.check_selected_safety(job["id"])
        self.assertEqual(self.app.background_threads, [])

    def test_locked_threat_does_not_skip_later_quarantine_or_erase_threat_result(self):
        outputs = [self.folder / name for name in ("locked.bin", "second.bin")]
        for path in outputs:
            path.write_bytes(b"harmless scanner fixture")
        job = self.app.store.create("https://example.com/file", self.folder, "file")
        self.app.store.update(job["id"], state="complete", output=str(outputs[0]),
                              outputs=list(map(str, outputs)))

        def quarantine(source, folder, name):
            if Path(source) == outputs[0]:
                raise PermissionError("fixture file locked")
            return deliver(source, folder, name)

        with patch("hngoos_dm.safety_ui.scan_files", return_value=(
                "threat", "Scanner identified two risks", list(map(str, outputs)))):
            self.app.check_selected_safety(job["id"])
            self.app.background_threads[-1].join(timeout=5)
        with patch("hngoos_dm.files.deliver", side_effect=quarantine):
            self.app.events.get(timeout=5)()
        current = self.app.store.get(job["id"])
        self.assertEqual(current["safety_check"]["status"], "threat")
        self.assertIn("locked.bin", current["safety_check"]["detail"])
        self.assertIn("fixture file locked", current["safety_check"]["detail"])
        self.assertIn("Scanner identified two risks", current["safety_check"]["detail"])
        self.assertTrue(outputs[0].is_file())
        self.assertFalse(outputs[1].exists())
        self.assertTrue(Path(str(outputs[1]) + ".chuakiemtra").is_file())
        self.assertEqual(current["state"], "quarantined")

