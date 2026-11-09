"""Keep upstream copyright/license metadata next to binary distributions."""

import importlib.metadata
import json
import re
import shutil
import subprocess
from pathlib import Path

folder = Path("dist/third-party-notices")
if folder.is_dir():
    shutil.rmtree(folder)
folder.mkdir(parents=True, exist_ok=True)
packages = ("yt-dlp", "openpyxl", "et-xmlfile", "imageio-ffmpeg", "pypdfium2", "pillow", "websockets",
            "pystray", "libtorrent", "cryptography", "cffi", "six")
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
quickjs_license = Path("src/hngoos_dm/assets/runtime/LICENSE.txt")
if quickjs_license.is_file():
    shutil.copy2(quickjs_license, folder/"QuickJS-NG-LICENSE.txt")
    versions["QuickJS-NG"] = "0.18.0"
(folder/"versions.json").write_text(json.dumps(versions, indent=2), encoding="utf-8")
shutil.copy2("THIRD_PARTY_NOTICES.txt", folder/"NOTICES.txt")
for notice in Path("browser-extension/licenses").glob("*.txt"):
    shutil.copy2(notice, folder/notice.name)
codec_sources = Path("tools/ffmpeg-build")
for name, source in (("FFmpeg-COPYING.GPLv2.txt", "ffmpeg-9.0.2/COPYING.GPLv2"),
                     ("x264-COPYING.txt", "x264-b35605ace3ddf7c1a5d67a2eb553f034aef41d55/COPYING"),
                     ("LAME-COPYING.txt", "lame-3.100/COPYING"),
                     ("dav1d-COPYING.txt", "dav1d-1.5.4/COPYING"),
                     ("zlib-LICENSE.txt", "zlib-1.4/LICENSE")):
    if (codec_sources/source).is_file():
        shutil.copy2(codec_sources/source, folder/name)
from hngoos_dm.media import find_ffmpeg

for option in ("-version", "-L", "-buildconf"):
    result = subprocess.run([find_ffmpeg(), option], check=False, capture_output=True,
                            creationflags=0x08000000 if __import__("os").name == "nt" else 0)
    (folder/("FFmpeg"+option+".txt")).write_bytes(result.stdout+result.stderr)
shutil.make_archive("dist/ThirdPartyNotices", "zip", folder)
print("Collected upstream notices for", len(versions), "packages")
