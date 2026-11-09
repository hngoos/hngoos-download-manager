"""Prepare a pinned, hash-verified QuickJS-NG runtime, including its MIT license."""

import hashlib
import platform
import urllib.request
from pathlib import Path

VERSION = "0.18.0"
ASSETS = {
    ("Windows", "AMD64"): ("qjs-windows-x86_64.exe", "ff03398d74ea6e6bd3a8e58058f7003225abcac229d7d57775b7aaae812a49c7"),
    ("Darwin", "arm64"): ("qjs-darwin-arm64", "91fe89916d3b0a6c01c4dc8382a99c3c1fd91ecfc214aa81ca051902bcce590d"),
    ("Darwin", "x86_64"): ("qjs-darwin-x86_64", "fa2c5dc78095daff566b32fab995ced12927875253b84216b91b834af2ef2b74"),
}
LICENSE_HASH = "96f73f9d2a16c21a36b418f06073be26e7d6d5e7c1bc99756b21a4f2c74ef171"


def fetch(url, destination, digest):
    if destination.is_file() and hashlib.sha256(destination.read_bytes()).hexdigest() == digest:
        return
    request = urllib.request.Request(url, headers={"User-Agent": "HDM-Build"})
    with urllib.request.urlopen(request, timeout=60) as response:
        data = response.read(8*1024*1024)
    if hashlib.sha256(data).hexdigest() != digest:
        raise ValueError("QuickJS-NG upstream checksum mismatch: "+destination.name)
    destination.write_bytes(data)


def main():
    name, digest = ASSETS[(platform.system(), platform.machine())]
    root = Path(__file__).resolve().parents[1]
    folder = root/"src/hngoos_dm/assets/runtime"
    folder.mkdir(parents=True, exist_ok=True)
    binary = folder/("qjs.exe" if platform.system() == "Windows" else "qjs")
    fetch(f"https://github.com/quickjs-ng/quickjs/releases/download/v{VERSION}/{name}", binary, digest)
    binary.chmod(0o755)
    fetch(f"https://raw.githubusercontent.com/quickjs-ng/quickjs/v{VERSION}/LICENSE", folder/"LICENSE.txt", LICENSE_HASH)
    print(f"Prepared QuickJS-NG {VERSION}: {binary.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
