"""User-level native host registration; importing this module never changes the registry."""

import json
import os
import re
import shlex
import sys
from pathlib import Path


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
                        "CocCoc\\Browser", "Opera Software"):
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
        browsers = ("Google/Chrome", "Microsoft Edge", "BraveSoftware/Brave-Browser", "Chromium")
    else:
        parent = Path(os.environ.get("XDG_CONFIG_HOME", "")).expanduser()
        if not parent.is_absolute():
            parent = Path.home()/".config"
        browsers = ("google-chrome", "microsoft-edge", "BraveSoftware/Brave-Browser", "chromium")
    return [parent/browser/"NativeMessagingHosts" for browser in browsers]
