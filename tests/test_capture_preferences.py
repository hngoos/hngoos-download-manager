import tempfile
import unittest
from pathlib import Path

from hngoos_dm.bridge import handle_message
from hngoos_dm.browser_preferences import validate_preferences
from hngoos_dm.store import Store


class CapturePreferenceTests(unittest.TestCase):
    def test_extension_capture_permission_updates_app_policy_and_revision(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder)/"db")
            store.set_setting("browser_preferences", {"capture": False, "auto_start": False})
            response = handle_message({"action": "set-browser-capture", "enabled": True}, store)
            self.assertTrue(response["ok"])
            self.assertTrue(store.setting("browser_preferences")["capture"])
            self.assertFalse(store.setting("browser_preferences")["auto_start"])
            revision = store.setting("browser_preferences_revision")
            self.assertTrue(revision)
            handle_message({"action": "set-browser-capture", "enabled": False}, store)
            self.assertFalse(store.setting("browser_preferences")["capture"])
            self.assertNotEqual(store.setting("browser_preferences_revision"), revision)
            with self.assertRaises(TypeError):
                handle_message({"action": "set-browser-capture", "enabled": "yes"}, store)

    def test_filters_can_be_disabled_without_losing_their_saved_values(self):
        settings = validate_preferences({"skip_domains": ["Example.com"], "skip_domains_enabled": False,
            "skip_extensions": [".zip"], "skip_extensions_enabled": False,
            "only_extensions": ["pdf"], "only_extensions_enabled": True,
            "min_bytes": 1048576, "min_bytes_enabled": False,
            "resume_on_cancel": True, "bypass_insert": True})
        self.assertEqual(settings["skip_domains"], ["example.com"])
        self.assertEqual(settings["skip_extensions"], ["zip"])
        self.assertFalse(settings["min_bytes_enabled"])
        with self.assertRaises(TypeError):
            validate_preferences({"resume_on_cancel": "yes"})

    def test_browser_observes_durable_cancel_status_without_receiving_private_request_data(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder)/"db")
            store.enqueue("browser-123", {"kind": "file", "url": "https://example.com/private?token=secret"})
            result = handle_message({"action": "download-status", "id": "browser-123"}, store)
            self.assertEqual(result, {"ok": True, "state": "pending"})
            store.acknowledge("browser-123", "cancelled")
            self.assertEqual(handle_message({"action": "download-status", "id": "browser-123"}, store),
                             {"ok": True, "state": "cancelled"})
            self.assertEqual(handle_message({"action": "download-status", "id": "unknown"}, store),
                             {"ok": True, "state": "unknown"})
