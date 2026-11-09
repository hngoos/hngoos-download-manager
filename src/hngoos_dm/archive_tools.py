"""Bounded 7-Zip/RAR inspection without extracting attacker-controlled paths."""

import io
import os
import shutil
import subprocess
import sys
import threading
import time
import zipfile
from pathlib import Path


def executable():
    candidates = [Path(sys.executable).parent/"archive-tools/7z.exe",
                  Path(__file__).resolve().parents[2]/"dist/archive-tools/7z.exe"]
    for path in candidates:
        if path.is_file():
            return str(path)
    command = shutil.which("7z") or shutil.which("7zz")
    if command:
        return command
    raise ValueError("Thiếu công cụ 7-Zip để kiểm RAR/7z; chưa kiểm tra được nội dung.")


def command(arguments, password=None, maximum=2*1024*1024, timeout=15):
    # The Windows CLI requires -pVALUE; never persist this command, log it, or echo a password.
    process = subprocess.Popen([executable(), "-sccUTF-8", "-spd", "-p"+(password or ""), *arguments],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        creationflags=0x08000000 if os.name == "nt" else 0)
    watchdog = threading.Timer(timeout, process.kill)
    watchdog.start()
    data = bytearray()
    truncated = False
    try:
        process.stdin.close()
        while block := process.stdout.read(min(65536, maximum+1-len(data))):
            data.extend(block)
            if len(data) > maximum:
                truncated = True
                process.kill()
                break
        status = process.wait(timeout=5)
        if status and not truncated:
            raise ValueError("Không đọc được tệp nén; mật khẩu sai, dữ liệu hỏng hoặc vượt thời gian kiểm tra.")
        return bytes(data[:maximum]), truncated
    finally:
        watchdog.cancel()
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        process.stdout.close()


def members(path, password=None):
    data, truncated = command(["l", "-slt", "-ba", "--", str(Path(path).resolve())], password)
    if truncated:
        raise ValueError("Danh sách tệp nén vượt giới hạn kiểm tra.")
    entries = []
    for paragraph in data.decode("utf-8", errors="strict").replace("\r\n", "\n").split("\n\n"):
        entry = {}
        for line in paragraph.strip().splitlines():
            if " = " not in line:
                raise ValueError("Tên hoặc siêu dữ liệu tệp nén mơ hồ; cần quét riêng.")
            key, value = line.split(" = ", 1)
            if key in entry:
                raise ValueError("Siêu dữ liệu tệp nén trùng lặp; cần quét riêng.")
            entry[key] = value
        if "Path" in entry:
            entries.append(entry)
    if len(entries) > 5000:
        raise ValueError("Tệp nén vượt giới hạn 5.000 thành phần.")
    return entries


def inspect_archive(path, password=None):
    from .safety import RISKY, archive_name_is_unsafe, inspect_zip
    reasons = []
    try:
        entries = members(path, password)
        deadline, budget = time.monotonic()+15, 64*1024*1024
        for entry in entries:
            name = entry["Path"].replace("\\", "/")
            if archive_name_is_unsafe(name) or any(key in entry for key in ("Symbolic Link", "Hard Link", "Reparse")):
                reasons.append("Tệp nén chứa đường dẫn hoặc liên kết không an toàn: "+name[:160])
                continue
            if entry.get("Folder") == "+" or entry.get("Attributes", "").startswith("D"):
                continue
            if Path(name).suffix.lower() in RISKY or name.lower().endswith("vbaproject.bin"):
                reasons.append("Tệp nén chứa mã/lối tắt rủi ro: "+name[:160])
            size = int(entry.get("Size", "0"))
            packed = int(entry.get("Packed Size") or 0)
            if size > 512*1024*1024 and size > max(1, packed)*200:
                reasons.append("Thành phần có tỷ lệ giải nén bất thường: "+name[:160])
                continue
            if entry.get("Encrypted") == "+" and not password:
                reasons.append("Tệp nén có mật khẩu, chưa kiểm tra được nội dung")
                continue
            if budget <= 0 or time.monotonic() > deadline:
                reasons.append("Đã hết ngân sách kiểm tra tệp nén; cần quét riêng")
                break
            maximum = min(budget, 16*1024*1024) if Path(name).suffix.lower() == ".zip" else min(budget, 64)
            data, truncated = command(["e", "-so", "--", str(Path(path).resolve()), entry["Path"]],
                                      password, maximum=maximum, timeout=max(1, deadline-time.monotonic()))
            budget -= len(data)
            if data.startswith(b"MZ"):
                reasons.append("Tệp nén chứa chương trình Windows: "+name[:160])
            if data.startswith((b"7z\xbc\xaf\x27\x1c", b"Rar!\x1a\x07")):
                reasons.append("RAR/7z lồng nhau cần giải nén riêng để kiểm tiếp: "+name[:160])
            if data.startswith(b"PK\x03\x04"):
                if truncated:
                    reasons.append("ZIP lồng nhau vượt giới hạn kiểm tra")
                else:
                    with zipfile.ZipFile(io.BytesIO(data)) as nested:
                        reasons.extend(inspect_zip(nested, password=password))
            if len(reasons) >= 30:
                break
    except (ValueError, OSError, UnicodeError, subprocess.TimeoutExpired, zipfile.BadZipFile) as exc:
        reasons.append(str(exc))
    return list(dict.fromkeys(reasons))
