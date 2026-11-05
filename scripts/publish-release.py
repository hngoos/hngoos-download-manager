"""Publish signed platform installers and the extension to the HDM GitHub repository.

Run locally after building and signing dist/release-notes.md. Authentication
uses Git Credential Manager; only the verified release assets are uploaded here.
"""

import argparse
import hashlib
import http.client
import json
import os
import subprocess
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

from hngoos_dm import __version__
from hngoos_dm.updater import MANIFEST_END, MANIFEST_START, verify_manifest

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--directory", type=Path, default=Path("dist"))
parser.add_argument("--publish", action="store_true", help="Publish the verified draft immediately")
parser.add_argument("--replace", action="store_true", help="Back up and replace the same version after staging and verification")
args = parser.parse_args()
folder = args.directory.resolve()
notes = (folder/"release-notes.md").read_text(encoding="utf-8")
assert notes.count(MANIFEST_START) == notes.count(MANIFEST_END) == 1
payload = verify_manifest(json.loads(notes.split(MANIFEST_START, 1)[1].split(MANIFEST_END, 1)[0]))
assert payload["version"] == __version__
required = {f"HDM-Setup-{__version__}.exe", "HDM-Browser-Extension.zip"}
allowed = required | {f"HDM-{__version__}-macOS-{arch}.dmg" for arch in ("arm64", "x64")} | {
    f"HDM-{__version__}-Linux-x64.deb", f"HDM-{__version__}-Linux-x64.AppImage"}
names = {item["name"] for item in payload["assets"]}
assert required <= names <= allowed
assert len(names) == len(payload["assets"])
for item in payload["assets"]:
    path = folder/item["name"]
    assert path.stat().st_size == item["size"]
    with path.open("rb") as stream:
        assert hashlib.file_digest(stream, "sha256").hexdigest() == item["sha256"]

result = subprocess.run(["git", "credential", "fill"], input="protocol=https\nhost=github.com\n\n",
                        text=True, capture_output=True, check=True,
                        env={**os.environ, "GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "Never"})
credential = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
headers = {"Authorization": "Bearer "+credential["password"], "Accept": "application/vnd.github+json",
           "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "HDM-Release"}
base = "https://api.github.com/repos/hngoos/hngoos-download-manager"


def api(path, method="GET", data=None):
    request = urllib.request.Request(base+path, headers=headers, method=method,
                                    data=json.dumps(data).encode() if data is not None else None)
    with urllib.request.urlopen(request, timeout=60) as response:
        body = response.read()
    return json.loads(body) if body else None


# Check repository identity and keep local/private material out of public Git.
repo = api("")
assert not repo["private"]
assert repo["full_name"] == "hngoos/hngoos-download-manager"
tree = api("/git/trees/"+repo["default_branch"]+"?recursive=1")
assert not tree["truncated"]
public_paths = {entry["path"] for entry in tree["tree"] if entry["type"] == "blob"}
assert {"README.md", "LICENSE", "src/hngoos_dm/__init__.py", "browser-extension/manifest.json"} <= public_paths
for name in public_paths:
    path = Path(name)
    assert not any(part.lower() in {"tools", "dist", "build", "node_modules", "__pycache__", ".venv", ".venv-build"}
                   for part in path.parts)
    assert path.suffix.lower() not in {".key", ".pem", ".pfx", ".p12", ".dpapi", ".sqlite3", ".exe", ".bundle"}
    assert not path.name.lower().startswith((".env", "cookies"))
releases = api("/releases")
tag = "v"+__version__
previous = next((release for release in releases if release["tag_name"] == tag), None)
assert not previous or args.replace, "Release exists; use --replace only after verifying the new build"
assert not args.replace or args.publish, "Replacement must promote the verified draft in the same operation"
staging_tag = "hdm-staging-"+uuid.uuid4().hex if previous else tag
release = api("/releases", "POST", {"tag_name": staging_tag, "target_commitish": repo["default_branch"],
                                   "name": "HDM v"+__version__, "body": notes, "draft": True})
release_id = release["id"]


def upload_asset(release, item, path):
    upload = urllib.parse.urlsplit(release["upload_url"].split("{", 1)[0])
    assert upload.scheme == "https" and upload.hostname == "uploads.github.com"
    connection = http.client.HTTPSConnection(upload.hostname, timeout=300)
    asset_headers = {**headers, "Content-Type": "application/octet-stream", "Content-Length": str(item["size"])}
    try:
        with path.open("rb") as stream:
            connection.request("POST", upload.path+"?name="+urllib.parse.quote(item["name"]),
                               body=stream, headers=asset_headers)
            response = connection.getresponse()
            data = json.loads(response.read())
        assert response.status == 201, f"Asset upload failed: HTTP {response.status}"
        assert data["size"] == item["size"] and data["digest"] == "sha256:"+item["sha256"]
    finally:
        connection.close()
    print("Uploaded and verified", item["name"], flush=True)


for item in payload["assets"]:
    upload_asset(release, item, folder/item["name"])
release = api("/releases/"+str(release_id))
assert {item["name"] for item in release["assets"]} == names
if args.publish:
    backup = None
    old_ref = None
    if previous:
        # Keep the old release usable until both replacement files are uploaded and verified.
        backup = Path("tools/release-backup")/str(previous["id"])
        backup.mkdir(parents=True, exist_ok=True)
        (backup/"release.json").write_text(json.dumps(previous, indent=2), encoding="utf-8")
        for item in previous["assets"]:
            path = backup/Path(item["name"]).name
            expected = (item.get("digest") or "").removeprefix("sha256:")
            if not path.is_file() or path.stat().st_size != item["size"]:
                # Public URL: never forward API authentication onto asset redirects.
                with urllib.request.urlopen(item["browser_download_url"], timeout=120) as response, path.open("wb") as output:
                    while block := response.read(1024*1024):
                        output.write(block)
            assert path.stat().st_size == item["size"]
            with path.open("rb") as stream:
                actual = hashlib.file_digest(stream, "sha256").hexdigest()
            assert not expected or actual == expected
            item["sha256"] = actual
        old_ref = api("/git/ref/tags/"+tag)
        api("/releases/"+str(previous["id"]), "DELETE")
    try:
        # Keep the documentation archived at the version tag consistent with the packages.
        if previous:
            commit = api("/commits/"+repo["default_branch"])["sha"]
            api("/git/refs/tags/"+tag, "PATCH", {"sha": commit, "force": True})
        release = api("/releases/"+str(release_id), "PATCH",
                      {"tag_name": tag, "draft": False, "make_latest": "true"})
    except Exception:
        if previous:
            api("/git/refs/tags/"+tag, "PATCH", {"sha": old_ref["object"]["sha"], "force": True})
            restored = api("/releases", "POST", {"tag_name": tag, "name": previous["name"],
                "body": previous["body"], "draft": True, "prerelease": previous["prerelease"]})
            for item in previous["assets"]:
                upload_asset(restored, item, backup/Path(item["name"]).name)
            api("/releases/"+str(restored["id"]), "PATCH", {"draft": False, "make_latest": "true"})
        raise
    print("Published", release["html_url"])
else:
    print("Verified draft", release_id)
