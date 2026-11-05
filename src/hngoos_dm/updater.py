"""Verify publisher signatures before accepting a release manifest or installer."""

import base64
import hashlib
import json
import re
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


def download_installer(payload, directory):
    asset = next((asset for asset in payload["assets"] if asset["name"].startswith("HDM-Setup-") and asset["name"].endswith(".exe")), None)
    if not asset:
        raise ValueError("Manifest chưa có bộ cài Windows.")
    version = payload["version"].lstrip("v")
    url = f"https://github.com/hngoos/hngoos-download-manager/releases/download/v{version}/{asset['name']}"
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    staged = directory / (asset["name"]+".download")
    digest = hashlib.sha256()
    count = 0
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "HDM-Update"}), timeout=30) as response, staged.open("wb") as output:
            for block in iter(lambda: response.read(1024*1024), b""):
                count += len(block)
                if count > asset["size"]:
                    raise ValueError("Bộ cài lớn hơn manifest đã ký.")
                digest.update(block)
                output.write(block)
        if count != asset["size"] or digest.hexdigest() != asset["sha256"]:
            raise ValueError("Mã băm/kích thước bộ cài không khớp manifest đã ký.")
        from .files import publish
        return publish(staged, directory, asset["name"])
    finally:
        staged.unlink(missing_ok=True)
