"""Opt-in updates of the official yt-dlp executable, verified against GitHub's asset digest."""

import hashlib
import json
import os
import urllib.request

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
    headers = {"User-Agent": "HDM-ToolUpdate", "Accept": "application/vnd.github+json"}
    with urllib.request.urlopen(urllib.request.Request("https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest", headers=headers), timeout=30) as response:
        release = json.load(response)
    asset = next((item for item in release["assets"] if item["name"] == "yt-dlp.exe"), None)
    if not asset or not str(asset.get("digest", "")).startswith("sha256:"):
        raise ValueError("Nguồn chính thức chưa có digest SHA-256 cho tài sản; không tự cập nhật.")
    wanted = asset["digest"].split(":", 1)[1]
    folder = root()
    folder.mkdir(parents=True, exist_ok=True)
    temporary = folder/"yt-dlp.exe.download"
    digest = hashlib.sha256()
    count = 0
    try:
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
    finally:
        temporary.unlink(missing_ok=True)
