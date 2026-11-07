"""Official yt-dlp executable updates, verified against GitHub's asset digest."""

import hashlib
import json
import os
import tempfile
import urllib.request

from .instance import InstanceLock
from .paths import data_directory


def root():
    return data_directory()/"tools"


def active_ytdlp():
    manifest = root()/"yt-dlp.json"
    try:
        metadata = json.loads(manifest.read_text(encoding="utf-8"))
        path = root()/"yt-dlp.exe"
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        return path if digest == metadata["sha256"] else None
    except (OSError, KeyError, ValueError):
        return None


def update_ytdlp():
    if os.name != "nt":
        raise ValueError("Bộ tải video cập nhật riêng hiện dành cho Windows.")
    folder = root()
    folder.mkdir(parents=True, exist_ok=True)
    try:
        lock = InstanceLock(folder/"yt-dlp-update.lock")
    except RuntimeError as error:
        raise ValueError("Bộ tải video đang được cập nhật. Hãy chờ hoàn tất.") from error
    try:
        return _update_ytdlp(folder)
    except PermissionError as error:
        raise ValueError("Tệp bộ tải video đang được sử dụng hoặc không có quyền ghi. Hãy chờ tác vụ kết thúc rồi thử lại.") from error
    finally:
        lock.close()


def _update_ytdlp(folder):
    headers = {"User-Agent": "HDM-ToolUpdate", "Accept": "application/vnd.github+json"}
    with urllib.request.urlopen(urllib.request.Request("https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest", headers=headers), timeout=30) as response:
        release = json.load(response)
    asset = next((item for item in release["assets"] if item["name"] == "yt-dlp.exe"), None)
    if not asset or not str(asset.get("digest", "")).startswith("sha256:"):
        raise ValueError("Nguồn chính thức chưa có digest SHA-256 cho tài sản; không tự cập nhật.")
    wanted = asset["digest"].split(":", 1)[1]
    existing = folder/"yt-dlp.exe"
    if (existing.is_file() and existing.stat().st_size == asset["size"]
            and hashlib.sha256(existing.read_bytes()).hexdigest() == wanted):
        (folder/"yt-dlp.json").write_text(json.dumps({"version": release["tag_name"], "sha256": wanted}), encoding="utf-8")
        return release["tag_name"]
    digest = hashlib.sha256()
    count = 0
    with tempfile.TemporaryDirectory(prefix=".yt-dlp-update-", dir=folder) as staging:
        from pathlib import Path
        temporary = Path(staging)/"yt-dlp.exe"
        with urllib.request.urlopen(urllib.request.Request(asset["browser_download_url"], headers={"User-Agent": "HDM-ToolUpdate"}), timeout=30) as incoming, temporary.open("wb") as outgoing:
            for block in iter(lambda: incoming.read(1024*1024), b""):
                count += len(block)
                if count > min(asset["size"], 100*1024*1024):
                    raise ValueError("Tệp yt-dlp vượt kích thước được công bố.")
                digest.update(block)
                outgoing.write(block)
        if count != asset["size"] or digest.hexdigest() != wanted:
            raise ValueError("yt-dlp không khớp mã SHA-256 được GitHub công bố.")
        temporary.replace(folder/"yt-dlp.exe")
        (folder/"yt-dlp.json").write_text(json.dumps({"version": release["tag_name"], "sha256": wanted}), encoding="utf-8")
        return release["tag_name"]
