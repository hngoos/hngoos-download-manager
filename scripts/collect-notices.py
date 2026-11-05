"""Keep upstream copyright/license metadata next to binary distributions."""

import importlib.metadata
import json
import re
import shutil
import subprocess
from pathlib import Path

folder = Path("dist/third-party-notices")
folder.mkdir(parents=True, exist_ok=True)
packages = ("yt-dlp", "openpyxl", "et-xmlfile", "imageio-ffmpeg", "pypdfium2", "pillow", "playwright",
            "pystray", "libtorrent", "cryptography", "cffi", "greenlet", "pyee", "six")
versions = {}
for name in packages:
    try:
        distribution = importlib.metadata.distribution(name)
    except importlib.metadata.PackageNotFoundError:
        continue
    target = folder/re.sub(r"[^a-z0-9_-]", "_", name.lower())
    target.mkdir(exist_ok=True)
    versions[name] = distribution.version
    for item in distribution.files or []:
        normalized = str(item).replace("\\", "/")
        if ".dist-info/" not in normalized:
            continue
        if not any(word in normalized.lower() for word in ("license", "copyright", "notice", "metadata")):
            continue
        relative = normalized.split(".dist-info/", 1)[1]
        destination = (target/relative).resolve()
        if target.resolve() not in destination.parents:
            continue
        source = distribution.locate_file(item)
        if source.is_file():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
(folder/"versions.json").write_text(json.dumps(versions, indent=2), encoding="utf-8")
shutil.copy2("THIRD_PARTY_NOTICES.md", folder/"README.md")
for notice in Path("browser-extension/licenses").glob("*.txt"):
    shutil.copy2(notice, folder/notice.name)
from hngoos_dm.media import find_ffmpeg

for option in ("-version", "-L", "-buildconf"):
    result = subprocess.run([find_ffmpeg(), option], check=False, capture_output=True,
                            creationflags=0x08000000 if __import__("os").name == "nt" else 0)
    (folder/("FFmpeg"+option+".txt")).write_bytes(result.stdout+result.stderr)
shutil.make_archive("dist/ThirdPartyNotices", "zip", folder)
print("Collected upstream notices for", len(versions), "packages")
