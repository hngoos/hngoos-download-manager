"""Opt-in monitoring of newly created/modified files in a chosen download folder."""

import threading
from pathlib import Path

from .files import checksums, mark_internet
from .safety import inspect_file


class DirectoryGuard:
    def __init__(self, folder, store, interval=1.0):
        self.folder = Path(folder).resolve()
        if not self.folder.is_dir():
            raise ValueError("Chọn thư mục tải có sẵn để theo dõi.")
        self.store = store
        self.interval = interval
        self.stop = threading.Event()
        self.lock = threading.RLock()
        self.known = self.snapshot()
        self.pending = {}
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def snapshot(self):
        files = {}
        for path in self.folder.iterdir():
            try:
                if (path.is_file() and not path.is_symlink()
                        and path.suffix.lower() not in {".crdownload", ".part", ".tmp", ".chuakiemtra"}):
                    stat = path.stat()
                    files[path] = (stat.st_size, stat.st_mtime_ns)
            except OSError:
                continue
        return files

    def scan_once(self):
        with self.lock:
            self._scan_once()

    def _scan_once(self):
        current = self.snapshot()
        for path, signature in current.items():
            if self.known.get(path) == signature:
                continue
            old_signature, repeats = self.pending.get(path, (None, 0))
            repeats = repeats+1 if old_signature == signature else 0
            self.pending[path] = signature, repeats
            if repeats < 2:
                continue
            try:
                reasons = inspect_file(path, path.name, high_security=self.store.setting("high_security", False))
                if reasons:
                    digest = checksums(path, ("sha256",))["sha256"]
                    # Do not quarantine a file which changed while it was inspected.
                    after = path.stat()
                    if (after.st_size, after.st_mtime_ns) != signature:
                        continue
                    target = path.with_name(path.name+".chuakiemtra")
                    if target.exists():
                        continue
                    path.rename(target)
                    mark_internet(target)
                    entries = self.store.setting("guard_log", [])
                    entries.append({"source": str(path), "quarantine": str(target), "sha256": digest, "reasons": reasons})
                    self.store.set_setting("guard_log", entries[-200:])
                self.known[path] = signature
                self.pending.pop(path, None)
            except OSError:
                continue  # Browser/antivirus may still hold the file; retry after it closes.
        self.known = {path: signature for path, signature in self.known.items() if path in current}
        self.pending = {path: value for path, value in self.pending.items() if path in current}

    def _run(self):
        while not self.stop.wait(self.interval):
            self.scan_once()

    def accept_restored(self, path):
        path = Path(path).resolve()
        with self.lock:
            if path.parent == self.folder:
                state = path.stat()
                self.known[path] = (state.st_size, state.st_mtime_ns)
                self.pending.pop(path, None)

    def close(self):
        self.stop.set()
        self.thread.join(timeout=15)
