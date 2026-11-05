"""User-level native host registration; importing this module never changes the registry."""

import json
import os
import re
from pathlib import Path


def register(extension_id, bridge_exe, data_dir):
    if os.name != "nt":
        raise ValueError("Đăng ký trình duyệt hiện hỗ trợ Windows.")
    if not re.fullmatch("[a-p]{32}", extension_id):
        raise ValueError("Extension ID Chromium cần đúng 32 ký tự a–p.")
    executable = Path(bridge_exe).resolve()
    if not executable.is_file() or executable.suffix.lower() != ".exe":
        raise ValueError("Chọn HDMBridge.exe đã build hoặc đã cài cùng ứng dụng.")
    folder = Path(data_dir) / "native-messaging"
    folder.mkdir(parents=True, exist_ok=True)
    manifest = folder / "com.hngoos.download_manager.json"
    manifest.write_text(json.dumps({
        "name": "com.hngoos.download_manager", "description": "hngoos-download-manager browser bridge",
        "path": str(executable), "type": "stdio", "allowed_origins": [f"chrome-extension://{extension_id}/"],
    }), encoding="utf-8")
    import winreg
    for browser in ("Google\\Chrome", "Microsoft\\Edge", "BraveSoftware\\Brave-Browser", "Chromium",
                    "CocCoc\\Browser", "Opera Software"):
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                              f"Software\\{browser}\\NativeMessagingHosts\\com.hngoos.download_manager") as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, str(manifest))
    return manifest
