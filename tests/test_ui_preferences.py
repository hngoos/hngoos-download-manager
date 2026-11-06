"""UI behavior checks; headless runners exercise these in the packaged smoke test."""

import tempfile
import time
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch

from hngoos_dm.app import App


class PresentationTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f"A desktop display is required: {error}")
        self.folder = tempfile.TemporaryDirectory()
        self.app = App(self.root, Path(self.folder.name))
        self.errors = []
        self.root.report_callback_exception = lambda *args: self.errors.append(args)
        self.root.update()

    def tearDown(self):
        self.app.close()
        self.folder.cleanup()

    def pump(self, seconds=0.2):
        end = time.monotonic()+seconds
        while time.monotonic() < end:
            self.root.update()
            time.sleep(0.01)
        self.assertEqual(self.errors, [])

    def test_switches_preserve_task_inputs_and_persist_settings(self):
        self.app.url.set("https://example.com/download?token=keep-me")
        self.app.filename.set("Tài liệu của tôi.pdf")
        inputs = (self.app.url.get(), self.app.filename.get(), self.app.connections.get())
        self.app.theme_switch.toggle(False)
        self.app.language_switch.toggle(True)
        self.pump()
        self.assertEqual(self.app.store.setting("theme"), "light")
        self.assertEqual(self.app.store.setting("language"), "en")
        self.assertEqual(self.app.tabs.tab(0, "text"), "Downloads")
        self.assertEqual(self.app.table.heading("name", "text"), "FILENAME")
        self.assertEqual(inputs, (self.app.url.get(), self.app.filename.get(), self.app.connections.get()))
        self.app.bandwidth_selector.current(1)
        self.app.bandwidth_selector.event_generate("<<ComboboxSelected>>")
        self.pump()
        self.assertEqual(self.app.store.setting("bandwidth_mode"), "medium")
        self.assertEqual(self.app.bandwidth_mode.get(), "Vừa (4 MB/s)")
        self.app.language_switch.toggle(False)
        self.pump()
        self.assertEqual(self.app.tabs.tab(0, "text"), "Tải xuống")
        self.assertEqual(self.app.bandwidth_display.get(), "Vừa (4 MB/s)")

    @patch("hngoos_dm.update_ui.check_update", return_value=None)
    def test_update_check_uses_single_dialog_and_stays_inside_app(self, check):
        with patch("hngoos_dm.app.webbrowser.open") as browser:
            self.app.check_update()
            dialog = self.app.update_dialog
            self.app.check_update()
            self.assertIs(self.app.update_dialog, dialog)
            self.pump()
            self.assertEqual(dialog.status.get(), "Bạn đang dùng phiên bản mới nhất.")
            self.assertFalse(dialog.busy)
            check.assert_called_once()
            browser.assert_not_called()
            dialog.close()

    def test_install_rejects_tampered_bytes_without_launching(self):
        import hashlib

        with patch("hngoos_dm.update_ui.check_update", return_value=None):
            self.app.check_update()
            self.pump()
        dialog = self.app.update_dialog
        dialog.path = Path(self.folder.name)/"HDM.exe"
        content = b"trusted fixture"
        dialog.asset = {"name": "HDM.exe", "size": len(content), "sha256": hashlib.sha256(content).hexdigest()}
        dialog.path.write_bytes(b"X"*len(content))
        with patch("hngoos_dm.update_ui.open_path") as launch:
            dialog.install()
            self.pump()
            self.assertIn("signed release", dialog.status.get())
            launch.assert_not_called()
        dialog.close()
