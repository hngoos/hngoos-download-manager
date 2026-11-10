"""Opening installation uses the selected browser, without a shell or store guess."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from hngoos_dm import browser


class BrowserInstallationTests(unittest.TestCase):
    def test_bundled_extension_registers_without_manual_identity_or_browser_launch(self):
        with patch("hngoos_dm.extension_package.bundled_extension_path", return_value=Path("bundle/extension")), \
                patch.object(browser, "connect_extension", return_value="a"*32) as connect, \
                patch("subprocess.Popen") as launch:
            self.assertEqual(browser.connect_bundled_extension(Path("data")), "a"*32)
        connect.assert_called_once_with(Path("bundle/extension"), Path("data"))
        launch.assert_not_called()
    @unittest.skipUnless(__import__("sys").platform == "win32", "Windows input API")
    def test_opera_shortcut_never_sends_input_to_another_foreground_window(self):
        user = MagicMock()
        user.GetForegroundWindow.return_value = 99
        with patch("ctypes.windll.user32", user), self.assertRaises(OSError):
            browser._opera_extension_shortcut(123)
        user.SendInput.assert_not_called()

    @unittest.skipUnless(__import__("sys").platform == "win32", "Windows input API")
    def test_opera_shortcut_sends_only_ctrl_shift_e_after_activating_selected_window(self):
        user = MagicMock()
        user.GetForegroundWindow.return_value = 123
        user.GetAsyncKeyState.return_value = 0
        user.IsIconic.return_value = False
        user.SendInput.return_value = 6
        with patch("ctypes.windll.user32", user):
            browser._opera_extension_shortcut(123)
        user.SetForegroundWindow.assert_called_once_with(123)
        count, events, size = user.SendInput.call_args.args
        self.assertEqual(count, 6)
        self.assertEqual(size, 40)
        self.assertEqual([(event.payload.keyboard.key, event.payload.keyboard.flags) for event in events],
                         [(17, 0), (16, 0), (69, 0), (69, 2), (16, 2), (17, 2)])

    def test_windows_opera_uses_its_extension_shortcut_instead_of_ignored_internal_url(self):
        with patch.object(browser.sys, "platform", "win32"), \
                patch.object(browser, "find_browser", return_value=Path("D:/OperaGX/opera.exe")), \
                patch.object(browser, "_open_opera_extensions", create=True) as open_page, \
                patch("subprocess.Popen") as launch:
            browser.open_extensions("opera-gx")
            open_page.assert_called_once_with(Path("D:/OperaGX/opera.exe"))
            launch.assert_not_called()

    def test_supported_browser_lists_target_only_windows_and_macos(self):
        for system in ("win32", "darwin"):
            self.assertIn("chrome", browser.supported_browsers(system))
            self.assertIn("opera-gx", browser.supported_browsers(system))
            self.assertNotIn("safari", browser.supported_browsers(system))
        self.assertEqual(browser.supported_browsers("linux"), ())

    def test_macos_detection_uses_native_application_bundles(self):
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder)
            executable = home/"Applications/Opera GX.app/Contents/MacOS/Opera GX"
            executable.parent.mkdir(parents=True)
            executable.touch()
            with patch.object(browser.sys, "platform", "darwin"), patch.object(browser.Path, "home", return_value=home):
                self.assertEqual(browser.find_browser("opera-gx"), executable)

    def test_unpacked_extension_id_is_stable_for_the_install_folder(self):
        import hashlib
        import os
        with tempfile.TemporaryDirectory() as folder:
            extension = Path(folder)/"extension"
            extension.mkdir()
            (extension/"manifest.json").write_text('{"manifest_version":3}')
            raw = os.path.abspath(extension) if os.name == "nt" else str(extension.resolve())
            if len(raw)>1 and raw[1]==":":
                raw=raw[0].upper()+raw[1:]
            data = raw.encode("utf-16-le" if os.name == "nt" else "utf-8")
            expected = "".join(chr(ord("a")+int(char,16)) for char in hashlib.sha256(data).hexdigest()[:32])
            self.assertEqual(browser.unpacked_extension_id(extension), expected)

    def test_selected_browser_opens_its_own_extension_page(self):
        with tempfile.TemporaryDirectory() as folder:
            executable = Path(folder)/"Microsoft Edge"/"msedge.exe"
            executable.parent.mkdir()
            executable.touch()
            with patch.object(browser.sys, "platform", "win32"), \
                    patch.object(browser, "find_browser", return_value=executable), \
                    patch.object(browser, "_opera_window", return_value=123), \
                    patch.object(browser, "_opera_extension_shortcut") as navigate, \
                    patch("subprocess.Popen") as launch:
                browser.open_extensions("edge")
            navigate.assert_called_once_with(123, "edge://extensions/")
            launch.assert_not_called()

    def test_missing_browser_is_reported_without_opening_a_different_browser(self):
        with patch.object(browser.sys, "platform", "win32"), \
                patch.object(browser, "find_browser", return_value=None), patch("subprocess.Popen") as launch:
            with self.assertRaises(FileNotFoundError):
                browser.open_extensions("chrome")
            launch.assert_not_called()

    def test_browser_selection_does_not_accept_arbitrary_command_or_url(self):
        with self.assertRaises(ValueError):
            browser.open_extensions("cmd.exe /c calc")
