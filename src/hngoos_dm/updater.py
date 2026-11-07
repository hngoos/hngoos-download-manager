"""Verify publisher signatures before accepting a release manifest or installer."""

import base64
import hashlib
import json
import platform
import re
import shutil
import tempfile
import urllib.request
from pathlib import Path

from . import __version__
from .safety import validate_url

RELEASES = "https://api.github.com/repos/hngoos/hngoos-download-manager/releases/latest"
PUBLIC_KEY = "mEUSU1OA/4F8wDfLuLhpz8YGNBqHulyT6c/WdgZms/8="
MANIFEST_START = "<!-- HDM_UPDATE_MANIFEST\n"
MANIFEST_END = "\nHDM_UPDATE_MANIFEST -->"


def version_tuple(value):
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", value)
    if not match:
        raise ValueError("Phiên bản phải có dạng x.y.z.")
    return tuple(map(int, match.groups()))


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def verify_manifest(envelope, public_key=None):
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    key = public_key or PUBLIC_KEY
    if not key:
        raise ValueError("Chưa cấu hình khóa công khai nhà phát hành; không chấp nhận cập nhật tự động.")
    payload = envelope.get("payload")
    if not isinstance(payload, dict):
        raise TypeError("Manifest không hợp lệ.")
    try:
        Ed25519PublicKey.from_public_bytes(base64.b64decode(key, validate=True)).verify(
            base64.b64decode(envelope["signature"], validate=True), canonical(payload))
    except (InvalidSignature, KeyError, ValueError) as exc:
        raise ValueError("Chữ ký cập nhật không hợp lệ; bản cập nhật bị từ chối.") from exc
    version_tuple(payload.get("version", ""))
    if not payload.get("assets"):
        raise ValueError("Manifest chưa có tài sản phát hành.")
    for asset in payload["assets"]:
        if (not re.fullmatch(r"[a-f0-9]{64}", asset.get("sha256", ""))
                or not re.fullmatch(r"[A-Za-z0-9._-]+", asset.get("name", ""))
                or not isinstance(asset.get("size"), int) or not 0 < asset["size"] <= 1024*1024*1024):
            raise ValueError("Thông tin tệp cập nhật không hợp lệ.")
    return payload


def fetch_json(url):
    validate_url(url)
    if not url.startswith("https://"):
        raise ValueError("Cập nhật yêu cầu HTTPS.")
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "HDM-Update"}), timeout=30) as response:
        data = response.read(1024*1024+1)
        if len(data) > 1024*1024:
            raise ValueError("Manifest quá lớn.")
        return json.loads(data)


def check_update():
    release = fetch_json(RELEASES)
    if version_tuple(release["tag_name"]) <= version_tuple(__version__):
        return None
    manifest = next((asset for asset in release["assets"] if asset["name"] == "update-manifest.json"), None)
    if manifest:
        envelope = fetch_json(manifest["browser_download_url"])
    else:
        body = release.get("body") or ""
        if body.count(MANIFEST_START) != 1 or body.count(MANIFEST_END) != 1:
            raise ValueError("Bản mới chưa có manifest ký số; không được cài tự động.")
        encoded = body.split(MANIFEST_START, 1)[1].split(MANIFEST_END, 1)[0]
        envelope = json.loads(encoded)
    payload = verify_manifest(envelope)
    if version_tuple(payload["version"]) != version_tuple(release["tag_name"]):
        raise ValueError("Manifest và tag phát hành không khớp.")
    return payload


class DownloadCancelled(Exception):
    """The user cancelled an update download; no partial file is installed."""


def select_installer(payload, system=None, machine=None, debian=None):
    """Choose only the exact package name for this release and native platform."""
    version = payload["version"].lstrip("v")
    version_tuple(version)
    system = system or platform.system()
    machine = (machine or platform.machine()).lower()
    if system == "Windows" and machine in {"amd64", "x86_64"}:
        name = f"HDM-Setup-{version}.exe"
    elif system == "Darwin" and machine in {"arm64", "aarch64", "amd64", "x86_64"}:
        arch = "arm64" if machine in {"arm64", "aarch64"} else "x64"
        name = f"HDM-{version}-macOS-{arch}.dmg"
    elif system == "Linux" and machine in {"amd64", "x86_64"}:
        debian = shutil.which("dpkg") is not None if debian is None else debian
        name = f"HDM-{version}-Linux-x64.{'deb' if debian else 'AppImage'}"
    else:
        raise ValueError("No update package is available for this platform.")
    matches = [asset for asset in payload["assets"] if asset["name"] == name]
    if len(matches) != 1:
        raise ValueError("The signed release does not contain a unique package for this platform.")
    return matches[0]


def verify_package(path, asset):
    """Recheck downloaded bytes immediately before handing off to the OS."""
    path = Path(path)
    with path.open("rb") as stream:
        if (path.stat().st_size != asset["size"]
                or hashlib.file_digest(stream, "sha256").hexdigest() != asset["sha256"]):
            raise ValueError("The update package no longer matches the signed release.")
    return path


def download_installer(payload, directory, progress=None, cancel=None, *, asset=None):
    asset = asset or select_installer(payload)
    if asset not in payload["assets"]:
        raise ValueError("The package is not part of the signed release.")
    version = payload["version"].lstrip("v")
    version_tuple(version)
    if not re.fullmatch(r"[A-Za-z0-9._-]+", asset["name"]):
        raise ValueError("Invalid update filename.")
    url = f"https://github.com/hngoos/hngoos-download-manager/releases/download/v{version}/{asset['name']}"
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=directory, prefix="hdm-update-", suffix=".download", delete=False) as temp:
        staged = Path(temp.name)
    digest = hashlib.sha256()
    count = 0
    try:
        if cancel and cancel.is_set():
            raise DownloadCancelled()
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "HDM-Update"}), timeout=30) as response, staged.open("wb") as output:
            for block in iter(lambda: response.read(1024*1024), b""):
                if cancel and cancel.is_set():
                    raise DownloadCancelled()
                count += len(block)
                if count > asset["size"]:
                    raise ValueError("Bộ cài lớn hơn manifest đã ký.")
                digest.update(block)
                output.write(block)
                if progress:
                    progress(count, asset["size"])
        if count != asset["size"] or digest.hexdigest() != asset["sha256"]:
            raise ValueError("Mã băm/kích thước bộ cài không khớp manifest đã ký.")
        if cancel and cancel.is_set():
            raise DownloadCancelled()
        from .files import publish
        return publish(staged, directory, asset["name"])
    finally:
        staged.unlink(missing_ok=True)
