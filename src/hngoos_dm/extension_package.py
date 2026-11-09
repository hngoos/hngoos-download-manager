"""Fetch the Chromium package using the same publisher verification as app updates."""

import json
import os
import tempfile
import zipfile
from pathlib import Path

from .updater import (
    MANIFEST_END,
    MANIFEST_START,
    RELEASES,
    download_installer,
    fetch_json,
    verify_manifest,
    version_tuple,
)

RUNTIME_FILES = ("manifest.json", "background.js", "retired-features.js", "options.html", "options.js",
                 "popup.html", "popup.js", "connection.js", "ui-text.js", "style.css", "video.js", "takeover.js", "capture-settings.js", "capture-insert.js",
                 "icons.js", "licenses/morphicons.txt", "licenses/lucide.txt",
                 "media-capture.js", "assets/icons/hdm-16.png", "assets/icons/hdm-32.png",
                 "assets/icons/hdm-48.png", "assets/icons/hdm-128.png")


def bundled_extension_path():
    """Locate the ready-to-load extension shipped with HDM."""
    import sys
    if not getattr(sys, "frozen", False):
        return Path(__file__).resolve().parents[2]/"browser-extension"
    folder = Path(sys.executable).resolve().parent
    if sys.platform == "darwin":
        folder = folder.parent/"Resources"
    return folder/"extension"


def build_development_extension(destination, source):
    """Package the current checkout so a live app never serves an older release ZIP."""
    destination, source = Path(destination), Path(source)
    with tempfile.TemporaryDirectory(dir=destination.parent) as folder:
        staged = Path(folder)/"extension.zip"
        with zipfile.ZipFile(staged, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name in RUNTIME_FILES:
                archive.write(source/name, name)
        os.replace(staged, destination)
    return destination


def prepare_extension(destination):
    import sys
    source = Path(__file__).resolve().parents[2]/"browser-extension"
    if not getattr(sys, "frozen", False) and (source/"manifest.json").is_file():
        return build_development_extension(destination, source)
    return download_extension(destination)


def prepare_extension_folder(destination):
    """Validate the entire archive before replacing the ready-to-load extension folder."""
    destination = Path(destination).absolute()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_symlink() or (hasattr(destination, "is_junction") and destination.is_junction()):
        raise ValueError("Thư mục tiện ích không được là liên kết.")
    with tempfile.TemporaryDirectory(prefix=".hdm-extension-", dir=destination.parent) as folder:
        temporary = Path(folder)
        archive_path = temporary/"extension.zip"
        prepare_extension(archive_path)
        staged = temporary/"unpacked"
        staged.mkdir()
        with zipfile.ZipFile(archive_path) as archive:
            entries = archive.infolist()
            names = [entry.filename for entry in entries]
            if (len(names) != len(set(names)) or set(names)-set(RUNTIME_FILES)
                    or not {"manifest.json", "background.js"}.issubset(names)
                    or sum(entry.file_size for entry in entries) > 64*1024*1024):
                raise ValueError("Gói tiện ích không hợp lệ.")
            for entry in entries:
                target = staged/entry.filename  # All names have passed the explicit runtime allowlist.
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(entry))
        manifest = json.loads((staged/"manifest.json").read_text(encoding="utf-8"))
        if manifest.get("manifest_version") != 3:
            raise ValueError("Gói tiện ích không hợp lệ.")
        previous = temporary/"previous"
        if destination.exists():
            os.replace(destination, previous)
        try:
            os.replace(staged, destination)
        except OSError:
            if previous.exists():
                os.replace(previous, destination)
            raise
    return destination


def download_extension(destination):
    release = fetch_json(RELEASES)
    body = release.get("body") or ""
    if body.count(MANIFEST_START) != 1 or body.count(MANIFEST_END) != 1:
        raise ValueError("Missing signed extension manifest")
    payload = verify_manifest(json.loads(body.split(MANIFEST_START)[1].split(MANIFEST_END)[0]))
    if version_tuple(payload["version"]) != version_tuple(release["tag_name"]):
        raise ValueError("Release version mismatch")
    assets = [item for item in payload["assets"] if item["name"] == "HDM-Browser-Extension.zip"]
    if len(assets) != 1 or assets[0]["size"] > 32*1024*1024:
        raise ValueError("Invalid extension package")
    path = Path(destination)
    with tempfile.TemporaryDirectory(dir=path.parent) as staging:
        temporary = download_installer(payload, staging, asset=assets[0])
        with zipfile.ZipFile(temporary) as archive:
            if "manifest.json" not in archive.namelist():
                raise ValueError("Invalid extension package")
        os.replace(temporary, path)
    return path
