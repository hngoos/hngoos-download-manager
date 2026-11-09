"""Factory defaults match the approved preferences and preserve saved choices."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from hngoos_dm import preferences
from hngoos_dm.store import Store


class DefaultPreferenceTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.store = Store(Path(self.folder.name)/"db")

    def assert_defaults(self):
        for key, expected in {
                "theme": "dark", "language": "en", "startup_enabled": True,
                "retry_failed": True, "auto_check_updates": True, "close_to_tray": True,
                "auto_install_updates": False, "auto_defender": False,
                "high_security": False, "auto_category": False, "auto_extract": False}.items():
            self.assertEqual(self.store.setting(key), expected, key)
        self.assertEqual(self.store.setting("proxy"), {"mode": "direct", "url": ""})
        self.assertTrue(self.store.setting("browser_preferences")["capture"])
        self.assertFalse(self.store.setting("browser_preferences")["auto_start"])

    def test_first_launch_registers_startup_and_saves_defaults_once(self):
        with patch("hngoos_dm.startup.set_enabled") as startup:
            preferences.initialize(self.store, register_startup=True)
            self.assert_defaults()
            preferences.initialize(self.store, register_startup=True)
            startup.assert_called_once_with(True)

    def test_development_and_tests_do_not_change_system_startup(self):
        with patch("hngoos_dm.startup.set_enabled") as startup:
            preferences.initialize(self.store)
            self.assert_defaults()
            preferences.reset(self.store, register_startup=False)
            startup.assert_not_called()

    def test_existing_choices_are_kept_and_reset_restores_approved_defaults(self):
        self.store.set_setting("language", "vi")
        self.store.set_setting("startup_enabled", False)
        self.store.set_setting("close_to_tray", False)
        self.store.set_setting("browser_preferences", {"capture": False, "auto_start": True})
        with patch("hngoos_dm.startup.set_enabled") as startup:
            preferences.initialize(self.store, register_startup=True)
            startup.assert_not_called()
            self.assertEqual(self.store.setting("language"), "vi")
            self.assertFalse(self.store.setting("browser_preferences")["capture"])
            preferences.reset(self.store)
            startup.assert_called_once_with(True)
            self.assert_defaults()

    def test_failed_startup_registration_does_not_claim_it_is_enabled(self):
        with patch("hngoos_dm.startup.set_enabled", side_effect=OSError("Access denied")):
            preferences.initialize(self.store, register_startup=True)
        self.assertFalse(self.store.setting("startup_enabled"))
