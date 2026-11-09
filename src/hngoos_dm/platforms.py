"""Small desktop integration helpers with no shell interpolation."""

import os
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path


def platform_label():
    return {"win32": "Windows", "darwin": "macOS"}.get(sys.platform, "Linux")


def open_path(path):
    target = str(Path(path).resolve())
    if os.name == "nt":
        os.startfile(target)
    else:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", target],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def installer_environment():
    """An installer and the app it starts must outlive the current onefile runtime."""
    environment = {key: value for key, value in os.environ.items()
                   if not key.startswith("_PYI_") and key != "_MEIPASS2"}
    environment["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    return environment


@contextmanager
def system_dll_search():
    """Do not give an external installer PyInstaller's private DLL search path."""
    if os.name != "nt" or not getattr(sys, "frozen", False):
        yield
        return
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetDllDirectoryW.argtypes = (wintypes.DWORD, wintypes.LPWSTR)
    kernel.GetDllDirectoryW.restype = wintypes.DWORD
    kernel.SetDllDirectoryW.argtypes = (wintypes.LPCWSTR,)
    kernel.SetDllDirectoryW.restype = wintypes.BOOL
    length = kernel.GetDllDirectoryW(0, None)
    buffer = ctypes.create_unicode_buffer(length+1)
    kernel.GetDllDirectoryW(len(buffer), buffer)
    original = buffer.value or None
    if not kernel.SetDllDirectoryW(None):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        yield
    finally:
        if not kernel.SetDllDirectoryW(original):
            raise ctypes.WinError(ctypes.get_last_error())


def launch_installer(path, arguments=()):
    """Launch a verified Windows installer with an independent runtime environment."""
    target = str(Path(path).resolve())
    with system_dll_search():
        return subprocess.Popen([target, *map(str, arguments)], env=installer_environment(),
                                close_fds=True, creationflags=0x08000000 if os.name == "nt" else 0)
