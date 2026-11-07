import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from hngoos_dm.paths import data_directory


class DataDirectoryTests(unittest.TestCase):
    def test_new_install_uses_hdm_and_existing_history_is_preserved(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {"LOCALAPPDATA": folder}, clear=True):
            root = Path(folder)
            self.assertEqual(data_directory(), root/"HDM")
            legacy = root/"HngoosDM"
            legacy.mkdir()
            (legacy/"downloads.sqlite3").touch()
            self.assertEqual(data_directory(), legacy)
            (root/"HDM").mkdir()
            self.assertEqual(data_directory(), root/"HDM")

    def test_explicit_hdm_override_takes_precedence(self):
        with patch.dict(os.environ, {"HDM_DATA_DIR": "custom-hdm", "HNGOOS_DATA_DIR": "legacy"}):
            self.assertEqual(data_directory(), Path("custom-hdm"))
