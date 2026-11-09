import hashlib
import queue
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from hngoos_dm.store import Store


class AutomaticUpdateTests(unittest.TestCase):
    def test_manual_update_rechecks_processing_before_verify_and_before_launch(self):
        import threading
        from unittest.mock import Mock

        from hngoos_dm.update_ui import UpdateDialog
        self.app.locale = SimpleNamespace(language="en")
        dialog = UpdateDialog.__new__(UpdateDialog)
        dialog.app = self.app
        dialog.path, dialog.asset = self.directory/"installer.exe", {}
        dialog.status, dialog.primary, dialog.run = Mock(), Mock(), Mock()
        with patch("hngoos_dm.update_ui.platform.system", return_value="Windows"), \
                patch("hngoos_dm.update_ui.launch_installer") as launch:
            self.app.processing_stops = [threading.Event()]
            dialog.install()
            dialog.run.assert_not_called()
            self.app.processing_stops[0].set()
            dialog.install()
            dialog.run.assert_called_once()
            # Work can start while package verification is running in the background.
            self.app.manager.active["new-download"] = True
            dialog.launch(dialog.path)
            launch.assert_not_called()
            self.assertFalse(self.app.closed)
            self.app.manager.active.clear()
            dialog.launch(dialog.path)
            launch.assert_called_once()
            self.assertTrue(self.app.closed)

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.directory = Path(self.folder.name)
        self.app = SimpleNamespace(store=Store(self.directory/"db"), data_dir=self.directory,
                                   events=queue.Queue(), background_threads=[], manager=SimpleNamespace(active={}))
        self.app.closed = False
        self.app.close = lambda: setattr(self.app, "closed", True)

    def drain(self, updates):
        if updates.worker:
            updates.worker.join(3)
        while not self.app.events.empty():
            self.app.events.get_nowait()()

    def test_video_updates_wait_for_media_and_retry_without_interrupting_the_user(self):
        from unittest.mock import Mock

        from hngoos_dm.automatic_updates import AutomaticVideoUpdates
        self.app.update_ytdlp = Mock()
        updates = AutomaticVideoUpdates(self.app)
        now = time.time()+60
        with patch("hngoos_dm.automatic_updates.platform.system", return_value="Windows"):
            for flag in ("media_busy", "source_busy", "media_tool_busy"):
                setattr(self.app, flag, True)
                updates.tick(now)
                self.app.update_ytdlp.assert_not_called()
                setattr(self.app, flag, False)
            updates.tick(now)
            self.app.update_ytdlp.assert_called_once_with()
            updates.tick(now+60)
            self.assertEqual(self.app.update_ytdlp.call_count, 1)
            updates.tick(now+3601)
            self.assertEqual(self.app.update_ytdlp.call_count, 2)

    def test_successful_video_check_is_persisted_across_sessions(self):
        from unittest.mock import Mock

        from hngoos_dm.automatic_updates import AutomaticVideoUpdates
        now = time.time()
        self.app.store.set_setting("last_video_tool_check", now)
        self.app.update_ytdlp = Mock()
        updates = AutomaticVideoUpdates(self.app)
        with patch("hngoos_dm.automatic_updates.platform.system", return_value="Windows"):
            updates.tick(now+3600)
            self.app.update_ytdlp.assert_not_called()
            updates.tick(now+24*3600+1)
            self.app.update_ytdlp.assert_called_once_with()

    def test_checks_are_periodic_disabled_means_no_network_and_new_release_is_not_installed_by_default(self):
        from hngoos_dm.automatic_updates import AutomaticUpdates
        updates = AutomaticUpdates(self.app)
        now = time.time()+60
        self.app.store.set_setting("auto_check_updates", False)
        with patch("hngoos_dm.automatic_updates.check_update", side_effect=AssertionError("must not contact network")):
            updates.tick(now)
            self.assertIsNone(updates.worker)
        self.app.store.set_setting("auto_check_updates", True)
        with patch("hngoos_dm.automatic_updates.check_update", return_value={"version": "9.9.9", "assets": []}):
            updates.tick(now)
            self.drain(updates)
        self.assertIn("9.9.9", self.app.store.setting("automatic_update_status"))
        self.assertFalse(self.app.closed)
        self.assertFalse((self.directory/"updates").exists())
        with patch("hngoos_dm.automatic_updates.check_update", side_effect=AssertionError("checked too soon")):
            updates.tick(now+60)
            self.assertFalse(updates.busy)

    def test_verified_update_waits_until_idle_and_rechecks_bytes_before_install(self):
        from hngoos_dm.automatic_updates import AutomaticUpdates
        updates = AutomaticUpdates(self.app)
        self.app.store.set_setting("auto_install_updates", True)
        content = b"verified installer fixture"
        path = self.directory/"HDM-Setup-9.9.9.exe"
        asset = {"name": path.name, "size": len(content), "sha256": hashlib.sha256(content).hexdigest()}
        path.write_bytes(content)
        updates.ready = ({"version": "9.9.9", "assets": [asset]}, asset, path)
        self.app.manager.active["busy"] = True
        with patch("hngoos_dm.automatic_updates.is_packaged", return_value=True), \
                patch("hngoos_dm.automatic_updates.launch_installer") as launch:
            updates.tick()
            self.assertFalse(self.app.closed)
            launch.assert_not_called()
            self.app.manager.active.clear()
            path.write_bytes(b"X"*len(content))
            updates.tick()
            self.drain(updates)
            launch.assert_not_called()
            self.assertFalse(self.app.closed)
            self.assertIsNone(updates.ready)
            self.assertIn("signed release", self.app.store.setting("automatic_update_status"))

    def test_install_opt_out_after_staging_prevents_launch(self):
        from hngoos_dm.automatic_updates import AutomaticUpdates
        updates = AutomaticUpdates(self.app)
        updates.ready = ({"version": "9.9.9"}, {}, self.directory/"installer.exe")
        self.app.store.set_setting("auto_check_updates", False)
        self.app.store.set_setting("auto_install_updates", False)
        with patch("hngoos_dm.automatic_updates.launch_installer", side_effect=AssertionError("opted out")):
            updates.tick(time.time()+60)
        self.assertFalse(self.app.closed)

    def test_manual_scan_prevents_automatic_install_until_its_result_is_published(self):
        from hngoos_dm.automatic_updates import AutomaticUpdates
        updates = AutomaticUpdates(self.app)
        self.app.store.set_setting("auto_install_updates", True)
        updates.ready = ({"version": "9.9.9"}, {}, self.directory/"installer.exe")
        self.app.safety_scanning = {"finished-download"}
        with patch("hngoos_dm.automatic_updates.is_packaged", return_value=True), \
                patch("hngoos_dm.automatic_updates.verify_package") as verify, \
                patch("hngoos_dm.automatic_updates.launch_installer") as launch:
            updates.tick()
            launch.assert_not_called()
            verify.assert_not_called()
            self.assertFalse(self.app.closed)
            self.assertIsNotNone(updates.ready)
            self.app.safety_scanning.clear()
            updates.tick()
            launch.assert_called_once()
            self.assertTrue(self.app.closed)

    def test_idle_packaged_app_hands_verified_update_to_installer(self):
        from hngoos_dm.automatic_updates import AutomaticUpdates
        updates = AutomaticUpdates(self.app)
        self.app.store.set_setting("auto_install_updates", True)
        path = self.directory/"HDM-Setup-9.9.9.exe"
        content = b"verified package"
        path.write_bytes(content)
        asset = {"name": path.name, "size": len(content), "sha256": hashlib.sha256(content).hexdigest()}
        updates.ready = ({"version": "9.9.9"}, asset, path)
        with patch("hngoos_dm.automatic_updates.is_packaged", return_value=True), \
                patch("hngoos_dm.automatic_updates.launch_installer") as launch:
            updates.tick()
        self.assertTrue(self.app.closed)
        self.assertEqual(launch.call_args.args[0], path)
        self.assertIn("/NORESTART", launch.call_args.args[1])
