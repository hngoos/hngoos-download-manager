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
