"""Collision-safe publishing, checksums and staged destination transfers."""

import errno
import hashlib
import os
import uuid
from pathlib import Path


def checksums(path, algorithms=("md5", "sha1", "sha256", "sha512")):
    values = {name: hashlib.new(name, usedforsecurity=False) for name in algorithms}
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            for digest in values.values():
                digest.update(block)
    return {name: digest.hexdigest() for name, digest in values.items()}


def assemble_parts(parts, destination, stop):
    """Merge durable ranges and calculate all integrity hashes in the same read pass."""
    values = {name: hashlib.new(name, usedforsecurity=False) for name in ("md5", "sha1", "sha256", "sha512")}
    with Path(destination).open("wb") as output:
        for part in parts:
            if stop.is_set():
                from .policy import TransferCancelled
                raise TransferCancelled()
            with Path(part).open("rb") as source:
                while block := source.read(1024*1024):
                    if stop.is_set():
                        from .policy import TransferCancelled
                        raise TransferCancelled()
                    output.write(block)
                    for digest in values.values():
                        digest.update(block)
        output.flush()
        os.fsync(output.fileno())
    return {name: digest.hexdigest() for name, digest in values.items()}


def mark_internet(path):
    if os.name == "nt":
        try:
            Path(str(path) + ":Zone.Identifier").write_text("[ZoneTransfer]\nZoneId=3\n")
        except OSError:
            return False
    return True


def publish(source, folder, filename):
    source, folder = Path(source), Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    for number in range(10000):
        name = filename if not number else f"{Path(filename).stem} ({number}){Path(filename).suffix}"
        candidate = folder / name
        try:
            if os.name == "nt":
                source.rename(candidate)
            else:
                os.link(source, candidate)
                source.unlink()
            mark_internet(candidate)
            return candidate
        except FileExistsError:
            continue
    raise OSError("Không tìm được tên tệp còn trống.")


def deliver(source, folder, filename, stop=None):
    """Publish locally completed data; cross-device copies use an unfinalized temporary name."""
    source, folder = Path(source), Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    try:
        return publish(source, folder, filename)
    except OSError as exc:
        if exc.errno != errno.EXDEV and getattr(exc, "winerror", None) != 17:
            raise
    temp = folder / f".hngoos-{uuid.uuid4().hex}.tmp"
    try:
        with source.open("rb") as incoming, temp.open("xb") as outgoing:
            while block := incoming.read(1024 * 1024):
                if stop and stop.is_set():
                    from .policy import TransferCancelled
                    raise TransferCancelled()
                outgoing.write(block)
            outgoing.flush()
            os.fsync(outgoing.fileno())
        if checksums(temp, ("sha256",)) != checksums(source, ("sha256",)):
            raise OSError("Bản sao tới nơi lưu không khớp SHA-256; giữ dữ liệu gốc để thử lại.")
        output = publish(temp, folder, filename)
        source.unlink()
        return output
    finally:
        temp.unlink(missing_ok=True)


def category(filename):
    suffix = Path(filename).suffix.lower()
    groups = {
        "Video": {".mp4", ".mkv", ".webm", ".avi", ".mov"},
        "Music": {".mp3", ".m4a", ".wav", ".flac", ".ogg"},
        "Images": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".avif"},
        "Documents": {".pdf", ".docx", ".xlsx", ".pptx", ".txt", ".csv"},
        "Archives": {".zip", ".7z", ".rar", ".tar", ".gz"},
    }
    return next((group for group, suffixes in groups.items() if suffix in suffixes), "Other")
