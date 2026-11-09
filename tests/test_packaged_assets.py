import shutil
import tempfile
import unittest
from importlib.resources import files
from pathlib import Path
from unittest.mock import patch

from hngoos_dm.diagnostics import check_assets


class PackagedAssetsTests(unittest.TestCase):
    def test_branding_images_are_readable_without_starting_ui(self):
        check_assets(None)

    def test_missing_header_is_detected_before_ui_startup(self):
        with tempfile.TemporaryDirectory() as temporary:
            package = Path(temporary)
            shutil.copytree(files("hngoos_dm") / "assets" / "branding", package / "assets" / "branding")
            (package / "assets" / "branding" / "header-dark.png").unlink()
            with patch("importlib.resources.files", return_value=package), self.assertRaises(FileNotFoundError):
                check_assets(None)
