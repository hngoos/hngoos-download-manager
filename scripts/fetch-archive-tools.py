"""Fetch pinned upstream 7-Zip binaries and preserve all bundled license notices."""

import hashlib
import shutil
import subprocess
import urllib.request
from pathlib import Path

root = Path(__file__).resolve().parents[1]
folder = root/"tools/archive-downloads"
folder.mkdir(parents=True, exist_ok=True)
assets = {
    "7zr.exe": "9bf582b894dfa665f852d7e9112b02290a1c303c2d95a21fcdc41ffcb03143b7",
    "7z2605-x64.exe": "fd99e86f57d8f429ef5ed045bf98315af962e2309b0f1ba87a147a44c71647d0",
}
for name, digest in assets.items():
    target = folder/name
    if not target.exists() or hashlib.sha256(target.read_bytes()).hexdigest() != digest:
        with urllib.request.urlopen("https://github.com/ip7z/7zip/releases/download/26.05/"+name, timeout=60) as response:
            content = response.read(8*1024*1024)
        if hashlib.sha256(content).hexdigest() != digest:
            raise ValueError("Upstream archive tool hash mismatch: "+name)
        target.write_bytes(content)
output = root/"tools/7zip"
output.mkdir(parents=True, exist_ok=True)
result = subprocess.run([str(folder/"7zr.exe"), "x", str(folder/"7z2605-x64.exe"), "-o"+str(output), "-y"],
                        capture_output=True, timeout=60, check=True)
assert (output/"7z.exe").is_file() and (output/"7z.dll").is_file()
destination = root/"dist/archive-tools"
destination.mkdir(parents=True, exist_ok=True)
for name in ("7z.exe", "7z.dll", "License.txt", "readme.txt", "History.txt"):
    source = output/name
    if source.is_file():
        shutil.copy2(source, destination/name)
(destination/"SOURCE.txt").write_text(
    "7-Zip 26.05, Copyright Igor Pavlov. LGPL and unRAR restrictions: see License.txt.\n"
    "Corresponding upstream source: https://github.com/ip7z/7zip/releases/download/26.05/7z2605-src.7z\n"
    "Upstream: https://www.7-zip.org/\n", encoding="utf-8")
print("Verified and prepared upstream 7-Zip tools and license notices")
