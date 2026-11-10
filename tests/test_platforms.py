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
    def test_browser_request_wakes_running_instance_without_starting_another_app(self):
        import io
        from types import SimpleNamespace

        from hngoos_dm.bridge import main, read_message, write_message
        from hngoos_dm.instance import InstanceLock
        from hngoos_dm.store import Store

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            owner = InstanceLock(root/"instance.lock")
            try:
                incoming, outgoing = io.BytesIO(), io.BytesIO()
                write_message(incoming, {"action": "download", "kind": "video", "id": "wake-fixture",
                                         "url": "https://www.youtube.com/watch?v=fixture"})
                incoming.seek(0)
                stream = SimpleNamespace(buffer=incoming, fileno=lambda: 0)
                output = SimpleNamespace(buffer=outgoing, fileno=lambda: 1)
                with patch("hngoos_dm.bridge.data_directory", return_value=root), \
                        patch("hngoos_dm.bridge.sys.stdin", stream), patch("hngoos_dm.bridge.sys.stdout", output), \
                        patch("hngoos_dm.bridge.launch_app") as launch:
                    if os.name == "nt":
                        with patch("msvcrt.setmode"):
                            main()
                    else:
                        main()
                outgoing.seek(0)
                self.assertTrue(read_message(outgoing)["queued"])
                self.assertEqual(len(Store(root/"downloads.sqlite3").inbox()), 1)
                launch.assert_not_called()
                self.assertTrue(owner.consume_show_request(), "Browser requests must wake an existing hidden/busy app")
            finally:
                owner.close()

    def test_update_installer_does_not_inherit_onefile_runtime_state(self):
        from hngoos_dm.platforms import launch_installer
        inherited = {"_PYI_ARCHIVE_FILE": "old/HDM.exe", "_PYI_APPLICATION_HOME_DIR": "deleted/_MEI123",
                     "_PYI_PARENT_PROCESS_LEVEL": "1", "_MEIPASS2": "old/runtime", "HDM_KEEP": "unchanged"}
        with patch.dict(os.environ, inherited), patch("hngoos_dm.platforms.subprocess.Popen") as spawn:
            launch_installer("HDM-Setup.exe")
            environment = spawn.call_args.kwargs["env"]
            self.assertEqual(environment["PYINSTALLER_RESET_ENVIRONMENT"], "1")
            self.assertFalse(any(name.startswith("_PYI_") for name in environment))
            self.assertNotIn("_MEIPASS2", environment)
            self.assertEqual(environment["HDM_KEEP"], "unchanged")
            self.assertEqual(os.environ["_PYI_APPLICATION_HOME_DIR"], "deleted/_MEI123")

    @unittest.skipUnless(os.name == "nt", "Windows DLL search path")
    def test_external_launch_restores_private_dll_search_path_even_on_error(self):
        import ctypes

        from hngoos_dm.platforms import system_dll_search
        kernel = ctypes.windll.kernel32
        buffer = ctypes.create_unicode_buffer(32768)
        kernel.GetDllDirectoryW(len(buffer), buffer)
        original = buffer.value or None
        with tempfile.TemporaryDirectory() as directory:
            try:
                kernel.SetDllDirectoryW(directory)
                with patch.object(sys, "frozen", True, create=True), \
                        self.assertRaisesRegex(RuntimeError, "fixture"), system_dll_search():
                    kernel.GetDllDirectoryW(len(buffer), buffer)
                    self.assertEqual(buffer.value, "")
                    raise RuntimeError("fixture")
                kernel.GetDllDirectoryW(len(buffer), buffer)
                self.assertEqual(buffer.value, directory)
            finally:
                kernel.SetDllDirectoryW(original)

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

    @unittest.skipIf(os.name == 'nt', 'POSIX native messaging launcher')
    def test_appimage_registration_survives_mount_path_and_quotes(self):
        import json
        import subprocess
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            image = root/"HDM's app.AppImage"
            image.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n')
            image.chmod(0o755)
            bridge = root/'mounted/HDMBridge'
            bridge.parent.mkdir()
            bridge.write_text('#!/bin/sh\nexit 1\n')
            bridge.chmod(0o755)
            with patch.dict(os.environ, {'APPIMAGE': str(image)}), \
                    patch('hngoos_dm.browser.host_directories', return_value=[root/'hosts']):
                manifest = register('a'*32, bridge, root/'data')
            launcher = Path(json.loads(manifest.read_text())['path'])
            bridge.unlink()
            output = subprocess.check_output([str(launcher)], text=True)
            self.assertEqual(output.strip(), '--native-messaging')
            self.assertEqual(launcher.parent, root/'data/native-messaging')

    def test_macos_bridge_launches_the_gui_inside_its_own_bundle(self):
        from hngoos_dm.bridge import launch_app
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {}, clear=True):
            contents = Path(folder)/'HDM.app/Contents'
            executable = contents/'MacOS/HDM'
            executable.parent.mkdir(parents=True)
            executable.touch()
            with patch.object(sys, 'frozen', True, create=True), patch.object(sys, 'platform', 'darwin'), \
                    patch.object(sys, 'executable', str(contents/'Helpers/HDMBridge')), \
                    patch('hngoos_dm.bridge.subprocess.Popen') as spawn:
                launch_app()
            self.assertEqual(spawn.call_args.args[0], [str(executable)])

    def test_native_message_mode_does_not_create_a_gui(self):
        from hngoos_dm.app import main
        with patch.object(sys, 'argv', ['HDM', '--native-messaging']), \
                patch('hngoos_dm.bridge.main') as bridge, patch('tkinter.Tk') as root:
            main()
        bridge.assert_called_once_with()
        root.assert_not_called()
