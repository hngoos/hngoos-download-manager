"""Place Windows tray menus next to the actual icon across mixed-DPI screens."""

import ctypes
from ctypes import wintypes

from pystray._util import win32
from pystray._win32 import Icon

user = ctypes.WinDLL("user32", use_last_error=True)
shell = ctypes.WinDLL("shell32", use_last_error=True)
user.SetThreadDpiAwarenessContext.argtypes = [ctypes.c_void_p]
user.SetThreadDpiAwarenessContext.restype = ctypes.c_void_p


class IconIdentifier(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("hWnd", wintypes.HWND),
                ("uID", wintypes.UINT), ("guidItem", win32.NOTIFYICONDATAW.GUID)]


shell.Shell_NotifyIconGetRect.argtypes = [ctypes.POINTER(IconIdentifier), ctypes.POINTER(wintypes.RECT)]
shell.Shell_NotifyIconGetRect.restype = ctypes.c_long


class WindowsIcon(Icon):
    def _run(self):
        # Set this before pystray creates either menu owner window. Tk keeps its
        # existing DPI context; only this native notification thread changes.
        previous = user.SetThreadDpiAwarenessContext(-4)  # PER_MONITOR_AWARE_V2
        try:
            super()._run()
        finally:
            if previous:
                user.SetThreadDpiAwarenessContext(previous)

    def _on_notify(self, wparam, lparam):
        if lparam != win32.WM_RBUTTONUP or not self._menu_handle:
            return super()._on_notify(wparam, lparam)
        # pystray registers uID=0; hWnd uniquely identifies this notification.
        identifier = IconIdentifier(cbSize=ctypes.sizeof(IconIdentifier), hWnd=self._hwnd, uID=0)
        rectangle = wintypes.RECT()
        if shell.Shell_NotifyIconGetRect(ctypes.byref(identifier), ctypes.byref(rectangle)) != 0:
            return super()._on_notify(wparam, lparam)
        win32.SetForegroundWindow(self._hwnd)
        menu, callbacks = self._menu_handle
        selected = win32.TrackPopupMenuEx(menu, win32.TPM_RETURNCMD,
                                          rectangle.left, rectangle.bottom, self._menu_hwnd, None)
        win32.PostMessage(self._hwnd, 0, 0, 0)  # Let a subsequent outside click dismiss the menu.
        if selected > 0:
            callbacks[selected-1](self)
