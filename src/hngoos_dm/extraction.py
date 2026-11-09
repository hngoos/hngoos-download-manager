"""Bounded ZIP extraction after triage; rejects paths, symlinks, programs and overwrite."""

import shutil
import stat
import tempfile
import zipfile
from pathlib import Path

from .files import mark_internet
from .safety import inspect_zip


def extract_zip(source, destination, password=None):
    destination = Path(destination).resolve()
    if destination.exists():
        raise ValueError("Chọn thư mục mới để tránh ghi đè dữ liệu đã có.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(source) as archive:
        reasons = inspect_zip(archive, password=password)
        if reasons:
            raise ValueError("Không tự giải nén ZIP có dấu hiệu rủi ro: " + "; ".join(reasons[:5]))
        total = sum(item.file_size for item in archive.infolist())
        if total > 2 * 1024**3:
            raise ValueError("ZIP vượt giới hạn giải nén 2 GB.")
        if shutil.disk_usage(destination.parent).free < total + 64*1024*1024:
            raise ValueError("Không đủ dung lượng đĩa để giải nén.")
        with tempfile.TemporaryDirectory(prefix=".hngoos-extract-", dir=destination.parent) as folder:
            staging = Path(folder)/"files"
            staging.mkdir()
            for item in archive.infolist():
                target = (staging/item.filename.replace("\\", "/")).resolve()
                if staging not in target.parents or stat.S_ISLNK(item.external_attr >> 16):
                    raise ValueError("ZIP có đường dẫn hoặc liên kết không hợp lệ.")
                if item.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(item, pwd=password.encode() if password else None) as incoming, target.open("xb") as outgoing:
                    shutil.copyfileobj(incoming, outgoing, 128*1024)
                mark_internet(target)
            staging.rename(destination)
    return destination
