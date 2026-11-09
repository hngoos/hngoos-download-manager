"""In-app release checks and verified package download with an explicit OS handoff."""

import platform
import queue
import threading
import tkinter as tk
from tkinter import ttk

from . import __version__
from .automatic_updates import has_active_work
from .information_ui import CenteredCard
from .platforms import launch_installer, open_path
from .rounded import RoundedButton
from .updater import DownloadCancelled, check_update, download_installer, select_installer, verify_package


class UpdateDialog:
    def __init__(self, app, ready=None):
        self.app = app
        self.window = CenteredCard(app, "Kiểm tra cập nhật", height=290, on_close=self.close)
        self.events = queue.Queue()
        self.cancel = threading.Event()
        self.busy = False
        self.closed = False
        self.path = None
        self.payload = self.asset = None
        body = ttk.Frame(self.window.body, style="Card.TFrame")
        body.pack(fill="both", expand=True)
        self.status = tk.StringVar(value=app.locale.text("Phiên bản hiện tại: {version}").format(version=__version__))
        self.ready = ready
        self.status_label = ttk.Label(body, textvariable=self.status, wraplength=430, style="Card.TLabel", anchor="center", justify="center")
        self.status_label.place(relx=.5, rely=.5, anchor="center", relwidth=1)
        self.actions = self.window.footer
        self.primary = RoundedButton(self.actions, text="", image=app.icons["refresh"], command=self.check, width=44, height=44)
        self.primary.pack(side="top", pady=(0, 8))
        self.poll_id = self.window.after(50, self.poll)
        self.window.bind("<Destroy>", lambda event: self.dispose() if event.widget == self.window else None)
        app.apply_preferences()

    def reset_check_button(self):
        self.primary.configure(text="", image=self.app.icons["refresh"], width=44, command=self.check, state="normal")

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
                    self.status.set(f"{done/1048576:.1f} / {total/1048576:.1f} MB · {100*done/total:.0f}%")
                else:
                    self.busy = False
                    if kind == "done":
                        callback, result = value
                        callback(result)
                    elif kind == "error":
                        self.status.set(self.bilingual("Không thể cập nhật: ", "Update failed: ")+self.app.locale.text(value))
                        self.reset_check_button()
                    else:
                        self.status.set("Đã hủy tải bản cập nhật.")
                        self.reset_check_button()
        except queue.Empty:
            pass
        if not self.closed:
            self.app.locale.apply(self.window)
            self.poll_id = self.window.after(50, self.poll)

    def check(self):
        if self.busy or self.closed:
            return
        self.status.set("Đang kiểm tra cập nhật…")
        self.run(check_update, self.found)

    def found(self, payload):
        self.app.show_update_notice(payload is not None)
        if payload is None:
            self.status.set("Không có bản cập nhật mới.")
            self.reset_check_button()
            return
        self.payload = payload
        try:
            self.asset = select_installer(payload)
        except ValueError as error:
            self.status.set(self.app.locale.text(str(error)))
            self.reset_check_button()
            return
        self.status.set(self.bilingual(
            f"Có HDM {payload['version']} · {self.asset['size']/1048576:.1f} MB\nChữ ký nhà phát hành đã được xác minh.",
            f"HDM {payload['version']} available · {self.asset['size']/1048576:.1f} MB\nPublisher signature verified."))
        self.primary.configure(image=None, width=210, text="Tải bản cập nhật", command=self.download, state="normal")
        if self.ready and self.ready[0]["version"] == payload["version"] and self.ready[1] == self.asset:
            self.downloaded(self.ready[2])

    def download(self):
        self.cancel.clear()
        self.status.set(self.bilingual("Đang tải bản cập nhật…", "Downloading update…"))
        self.run(lambda: download_installer(self.payload, self.app.data_dir/"updates",
            progress=lambda done, total: self.events.put(("progress", (done, total))),
            cancel=self.cancel, asset=self.asset), self.downloaded)

    def downloaded(self, path):
        self.path = path
        self.status.set("Đã tải và xác minh bản cập nhật.")
        self.primary.configure(image=None, width=210, text="Cài đặt bản cập nhật", command=self.install, state="normal")

    def can_install(self):
        if has_active_work(self.app):
            self.status.set(self.bilingual("Hãy tạm dừng hoặc hoàn tất các tác vụ trước khi cài cập nhật.",
                                           "Pause or finish active tasks before installing the update."))
            self.primary.configure(state="normal", command=self.install)
            return False
        return True

    def install(self):
        if not self.can_install():
            return
        self.run(lambda: verify_package(self.path, self.asset), self.launch)

    def launch(self, path):
        if not self.can_install():
            return
        try:
            if path.suffix == ".AppImage":
                path.chmod(path.stat().st_mode | 0o100)
                open_path(path.parent)
                self.status.set(self.bilingual("Bản mới đã sẵn sàng trong thư mục cập nhật. Đóng HDM rồi chạy tệp AppImage.",
                                               "The update is ready in this folder. Close HDM, then run the AppImage."))
            else:
                if platform.system() == "Windows":
                    launch_installer(path)
                else:
                    open_path(path)
                self.status.set(self.bilingual("Hoàn tất cài đặt trong cửa sổ hệ thống, sau đó mở lại HDM.",
                                               "Finish installation in the system window, then restart HDM."))
                if platform.system() == "Windows":
                    self.app.close()
                    return
            self.primary.configure(text="Mở thư mục cập nhật", command=lambda: open_path(path.parent), state="normal")
        except OSError as error:
            self.status.set(self.app.locale.text(str(error)))
            self.primary.configure(text="Mở bộ cài", command=self.install, state="normal")

    def close(self):
        self.dispose()
        if self.window.winfo_exists():
            self.window.destroy()

    def dispose(self):
        self.cancel.set()
        if not self.closed:
            self.closed = True
            self.window.after_cancel(self.poll_id)
