"""Failures must not strand the hidden app or leave shutdown work unreachable."""

import queue
import tempfile
import threading
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import Mock, patch

from hngoos_dm.app import App
from hngoos_dm.engine import DownloadManager
from hngoos_dm.instance import InstanceLock
from hngoos_dm.store import Store


class InterruptedDownloadTests(unittest.TestCase):
    def test_shutdown_connection_failure_stays_paused_without_scheduling_a_retry(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            manager = DownloadManager(Store(folder/"journal.sqlite3"))
            try:
                job_id = manager.add("https://example.com/file", folder, "file.bin", start=False)
                stop = threading.Event()
                manager.active[job_id] = stop
                manager.close()
                with patch.object(manager, "_download", side_effect=urllib.error.URLError("socket closed on exit")):
                    manager._run(job_id, stop)
                row = manager.store.get(job_id)
                self.assertEqual(row["state"], "paused")
                self.assertFalse(row.get("retry_at"))
                self.assertNotIn(job_id, manager.active)
            finally:
                manager.close()


class RefreshRecoveryTests(unittest.TestCase):
    def app(self):
        app = App.__new__(App)
        app.events = queue.Queue()
        app.root = Mock()
        app._refresh_state = Mock()
        return app

    def test_callback_failure_does_not_block_later_tray_events_or_next_refresh(self):
        app = self.app()
        later = Mock()
        app.events.put(Mock(side_effect=ValueError("expired background result")))
        app.events.put(later)
        app.refresh()
        later.assert_called_once_with()
        app.root.report_callback_exception.assert_called_once()
        app._refresh_state.assert_called_once_with()
        app.root.after.assert_called_once_with(500, app.refresh)

    def test_refresh_failure_is_reported_and_the_next_tick_is_still_scheduled(self):
        app = self.app()
        app._refresh_state.side_effect = OSError("temporary metadata failure")
        app.refresh()
        app.root.report_callback_exception.assert_called_once()
        app.root.after.assert_called_once_with(500, app.refresh)

    def test_exit_callback_does_not_touch_destroyed_widgets_or_schedule_again(self):
        app = self.app()
        def exit_app():
            app._closing = True
        app.events.put(exit_app)
        app.refresh()
        app._refresh_state.assert_not_called()
        app.root.after.assert_not_called()

    def test_cleanup_failure_does_not_skip_manager_tray_or_window_shutdown(self):
        app = self.app()
        app.refresh_id = "refresh"
        app.media_stop = threading.Event()
        app.guard = Mock()
        app.guard.close.side_effect = RuntimeError("guard already stopped")
        app.tray = Mock()
        app.manager = Mock()
        app.close()
        app.close()
        self.assertTrue(app.media_stop.is_set())
        app.manager.close.assert_called_once_with()
        app.tray.close.assert_called_once_with()
        app.root.destroy.assert_called_once_with()
        app.root.report_callback_exception.assert_called_once()


class InstanceActivationTests(unittest.TestCase):
    def test_second_launch_requests_show_without_releasing_database_lock(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)/"instance.lock"
            first = InstanceLock(path)
            try:
                with self.assertRaises(RuntimeError):
                    InstanceLock(path)
                InstanceLock.request_show(path)
                self.assertTrue(first.consume_show_request())
                self.assertFalse(first.consume_show_request())
                with self.assertRaises(RuntimeError):
                    InstanceLock(path)
            finally:
                first.close()
            reopened = InstanceLock(path)
            reopened.close()

    def test_stale_activation_request_does_not_reappear_on_a_new_owner(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)/"instance.lock"
            first = InstanceLock(path)
            InstanceLock.request_show(path)
            first.close()
            reopened = InstanceLock(path)
            try:
                self.assertFalse(reopened.consume_show_request())
            finally:
                reopened.close()
