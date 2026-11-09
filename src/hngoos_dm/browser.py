"""User-level native host registration; importing this module never changes the registry."""

import json
import os
import re
import shlex
import sys
from pathlib import Path

BROWSERS = {
    "chrome": ("Google Chrome", "chrome", "chrome.exe", "Google/Chrome/Application/chrome.exe"),
    "edge": ("Microsoft Edge", "edge", "msedge.exe", "Microsoft/Edge/Application/msedge.exe"),
    "brave": ("Brave", "brave", "brave.exe", "BraveSoftware/Brave-Browser/Application/brave.exe"),
    "coccoc": ("Cốc Cốc", "coccoc", "browser.exe", "CocCoc/Browser/Application/browser.exe"),
    "opera": ("Opera", "opera", "opera.exe", "Programs/Opera/launcher.exe"),
    "opera-gx": ("Opera GX", "opera", "opera.exe", "Programs/Opera GX/launcher.exe"),
    "vivaldi": ("Vivaldi", "vivaldi", "vivaldi.exe", "Vivaldi/Application/vivaldi.exe"),
}


def supported_browsers(platform=None):
    """Only Chromium extensions are shipped, on Windows and macOS."""
    return tuple(BROWSERS) if (platform or sys.platform) in {"win32", "darwin"} else ()


def find_browser(browser_id):
    if browser_id not in supported_browsers():
        return None
    name, _scheme, executable, relative = BROWSERS[browser_id]
    candidates = []
    if sys.platform == "win32":
        import winreg
        for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            if browser_id == "coccoc":
                break  # Other browsers also use browser.exe; use vendor-specific paths below.
            try:
                with winreg.OpenKey(hive, f"Software\\Microsoft\\Windows\\CurrentVersion\\App Paths\\{executable}") as key:
                    path = Path(winreg.QueryValueEx(key, "")[0].strip('"'))
                    gx = "operagx" in str(path).lower().replace(" ", "").replace("-", "")
                    if browser_id not in {"opera", "opera-gx"} or gx == (browser_id == "opera-gx"):
                        candidates.append(path)
            except OSError:
                pass
        for variable in ("LOCALAPPDATA", "PROGRAMFILES", "PROGRAMFILES(X86)"):
            if base := os.environ.get(variable):
                candidates.append(Path(base)/relative)
                if browser_id in {"opera", "opera-gx"}:
                    folder = "Opera GX" if browser_id == "opera-gx" else "Opera"
                    candidates.extend((Path(base)/folder/"launcher.exe", Path(base)/folder/"opera.exe"))
    elif sys.platform == "darwin":
        name = {"brave": "Brave Browser", "coccoc": "CocCoc"}.get(browser_id, name)
        for base in (Path("/Applications"), Path.home()/"Applications"):
            candidates.append(base/f"{name}.app/Contents/MacOS/{name}")
    return next((candidate for candidate in candidates if candidate.is_file()), None)


def open_extensions(browser_id):
    import subprocess
    if browser_id not in supported_browsers():
        raise ValueError("Trình duyệt không được hỗ trợ.")
    executable = find_browser(browser_id)
    if executable is None:
        raise FileNotFoundError("Chưa tìm thấy trình duyệt này trên máy. Hãy cài trình duyệt trước.")
    if sys.platform == "win32" and browser_id in {"opera", "opera-gx"}:
        return _open_opera_extensions(executable)
    subprocess.Popen([str(executable), "--new-tab", "--", BROWSERS[browser_id][1]+"://extensions/"],
                     creationflags=0x08000000 if os.name == "nt" else 0)


def _opera_window(executable):
    """Find an existing window belonging to this Opera installation, including versioned binaries."""
    import ctypes
    from ctypes import wintypes
    user, kernel = ctypes.windll.user32, ctypes.windll.kernel32
    user.IsWindowVisible.argtypes = [wintypes.HWND]
    user.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
    user.GetWindow.restype = wintypes.HWND
    user.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                                ctypes.POINTER(wintypes.DWORD)]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    found = []
    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def visit(hwnd, _data):
        if not user.IsWindowVisible(hwnd) or not user.GetWindowTextLengthW(hwnd) or user.GetWindow(hwnd, 4):
            return True
        window_class = ctypes.create_unicode_buffer(64)
        user.GetClassNameW(hwnd, window_class, 64)
        if window_class.value != "Chrome_WidgetWin_1":
            return True
        pid = wintypes.DWORD()
        user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        process = kernel.OpenProcess(0x1000, False, pid.value)
        if process:
            try:
                buffer, length = ctypes.create_unicode_buffer(32768), wintypes.DWORD(32768)
                if kernel.QueryFullProcessImageNameW(process, 0, buffer, ctypes.byref(length)):
                    image = Path(buffer.value)
                    if image.name.lower() == "opera.exe" and image.is_relative_to(executable.parent):
                        found.append(hwnd)
                        return False
            finally:
                kernel.CloseHandle(process)
        return True
    user.EnumWindows.argtypes = [type(visit), wintypes.LPARAM]
    user.EnumWindows(visit, 0)
    return found[0] if found else None


def _opera_extension_shortcut(hwnd):
    """Opera ignores internal URLs from its launcher. Use its documented shortcut only after focus is verified."""
    import ctypes
    from ctypes import wintypes
    user = ctypes.windll.user32
    user.GetForegroundWindow.restype = wintypes.HWND
    user.IsIconic.argtypes = [wintypes.HWND]
    user.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    user.SetForegroundWindow.argtypes = [wintypes.HWND]
    if user.IsIconic(hwnd):
        user.ShowWindow(hwnd, 9)
    user.SetForegroundWindow(hwnd)
    if user.GetForegroundWindow() != hwnd or any(user.GetAsyncKeyState(key) & 0x8000
                                                for key in (0x10, 0x11, 0x12, 0x5b, 0x5c)):
        raise OSError("Không thể mở trang tiện ích. Hãy nhập opera://extensions vào thanh địa chỉ trình duyệt.")
    class Keyboard(ctypes.Structure):
        _fields_ = [("key", wintypes.WORD), ("scan", wintypes.WORD), ("flags", wintypes.DWORD),
                    ("time", wintypes.DWORD), ("extra", ctypes.c_size_t)]
    class Mouse(ctypes.Structure):
        _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG), ("data", wintypes.DWORD),
                    ("flags", wintypes.DWORD), ("time", wintypes.DWORD), ("extra", ctypes.c_size_t)]
    class Payload(ctypes.Union):
        _fields_ = [("keyboard", Keyboard), ("mouse", Mouse)]
    class Input(ctypes.Structure):
        _fields_ = [("kind", wintypes.DWORD), ("payload", Payload)]
    # https://help.opera.com/en/latest/shortcuts/: Ctrl+Shift+E opens Extensions.
    keys = ((0x11, 0), (0x10, 0), (0x45, 0), (0x45, 2), (0x10, 2), (0x11, 2))
    events = (Input*len(keys))(*(Input(kind=1, payload=Payload(keyboard=Keyboard(key, 0, flags, 0, 0)))
                                for key, flags in keys))
    user.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(Input), ctypes.c_int]
    if user.SendInput(len(events), events, ctypes.sizeof(Input)) != len(events):
        for key in (0x45, 0x10, 0x11):
            user.keybd_event(key, 0, 2, 0)
        raise OSError("Không thể mở trang tiện ích. Hãy nhập opera://extensions vào thanh địa chỉ trình duyệt.")


def _open_opera_extensions(executable):
    import subprocess
    import time
    hwnd = _opera_window(executable)
    if hwnd is None:
        subprocess.Popen([str(executable)], creationflags=0x08000000)
        deadline = time.monotonic()+3
        while hwnd is None and time.monotonic() < deadline:
            time.sleep(.05)
            hwnd = _opera_window(executable)
    if hwnd is None:
        raise OSError("Chưa tìm thấy trình duyệt này trên máy. Hãy cài trình duyệt trước.")
    _opera_extension_shortcut(hwnd)


def unpacked_extension_id(folder):
    """Chromium crx_file::id_util::GenerateIdForPath; Windows hashes UTF-16 bytes."""
    import base64
    import hashlib
    # Chromium's Windows _wfullpath preserves 8.3 aliases; resolve() expands
    # them and would register a different native-messaging extension identity.
    folder = Path(os.path.abspath(folder)) if os.name == "nt" else Path(folder).resolve()
    manifest = json.loads((folder/"manifest.json").read_text(encoding="utf-8"))
    if manifest.get("key"):
        data = base64.b64decode(manifest["key"], validate=True)
    else:
        path = str(folder)
        if os.name == "nt" and len(path) >= 2 and path[1] == ":":
            path = path[0].upper()+path[1:]
        data = path.encode("utf-16-le" if os.name == "nt" else "utf-8")
    return "".join(chr(ord("a")+int(char, 16)) for char in hashlib.sha256(data).hexdigest()[:32])


def connect_bundled_extension(data_dir):
    """Prepare the installed folder before a browser loads it for the first time."""
    from .extension_package import bundled_extension_path
    return connect_extension(bundled_extension_path(), data_dir)


def connect_extension(folder, data_dir):
    """Register the exact unpacked extension automatically, without copying IDs."""
    data_dir = Path(data_dir).resolve()
    if getattr(sys, "frozen", False):
        bridge = Path(sys.executable).parent/("HDMBridge.exe" if os.name == "nt" else "HDMBridge")
        if sys.platform == "darwin":
            bridge = Path(sys.executable).parents[1]/"Helpers/HDMBridge"
    else:
        bridge = Path(__file__).resolve().parents[2]/"tools/native-bridge"/("HDMBridge.exe" if os.name == "nt" else "HDMBridge")
        if not bridge.is_file():
            raise FileNotFoundError("Bản thử nghiệm chưa có bộ kết nối trình duyệt.")
        (bridge.parent/"bridge-data.json").write_text(json.dumps({"directory": str(data_dir)}), encoding="utf-8")
    extension_id = unpacked_extension_id(folder)
    register(extension_id, bridge, data_dir)
    from .store import Store
    Store(data_dir/"downloads.sqlite3").set_setting("extension_id", extension_id)
    return extension_id


def register(extension_id, bridge_exe, data_dir):
    if not re.fullmatch("[a-p]{32}", extension_id):
        raise ValueError("Extension ID Chromium cần đúng 32 ký tự a–p.")
    executable = Path(bridge_exe).resolve()
    if not executable.is_file() or (os.name == "nt" and executable.suffix.lower() != ".exe"):
        raise ValueError("Chọn HDMBridge hoặc hdm-bridge đã cài cùng ứng dụng.")
    if os.name != "nt" and not os.access(executable, os.X_OK):
        raise ValueError("Native bridge cần có quyền thực thi.")
    folder = Path(data_dir) / "native-messaging"
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name != "nt" and os.environ.get("APPIMAGE"):
        image = Path(os.environ["APPIMAGE"]).resolve()
        if not image.is_file() or not os.access(image, os.X_OK):
            raise ValueError("Không tìm thấy tệp AppImage gốc. Hãy giữ tệp tại một vị trí cố định.")
        # AppImage mount points disappear when the process exits. Register a stable launcher.
        executable = folder/"HDMBridge"
        executable.write_text('#!/bin/sh\nexec env APPIMAGE_EXTRACT_AND_RUN=1 '
                              + shlex.quote(str(image))+' --native-messaging "$@"\n', encoding="utf-8")
        executable.chmod(0o700)
    manifest = folder / "com.hngoos.download_manager.json"
    manifest.write_text(json.dumps({
        "name": "com.hngoos.download_manager", "description": "hngoos-download-manager browser bridge",
        "path": str(executable), "type": "stdio", "allowed_origins": [f"chrome-extension://{extension_id}/"],
    }), encoding="utf-8")
    if os.name == "nt":
        import winreg
        for browser in ("Google\\Chrome", "Microsoft\\Edge", "BraveSoftware\\Brave-Browser", "Chromium",
                        "CocCoc\\Browser", "Opera Software", "Vivaldi"):
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                                  f"Software\\{browser}\\NativeMessagingHosts\\com.hngoos.download_manager") as key:
                winreg.SetValueEx(key, "", 0, winreg.REG_SZ, str(manifest))
    else:
        for directory in host_directories():
            directory.mkdir(parents=True, exist_ok=True)
            (directory/manifest.name).write_bytes(manifest.read_bytes())
    return manifest


def host_directories():
    """Native messaging manifests are per user, never system-wide."""
    if sys.platform == "darwin":
        parent = Path.home()/"Library/Application Support"
        browsers = ("Google/Chrome", "Microsoft Edge", "BraveSoftware/Brave-Browser", "Chromium",
                    "Vivaldi", "com.operasoftware.Opera", "com.operasoftware.OperaGX", "CocCoc")
    else:
        parent = Path(os.environ.get("XDG_CONFIG_HOME", "")).expanduser()
        if not parent.is_absolute():
            parent = Path.home()/".config"
        browsers = ("google-chrome", "microsoft-edge", "BraveSoftware/Brave-Browser", "chromium", "vivaldi", "opera")
    return [parent/browser/"NativeMessagingHosts" for browser in browsers]
