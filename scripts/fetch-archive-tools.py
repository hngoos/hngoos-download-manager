"""Fetch pinned upstream 7-Zip binaries and preserve all bundled license notices."""

import hashlib
import shutil
import subprocess
import time
import urllib.request
from pathlib import Path

ASSETS = {
    "7zr.exe": "9bf582b894dfa665f852d7e9112b02290a1c303c2d95a21fcdc41ffcb03143b7",
    "7z2605-x64.exe": "fd99e86f57d8f429ef5ed045bf98315af962e2309b0f1ba87a147a44c71647d0",
}


def fetch_verified(target, digest):
    asset_id = {"7zr.exe": 662536918, "7z2605-x64.exe": 662536847}[target.name]
    urls = ("https://github.com/ip7z/7zip/releases/download/26.05/"+target.name,
            f"https://api.github.com/repos/ip7z/7zip/releases/assets/{asset_id}")
    for attempt in range(3):
        for index, url in enumerate(urls):
            try:
                request = urllib.request.Request(url, headers={"Accept": "application/octet-stream",
                                                               "User-Agent": "HDM-Build"})
                with urllib.request.urlopen(request, timeout=60) as response:
                    content = response.read(8*1024*1024)
            except OSError:
                if attempt == 2 and index == len(urls)-1:
                    raise
                continue
            if hashlib.sha256(content).hexdigest() != digest:
                raise ValueError("Upstream archive tool hash mismatch: "+target.name)
            target.write_bytes(content)
            return
        time.sleep(2**attempt)


def main():
    root = Path(__file__).resolve().parents[1]
    folder = root/"tools/archive-downloads"
    folder.mkdir(parents=True, exist_ok=True)
    for name, digest in ASSETS.items():
        target = folder/name
        if not target.exists() or hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            fetch_verified(target, digest)
    output = root/"tools/7zip"
    output.mkdir(parents=True, exist_ok=True)
    subprocess.run([str(folder/"7zr.exe"), "x", str(folder/"7z2605-x64.exe"), "-o"+str(output), "-y"],
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


if __name__ == "__main__":
    main()
