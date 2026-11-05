import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from hngoos_dm.browser import host_directories, register
from hngoos_dm.paths import data_directory
from hngoos_dm.safety import inspect_file


class PlatformTests(unittest.TestCase):
    def test_standard_locations_preserve_legacy_databases(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {}, clear=True), \
                patch('pathlib.Path.home', return_value=Path(folder)):
            home = Path(folder)
            with patch.object(sys, 'platform', 'darwin'):
                self.assertEqual(data_directory(), home/'Library/Application Support/HDM')
                self.assertEqual(host_directories()[0], home/'Library/Application Support/Google/Chrome/NativeMessagingHosts')
            with patch.object(sys, 'platform', 'linux'):
                self.assertEqual(data_directory(), home/'.local/share/hdm')
                with patch.dict(os.environ, {'XDG_DATA_HOME': str(home/'custom')}):
                    self.assertEqual(data_directory(), home/'custom/hdm')
            (home/'HDM').mkdir()
            (home/'HDM/downloads.sqlite3').touch()
            self.assertEqual(data_directory(), home/'HDM')

    @unittest.skipIf(os.name == 'nt', 'POSIX executable permissions and native host locations')
    def test_native_host_registration_and_invalid_input(self):
        import json
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {}, clear=True), \
                patch('pathlib.Path.home', return_value=Path(folder)), patch.object(sys, 'platform', 'linux'):
            root = Path(folder)
            bridge = root/'bridge with spaces'
            bridge.write_text('#!/bin/sh\nexit 0\n')
            bridge.chmod(0o755)
            manifest = register('a'*32, bridge, root/'data')
            self.assertEqual(json.loads(manifest.read_text())['path'], str(bridge.resolve()))
            for directory in host_directories():
                self.assertEqual((directory/manifest.name).read_bytes(), manifest.read_bytes())
            with self.assertRaises(ValueError):
                register('../invalid', bridge, root/'data')
            bridge.chmod(0o644)
            with self.assertRaises(ValueError):
                register('a'*32, bridge, root/'data')

    def test_disguised_posix_programs_and_scripts_are_flagged(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'photo.jpg'
            for content in (b'\x7fELFprogram', b'\xcf\xfa\xed\xfeprogram', b'#!/bin/sh\necho test'):
                with self.subTest(content=content):
                    path.write_bytes(content)
                    self.assertTrue(inspect_file(path, path.name))
