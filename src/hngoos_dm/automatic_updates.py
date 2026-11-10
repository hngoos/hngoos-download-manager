"""Periodic signed release checks; install only after opting in and becoming idle."""

import platform
import sys
import threading
import time

from .platforms import launch_installer
from .updater import check_update, download_installer, select_installer, verify_package


def is_packaged():
    return bool(getattr(sys, "frozen", False)) and platform.system() == "Windows"


def has_active_work(app):
    """Completion in the journal can precede security scans and extraction finishing."""
    return bool(app.manager.active or getattr(app.manager, "safety_tasks", None)
                or getattr(app, "safety_scanning", None)
                or any(getattr(app, flag, False) for flag in ("media_busy", "media_tool_busy", "source_busy"))
                or any(not task.closed and not task.completed for task in getattr(app, "torrent_jobs", []))
                or any(not event.is_set() for event in getattr(app, "processing_stops", [])))


class AutomaticVideoUpdates:
    """Keep the standalone engine current without interrupting media work."""
    def __init__(self, app):
        self.app = app
        self.next_check = max(time.time()+30, app.store.setting("last_video_tool_check", 0)+24*3600)

    def tick(self, now=None):
        now = time.time() if now is None else now
        if (platform.system() != "Windows" or now < self.next_check
                or getattr(self.app, "_closing", False)
                or any(getattr(self.app, flag, False) for flag in ("media_busy", "source_busy", "media_tool_busy"))):
            return
        # Failed checks retry in an hour; successful checks survive app restarts.
        self.next_check = now+3600
        self.app.update_ytdlp()
        self.next_check = max(self.next_check, self.app.store.setting("last_video_tool_check", 0)+24*3600)


class AutomaticUpdates:
    CHECK_INTERVAL = 5*60
    RETRY_INTERVAL = 60

    def __init__(self, app):
        self.app = app
        # A release may have appeared since the previous session's check.
        self.next_check = time.time()+3
        self.busy = False
        self.worker = None
        self.ready = None

    def status(self, value):
        self.app.store.set_setting("automatic_update_status", value)
        variable = getattr(self.app, "automatic_update_status", None)
        if variable is not None:
            variable.set(value)

    def idle(self):
        return not (has_active_work(self.app)
                    or getattr(self.app, "page_stack", []) or getattr(self.app, "modal_card", None))

    def tick(self, now=None):
        if self.busy or getattr(self.app, "_closing", False):
            return
        install = self.app.store.setting("auto_install_updates", False)
        if self.ready and install:
            if self.idle() and is_packaged():
                _payload, asset, path = self.ready
                self.ready = None
                try:
                    verify_package(path, asset)
                    launch_installer(path, ("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"))
                    self.app.close()
                except (OSError, ValueError) as error:
                    self.status(f"Không thể cập nhật tự động: {error}")
            return
        now = now if now is not None else time.time()
        if not self.app.store.setting("auto_check_updates", True) or now < self.next_check:
            return
        manual = getattr(self.app, "update_dialog", None)
        if manual and not manual.closed:
            return
        self.next_check = now+self.CHECK_INTERVAL
        self.busy = True
        self.status("Đang kiểm tra cập nhật…")

        def work():
            try:
                payload = check_update()
                asset = path = None
                if payload and self.app.store.setting("auto_install_updates", False):
                    asset = select_installer(payload)
                    path = download_installer(payload, self.app.data_dir/"updates", asset=asset)
                    verify_package(path, asset)
                self.app.events.put(lambda: self.found(payload, asset, path))
            except Exception as error:  # noqa: BLE001 -- Optional background network failures stay in preferences.
                self.app.events.put(lambda error=str(error): self.failed(error))
        self.worker = threading.Thread(target=work, daemon=True)
        self.app.background_threads.append(self.worker)
        self.worker.start()

    def found(self, payload, asset, path):
        self.busy = False
        now = time.time()
        self.next_check = now+self.CHECK_INTERVAL
        self.app.store.set_setting("last_update_check", now)
        notify = getattr(self.app, "show_update_notice", None)
        if notify:
            notify(payload is not None)
        if payload is None:
            self.status("Bạn đang dùng phiên bản mới nhất.")
        elif path:
            self.ready = (payload, asset, path)
            self.status("Đã tải và xác minh bản cập nhật. Cài khi HDM rảnh hoặc mở Kiểm tra cập nhật.")
        else:
            self.status("Có bản cập nhật HDM {version}.".format(version=payload["version"]))

    def failed(self, error):
        self.busy = False
        self.next_check = time.time()+self.RETRY_INTERVAL
        self.status(f"Không thể cập nhật tự động: {error}")
