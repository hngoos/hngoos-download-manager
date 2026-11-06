"""In-app release checks and verified package download with an explicit OS handoff."""

import platform
import queue
import threading
import tkinter as tk
from tkinter import ttk

from . import __version__
from .platforms import open_path
from .updater import DownloadCancelled, check_update, download_installer, select_installer, verify_package


class UpdateDialog:
    def __init__(self, app):
        self.app = app
        self.window = tk.Toplevel(app.root)
        self.window.title("HDM · Check for update")
        self.window.transient(app.root)
        self.window.resizable(False, False)
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.events = queue.Queue()
        self.cancel = threading.Event()
        self.busy = False
        self.closed = False
        self.path = None
        self.payload = self.asset = None
        body = ttk.Frame(self.window, padding=24)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="Check for update", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(body, text=f"HDM {__version__}", style="Muted.TLabel").pack(anchor="w", pady=(8, 16))
        self.status = tk.StringVar(value="Đang kiểm tra cập nhật…")
        ttk.Label(body, textvariable=self.status, wraplength=430).pack(anchor="w", fill="x")
        self.progress = ttk.Progressbar(body, length=430, mode="indeterminate")
        self.progress.pack(fill="x", pady=20)
        self.actions = ttk.Frame(body)
        self.actions.pack(fill="x")
        self.primary = ttk.Button(self.actions, text="Thử lại", command=self.check)
        self.primary.pack(side="left")
        ttk.Button(self.actions, text="Đóng", command=self.close).pack(side="right")
        self.poll_id = self.window.after(50, self.poll)
        self.check()

    def bilingual(self, vi, en):
        return en if self.app.locale.language == "en" else vi

    def run(self, action, success):
        self.busy = True
        self.primary.configure(state="disabled")

        def work():
            try:
                value = action()
                self.events.put(("done", (success, value)))
            except DownloadCancelled:
                self.events.put(("cancelled", None))
            except Exception as error:  # noqa: BLE001 -- Show optional network/crypto errors in this dialog.
                self.events.put(("error", str(error)))

        worker = threading.Thread(target=work, daemon=True)
        self.app.background_threads.append(worker)
        worker.start()

    def poll(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "progress":
                    done, total = value
                    self.progress.configure(value=100*done/total)
                    self.status.set(f"{done/1048576:.1f} / {total/1048576:.1f} MB · {100*done/total:.0f}%")
                else:
                    self.busy = False
                    self.progress.stop()
                    if kind == "done":
                        callback, result = value
                        callback(result)
                    elif kind == "error":
                        self.status.set(self.bilingual("Không thể cập nhật: ", "Update failed: ")+value)
                        self.primary.configure(text="Thử lại", command=self.check, state="normal")
                    else:
                        self.status.set("Đã hủy tải bản cập nhật.")
                        self.primary.configure(text="Thử lại", command=self.check, state="normal")
        except queue.Empty:
            pass
        if not self.closed:
            self.app.locale.apply(self.window)
            self.poll_id = self.window.after(50, self.poll)

    def check(self):
        self.status.set("Đang kiểm tra cập nhật…")
        self.progress.configure(mode="indeterminate")
        self.progress.start()
        self.run(check_update, self.found)

    def found(self, payload):
        self.progress.configure(mode="determinate", value=0)
        if payload is None:
            self.status.set("Bạn đang dùng phiên bản mới nhất.")
            self.primary.configure(text="Thử lại", command=self.check, state="normal")
            return
        self.payload = payload
        try:
            self.asset = select_installer(payload)
        except ValueError as error:
            self.status.set(str(error))
            self.primary.configure(text="Thử lại", command=self.check, state="normal")
            return
        self.status.set(self.bilingual(
            f"Có HDM {payload['version']} · {self.asset['size']/1048576:.1f} MB\nChữ ký nhà phát hành đã được xác minh.",
            f"HDM {payload['version']} available · {self.asset['size']/1048576:.1f} MB\nPublisher signature verified."))
        self.primary.configure(text="Tải bản cập nhật", command=self.download, state="normal")

    def download(self):
        self.cancel.clear()
        self.progress.configure(mode="determinate", value=0)
        self.status.set(self.bilingual("Đang tải bản cập nhật…", "Downloading update…"))
        self.run(lambda: download_installer(self.payload, self.app.data_dir/"updates",
            progress=lambda done, total: self.events.put(("progress", (done, total))),
            cancel=self.cancel, asset=self.asset), self.downloaded)

    def downloaded(self, path):
        self.path = path
        self.progress.configure(value=100)
        self.status.set("Đã tải và xác minh bản cập nhật.")
        self.primary.configure(text="Cài đặt bản cập nhật", command=self.install, state="normal")

    def install(self):
        # Do not interrupt transfers, media processing or a live application session.
        if (self.app.manager.active or getattr(self.app, "media_busy", False)
                or any(not job.closed and not job.completed for job in getattr(self.app, "torrent_jobs", []))):
            self.status.set(self.bilingual("Hãy tạm dừng hoặc hoàn tất các tác vụ trước khi cài cập nhật.",
                                           "Pause or finish active tasks before installing the update."))
            return
        self.run(lambda: verify_package(self.path, self.asset), self.launch)

    def launch(self, path):
        try:
            if path.suffix == ".AppImage":
                path.chmod(path.stat().st_mode | 0o100)
                open_path(path.parent)
                self.status.set(self.bilingual("Bản mới đã sẵn sàng trong thư mục cập nhật. Đóng HDM rồi chạy tệp AppImage.",
                                               "The update is ready in this folder. Close HDM, then run the AppImage."))
            else:
                open_path(path)
                self.status.set(self.bilingual("Hoàn tất cài đặt trong cửa sổ hệ thống, sau đó mở lại HDM.",
                                               "Finish installation in the system window, then restart HDM."))
                if platform.system() == "Windows":
                    self.app.close()
                    return
            self.primary.configure(text="Mở thư mục cập nhật", command=lambda: open_path(path.parent), state="normal")
        except OSError as error:
            self.status.set(str(error))
            self.primary.configure(text="Mở bộ cài", command=self.install, state="normal")

    def close(self):
        self.cancel.set()
        if not self.closed and self.window.winfo_exists():
            self.closed = True
            self.window.after_cancel(self.poll_id)
            self.window.destroy()
