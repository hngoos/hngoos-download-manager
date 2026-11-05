"""Optional libtorrent session with explicit selection and no seeding after completion."""

import hashlib
import threading
import time
from pathlib import Path

from .safety import RISKY, inspect_file


class TorrentJob:
    def __init__(self, source, directory, local_only=False, state_directory=None):
        try:
            import libtorrent as lt
        except ImportError as exc:
            raise ValueError('Cần cài hỗ trợ torrent: pip install ".[torrent]"') from exc
        self.lt = lt
        self.directory = Path(directory).expanduser().resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.state_directory = Path(state_directory or self.directory/".hngoos-torrents").resolve()
        self.state_directory.mkdir(parents=True, exist_ok=True)
        self.session = lt.session({"listen_interfaces": "127.0.0.1:0" if local_only else "0.0.0.0:0", "enable_upnp": False,
                                   "enable_dht": not local_only, "enable_lsd": not local_only,
                                   "enable_natpmp": False, "alert_mask": lt.alert.category_t.status_notification
                                   | lt.alert.category_t.storage_notification | lt.alert.category_t.error_notification})
        if source.startswith("magnet:?"):
            params = lt.parse_magnet_uri(source)
        else:
            path = Path(source).resolve()
            if not path.is_file() or path.suffix.lower() != ".torrent":
                raise ValueError("Chọn tệp .torrent hoặc magnet hợp lệ.")
            params = lt.add_torrent_params()
            params.ti = lt.torrent_info(str(path))
            cached_source = self.state_directory/(hashlib.sha256(path.read_bytes()).hexdigest()+".torrent")
            if not cached_source.exists():
                cached_source.write_bytes(path.read_bytes())
            source = str(cached_source)
        self.source = source
        hashes = params.ti.info_hashes() if params.ti else params.info_hashes
        key = hashlib.sha256((str(hashes.v1)+str(hashes.v2)).encode()).hexdigest()
        self.resume_path = self.state_directory/(key+".fastresume")
        self.restored = False
        if self.resume_path.is_file():
            try:
                resumed = lt.read_resume_data(self.resume_path.read_bytes())
                if Path(resumed.save_path).resolve() == self.directory:
                    params = resumed
                    self.restored = True
            except (RuntimeError, ValueError):
                pass  # Corrupt state must not prevent a normal verified recheck/download.
        params.save_path = str(self.directory)
        if not self.restored:
            params.flags |= lt.torrent_flags.upload_mode
        else:
            params.flags |= lt.torrent_flags.paused
        params.flags &= ~lt.torrent_flags.auto_managed
        self.handle = self.session.add_torrent(params)
        self.closed = False
        self.completed = False
        self.resume_event = threading.Event()
        self.resume_event.set()
        self.cache_event = threading.Event()
        self.resume_lock = threading.Lock()
        self.alert_lock = threading.Lock()
        self.last_save = time.monotonic()
        self.save_error = ""
        self.stop = threading.Event()
        self.monitor = threading.Thread(target=self._monitor, daemon=True)
        self.monitor.start()

    def files(self):
        if not self.handle.status().has_metadata:
            return None
        storage = self.handle.torrent_file().files()
        result = []
        for index in range(storage.num_files()):
            relative = storage.file_path(index)
            target = (self.directory / relative).resolve()
            if self.directory not in target.parents:
                self.close()
                raise ValueError("Torrent chứa đường dẫn vượt thư mục lưu.")
            risky = Path(relative).suffix.lower() in RISKY
            result.append({"index": index, "name": relative, "size": storage.file_size(index), "risky": risky})
        return result

    def select(self, indexes):
        files = self.files()
        if files is None:
            raise ValueError("Đang chờ metadata torrent.")
        selected = set(indexes)
        priorities = [4 if file["index"] in selected else 0 for file in files]
        if not any(priorities):
            raise ValueError("Chọn ít nhất một tệp để tải.")
        self.handle.prioritize_files(priorities)
        self.handle.unset_flags(self.lt.torrent_flags.upload_mode)
        self.handle.resume()

    def status(self):
        status = self.handle.status()
        return {"progress": status.progress, "download_rate": status.download_rate,
                "upload_rate": status.upload_rate, "peers": status.num_peers,
                "metadata": status.has_metadata, "paused": bool(status.flags & self.lt.torrent_flags.paused),
                "complete": self.completed, "error": status.errc.message() if status.errc.value() else self.save_error}

    def pause(self):
        self.handle.pause()
        self.checkpoint()

    def resume(self):
        if not self.completed:
            self.handle.resume()

    def _monitor(self):
        while not self.stop.wait(0.2):
            self._alerts()
            status = self.handle.status()
            if status.has_metadata and time.monotonic()-self.last_save >= 30:
                self.checkpoint()
            ready = (status.is_finished and status.has_metadata and status.total_wanted > 0
                     and status.total_wanted_done >= status.total_wanted
                     and status.state in {self.lt.torrent_status.finished, self.lt.torrent_status.seeding})
            if ready and not self.completed:
                self.handle.pause()
                # Verified pieces may still be in libtorrent's disk cache. Do not publish completion
                # or inspect the output until the flush checkpoint has actually completed.
                if not self.flush() or not self.checkpoint(wait=True):
                    continue
                try:
                    self._triage()
                except OSError as exc:
                    self.save_error = str(exc)
                    continue
                self.completed = True

    def flush(self):
        """Explicitly release file mappings/handles before inspecting data or reopening a session."""
        self.cache_event.clear()
        self.handle.flush_cache()
        deadline = time.monotonic()+10
        while not self.cache_event.is_set() and time.monotonic() < deadline:
            self._alerts()
            self.cache_event.wait(0.02)
        if not self.cache_event.is_set():
            self.save_error = "Chưa ghi xong dữ liệu torrent xuống đĩa; giữ trạng thái tạm dừng."
        return self.cache_event.is_set()

    def _wait_checkpoint(self):
        deadline = time.monotonic()+10
        while not self.resume_event.is_set() and time.monotonic() < deadline:
            self._alerts()
            self.resume_event.wait(0.02)
        return self.resume_event.is_set() and not self.save_error

    def checkpoint(self, wait=False):
        """Libtorrent serializes verified pieces/priorities; use an atomic local checkpoint."""
        with self.resume_lock:
            # A completion flush must never consume the acknowledgement of an older save request.
            if not self.resume_event.is_set() and not self._wait_checkpoint():
                return False
            self.resume_event.clear()
            self.save_error = ""
            self.handle.save_resume_data(self.lt.save_resume_flags_t.flush_disk_cache)
            self.last_save = time.monotonic()
            if wait:
                return self._wait_checkpoint()
        return True

    def _alerts(self):
        with self.alert_lock:
            self._drain_alerts()

    def _drain_alerts(self):
        for alert in self.session.pop_alerts():
            if isinstance(alert, self.lt.save_resume_data_alert):
                temporary = self.resume_path.with_suffix(".tmp")
                try:
                    temporary.write_bytes(self.lt.write_resume_data_buf(alert.params))
                    temporary.replace(self.resume_path)
                except OSError as exc:
                    self.save_error = str(exc)
                finally:
                    self.resume_event.set()
            elif isinstance(alert, self.lt.save_resume_data_failed_alert):
                self.save_error = str(alert.message())
                self.resume_event.set()
            elif isinstance(alert, self.lt.cache_flushed_alert):
                self.cache_event.set()

    def _triage(self):
        files = self.files() or []
        priorities = self.handle.get_file_priorities()
        from .files import mark_internet
        for item in files:
            if self.stop.is_set():
                return
            path = self.directory / item["name"]
            if priorities[item["index"]]:
                if not path.is_file() or path.stat().st_size != item["size"]:
                    raise OSError("Dung lượng tệp torrent trên đĩa chưa khớp metadata; chưa thể báo hoàn tất.")
                mark_internet(path)
                if inspect_file(path, path.name):
                    target = path.with_name(path.name+".chuakiemtra")
                    if not target.exists():
                        path.rename(target)

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.stop.set()
        self.handle.pause()
        if self.monitor is not threading.current_thread():
            self.monitor.join(timeout=25)
        self.flush()
        self.checkpoint(wait=True)
        self.session.remove_torrent(self.handle)
