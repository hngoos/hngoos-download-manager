"""Windows power actions are armed by the user; importing never changes system state."""

import ctypes
import os
import subprocess


def prevent_sleep(active):
    if os.name == "nt":
        flags = 0x80000001 if active else 0x80000000  # ES_CONTINUOUS, ES_SYSTEM_REQUIRED.
        return bool(ctypes.windll.kernel32.SetThreadExecutionState(flags))
    return False


def shutdown_in(seconds=60):
    if os.name != "nt":
        raise ValueError("Tắt máy tự động hiện hỗ trợ Windows.")
    subprocess.run(["shutdown.exe", "/s", "/t", str(max(30, min(3600, int(seconds)))), "/c",
                    "HDM đã tải xong. Bạn có thể hủy tắt máy từ HDM hoặc chạy shutdown /a."],
                   check=True, capture_output=True, creationflags=0x08000000)


def cancel_shutdown():
    if os.name == "nt":
        subprocess.run(["shutdown.exe", "/a"], check=False, capture_output=True, creationflags=0x08000000)
