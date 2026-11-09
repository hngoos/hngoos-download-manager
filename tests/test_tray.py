"""Windows tray popups stay beside their icon in physical screen coordinates."""

import sys
import unittest


@unittest.skipUnless(sys.platform == "win32", "Windows notification area")
class TrayPositionTests(unittest.TestCase):
    def test_popup_anchors_to_icon_instead_of_stale_cursor_position(self):
        import ctypes
        from ctypes import wintypes
        from unittest.mock import patch

        from PIL import Image
        from pystray import Menu, MenuItem

        from hngoos_dm.windows_tray import WindowsIcon, shell, win32

        icon = WindowsIcon("test", Image.new("RGBA", (16, 16)), menu=Menu(MenuItem("Open", lambda *_: None)))
        icon._hwnd = 1
        icon._menu_hwnd = 2
        icon._menu_handle = (3, [])
        for bounds in ((440, 306, 464, 330), (2500, 900, 2536, 936), (-1800, -500, -1764, -464)):
            def rectangle(_identifier, rect, bounds=bounds):
                rect = ctypes.cast(rect, ctypes.POINTER(wintypes.RECT)).contents
                rect.left, rect.top, rect.right, rect.bottom = bounds
                return 0
            with patch.object(shell, "Shell_NotifyIconGetRect", side_effect=rectangle), \
                    patch.object(win32, "SetForegroundWindow"), patch.object(win32, "PostMessage"), \
                    patch.object(win32, "TrackPopupMenuEx", return_value=0) as popup:
                icon._on_notify(0, win32.WM_RBUTTONUP)
            self.assertEqual(popup.call_args.args[2:4], (bounds[0], bounds[3]))

    def test_tray_thread_uses_per_monitor_coordinates_and_restores_context(self):
        import ctypes
        from ctypes import wintypes
        from unittest.mock import patch

        from PIL import Image
        from pystray._win32 import Icon

        from hngoos_dm.windows_tray import WindowsIcon, user

        user.GetThreadDpiAwarenessContext.argtypes = []
        user.GetThreadDpiAwarenessContext.restype = ctypes.c_void_p
        user.AreDpiAwarenessContextsEqual.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        user.AreDpiAwarenessContextsEqual.restype = wintypes.BOOL
        previous = user.GetThreadDpiAwarenessContext()
        observed = []
        icon = WindowsIcon("test", Image.new("RGBA", (16, 16)))
        with patch.object(Icon, "_run", side_effect=lambda: observed.append(user.GetThreadDpiAwarenessContext())):
            icon._run()
        self.assertTrue(user.AreDpiAwarenessContextsEqual(observed[0], -4))
        self.assertTrue(user.AreDpiAwarenessContextsEqual(user.GetThreadDpiAwarenessContext(), previous))
