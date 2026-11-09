"""Fetch exact codec sources for the compact Windows FFmpeg build."""

import hashlib
import http.client
import io
import tarfile
import time
import urllib.request
from pathlib import Path

SOURCES = {
    "ffmpeg-9.0.2": ("https://ffmpeg.org/releases/ffmpeg-9.0.2.tar.xz",
                     "8c3850283eb25fa026482078a04051e0be17347b09ef81a0849bec15a96e002e"),
    "x264-b35605ace3ddf7c1a5d67a2eb553f034aef41d55": (
        "https://code.videolan.org/videolan/x264/-/archive/b35605ace3ddf7c1a5d67a2eb553f034aef41d55/x264-b35605ace3ddf7c1a5d67a2eb553f034aef41d55.tar.gz",
        "cd71a7515b0e9a012e1ac9b1f8415bebcaf6fc97d4db32286642ac4c0fbe24f9"),
    "lame-3.100": ("https://downloads.sourceforge.net/project/lame/lame/3.100/lame-3.100.tar.gz",
                   "ddfe36cab873794038ae2c1210557ad34857a4b6bdc515785d1da9e175b1da1e"),
    "dav1d-1.5.4": ("https://code.videolan.org/videolan/dav1d/-/archive/1.5.4/dav1d-1.5.4.tar.gz",
                    "a1d5b63d2d38ec9bd03acf643caa51fa22edd1e89c5a109c4807717216bbec07"),
    "zlib-1.4": ("https://zlib.net/zlib-1.4.tar.gz",
                 "02dd159783677a749c04adbdd02b55b8a2bcc7e054f51b76b549199a916ad584"),
}


def fetch_verified(url, digest, target):
    urls = [url]
    if url.startswith("https://ffmpeg.org/"):
        urls.append(url.replace("https://ffmpeg.org/", "https://www.ffmpeg.org/", 1))
    for attempt in range(3):
        for source in urls:
            print("Fetching codec source:", source, flush=True)
            try:
                request = urllib.request.Request(source, headers={"User-Agent": "HDM-Build"})
                with urllib.request.urlopen(request, timeout=60) as response:
                    data = response.read(32*1024*1024+1)
            except (OSError, http.client.IncompleteRead):
                if attempt == 2 and source == urls[-1]:
                    raise
                continue
            if len(data) > 32*1024*1024 or hashlib.sha256(data).hexdigest() != digest:
                raise ValueError("Codec source checksum mismatch: "+target.name)
            target.write_bytes(data)
            return
        time.sleep(2**attempt)


def fetch_preserved_source(target, digest):
    # Releases preserve the original, unmodified upstream source archives. This
    # fallback is trusted by each archive's pinned hash, not by the release tag.
    url = ("https://github.com/hngoos/hngoos-download-manager/releases/download/v0.1.0/"
           "HDM-FFmpeg-9.0.2-Sources.tar.gz")
    request = urllib.request.Request(url, headers={"User-Agent": "HDM-Build"})
    with urllib.request.urlopen(request, timeout=90) as response:
        bundle = response.read(96*1024*1024+1)
    if len(bundle) > 96*1024*1024:
        raise ValueError("Codec source bundle is too large")
    with tarfile.open(fileobj=io.BytesIO(bundle), mode="r:gz") as archive:
        member = archive.getmember(target.name)
        if not member.isfile() or member.size > 32*1024*1024:
            raise ValueError("Invalid preserved codec source")
        with archive.extractfile(member) as source:
            data = source.read(32*1024*1024+1)
    if hashlib.sha256(data).hexdigest() != digest:
        raise ValueError("Codec source checksum mismatch: "+target.name)
    target.write_bytes(data)


def main():
    root = Path(__file__).resolve().parents[1]
    folder = root/"tools/ffmpeg-build"
    folder.mkdir(parents=True, exist_ok=True)
    archives = []
    for name, (url, digest) in SOURCES.items():
        archive = folder/url.rsplit("/", 1)[-1]
        if not archive.is_file() or hashlib.sha256(archive.read_bytes()).hexdigest() != digest:
            try:
                fetch_verified(url, digest, archive)
            except (OSError, http.client.IncompleteRead, ValueError):
                print("Upstream unavailable or unverified; checking preserved codec source:", name, flush=True)
                fetch_preserved_source(archive, digest)
        if not (folder/name).is_dir():
            with tarfile.open(archive) as source:
                source.extractall(folder, filter="data")
        archives.append(archive)
    # Redistribute corresponding source beside the binary release, including
    # the exact recipe. Keep it separate from the user's installed application.
    (root/"dist").mkdir(exist_ok=True)
    with tarfile.open(root/"dist/HDM-FFmpeg-9.0.2-Sources.tar.gz", "w:gz") as output:
        for archive in archives:
            output.add(archive, arcname=archive.name)
        for name in ("prepare-ffmpeg.py", "build-ffmpeg.sh"):
            output.add(root/"scripts"/name, arcname="scripts/"+name)
    print("Verified compact FFmpeg sources and corresponding-source archive")


if __name__ == "__main__":
    main()
