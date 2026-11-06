"""Vietnamese desktop UI for Windows, macOS and Linux with Tkinter."""

import argparse
import os
import queue
import threading
import time
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from . import __version__
from .engine import DownloadManager
from .instance import InstanceLock
from .paths import data_directory
from .platforms import open_path
from .safety import filename_from_url, scan_defender, sha256_file
from .store import Store

BG, PANEL, TEXT, MUTED, BLUE = "#0f121c", "#181d2b", "#e6edf8", "#9cabc3", "#a78bfa"
STATES = {"queued": "Đang chờ", "downloading": "Đang tải", "paused": "Tạm dừng",
          "verifying": "Kiểm tra", "complete": "Hoàn tất", "quarantined": "Cách ly", "error": "Lỗi",
          "scheduled": "Đã hẹn giờ"}


def human(size):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


class App:
    def __init__(self, root, data_dir=None):
        self.root = root
        self.root.title(f"Hngoos Download Manager · HDM {__version__}")
        self.root.geometry("1280x800")
        self.root.minsize(1120, 720)
        self.root.configure(bg=BG)
        data_dir = data_dir or data_directory()
        self.store = Store(data_dir / "downloads.sqlite3")
        if self.store.setting("auto_defender") is None:
            self.store.set_setting("auto_defender", os.name == "nt")
        self.data_dir = data_dir
        from .ui_preferences import PALETTES, Localizer
        self.theme = self.store.setting("theme", "dark")
        if self.theme not in PALETTES:
            self.theme = "dark"
        self.locale = Localizer(root, self.store.setting("language", "vi"))
        self.manager = DownloadManager(self.store)
        self.events = queue.Queue()
        self.background_threads = []
        self.last_jobs = {}
        self.directory = tk.StringVar(value=self.store.setting("download_directory", str(Path.home() / "Downloads")))
        self.url = tk.StringVar()
        self.filename = tk.StringVar()
        self.connections = tk.StringVar(value="32")
        self.expected_hash = tk.StringVar()
        self.hash_algorithm = tk.StringVar(value="SHA-256")
        self.mirrors = tk.StringVar()
        self.bandwidth_mode = tk.StringVar(value={"maximum": "Tối đa", "medium": "Vừa (4 MB/s)", "light": "Nhẹ (512 KB/s)"}[
            self.store.setting("bandwidth_mode", "maximum")])
        self.media_stop = threading.Event()
        self.media_url = tk.StringVar()
        self.media_quality = tk.StringVar(value="1080")
        self.media_playlist = tk.BooleanVar()
        self.media_subtitles = tk.BooleanVar()
        self.media_cookie = tk.StringVar()
        self.media_format = tk.StringVar()
        self.download_format = tk.StringVar(value="Auto")
        self.media_status = tk.StringVar()
        self.clipboard_enabled = tk.BooleanVar(value=self.store.setting("clipboard_enabled", True))
        self.clipboard_notice = tk.StringVar()
        self.clipboard_last = ""
        self.clipboard_pending = ""
        self.clipboard_checked = 0
        self.browser_session = ""
        self.browser_session_url = ""
        self.video_inbox_busy = False
        self.power_seen_work = False
        self.sleep_prevented = False
        self.status = tk.StringVar(value="Sẵn sàng · dữ liệu tải được lưu trên máy của bạn")
        self._styles()
        from .icons import MorphPlayback, decorate_buttons, load_brand_icons, load_icons
        self.brand_icons = load_brand_icons(root)
        self.icons = load_icons(root)
        self.primary_icons = self.icons
        self._layout()
        decorate_buttons(root, self.icons)
        self.playback_icon = MorphPlayback(self.transfer_button)
        self.apply_preferences()
        self.root.bind_all("<Map>", self._presentation_mapped, add="+")
        self.root.protocol("WM_DELETE_WINDOW", self.request_close)
        self.refresh_id = self.root.after(200, self.refresh)

    def _styles(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        light = self.theme == "light"
        control = "#edf0f6" if light else "#242b3e"
        hover = "#e4e8f0" if light else "#344e73"
        border = "#b4bfd1" if light else "#30364b"
        selected = "#d6c7f5" if light else "#3c2c61"
        primary = "#6d28d9" if light else "#7c3aed"
        style.configure(".", background=BG, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("TFrame", background=BG)
        style.configure("Card.TFrame", background=PANEL)
        style.configure("TLabel", background=BG, foreground=TEXT)
        style.configure("Muted.TLabel", foreground=MUTED)
        style.configure("Title.TLabel", font=("Segoe UI", 26, "bold"))
        style.configure("TButton", padding=(12, 8), background=control, foreground=TEXT,
                        borderwidth=0, bordercolor=BG, lightcolor=BG, darkcolor=BG)
        style.map("TButton", background=[("active", hover)], foreground=[("disabled", MUTED)])
        style.configure("Primary.TButton", background=primary, foreground="white")
        style.map("Primary.TButton", background=[("active", "#5820b8" if light else "#8b5cf6")],
                  foreground=[("disabled", "#d6c7f5"), ("!disabled", "white")])
        style.configure("Nav.TButton", background=BG, foreground=MUTED, anchor="w", padding=(12, 14))
        style.map("Nav.TButton", background=[("active", control)], foreground=[("active", TEXT)])
        style.configure("ActiveNav.TButton", background="#e9e0fc" if light else "#2e2249",
                        foreground=BLUE if light else "#d9c8ff", anchor="w", padding=(12, 14))
        style.map("ActiveNav.TButton", background=[("active", "#e9e0fc" if light else "#2e2249")],
                  foreground=[("active", BLUE if light else "#d9c8ff")])
        style.configure("TEntry", fieldbackground=PANEL, foreground=TEXT, insertcolor=TEXT,
                        padding=8, bordercolor=border, lightcolor=border, darkcolor=border)
        style.map("TEntry", selectbackground=[("!disabled", selected)], selectforeground=[("!disabled", TEXT)])
        style.configure("TCombobox", fieldbackground=PANEL, foreground=TEXT, padding=8,
                        background=control, arrowcolor=MUTED, bordercolor=border, lightcolor=border, darkcolor=border)
        style.map("TCombobox", fieldbackground=[("readonly", PANEL)], foreground=[("readonly", TEXT)])
        style.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=TEXT,
                        rowheight=38, borderwidth=0, bordercolor=PANEL, lightcolor=PANEL, darkcolor=PANEL)
        style.configure("Treeview.Heading", background=control, foreground=MUTED, padding=10,
                        bordercolor=PANEL, lightcolor=PANEL, darkcolor=PANEL, relief="flat")
        style.map("Treeview", background=[("selected", selected)], foreground=[("selected", TEXT)])
        style.configure("TCheckbutton", background=BG, foreground=TEXT, indicatorbackground=PANEL)
        style.map("TCheckbutton", background=[("active", BG)],
                  foreground=[("disabled", MUTED), ("active", TEXT)],
                  indicatorbackground=[("selected", primary), ("!selected", PANEL)])
        style.configure("TRadiobutton", background=BG, foreground=TEXT)
        style.map("TRadiobutton", background=[("active", BG)], foreground=[("active", TEXT)])
        style.configure("Horizontal.TProgressbar", troughcolor=control, background=BLUE,
                        bordercolor=control, lightcolor=BLUE, darkcolor=BLUE)
        style.configure("TNotebook", borderwidth=0)
        style.layout("HDM.TNotebook.Tab", [])
        style.configure("HDM.TNotebook", borderwidth=0, tabmargins=0, bordercolor=BG, lightcolor=BG, darkcolor=BG)
        style.configure("Vertical.TScrollbar", background="#30364b", troughcolor=PANEL,
                        arrowcolor=MUTED, bordercolor=PANEL, lightcolor=PANEL, darkcolor=PANEL)
        style.configure("TNotebook.Tab", background=PANEL, foreground=MUTED, padding=(20, 12))
        style.map("TNotebook.Tab", background=[("selected", "#e1e9f8" if light else "#263d5c")],
                  foreground=[("selected", TEXT)])
        self.root.option_add("*TCombobox*Listbox.background", PANEL)
        self.root.option_add("*TCombobox*Listbox.foreground", TEXT)
        self.root.option_add("*TCombobox*Listbox.selectBackground", selected)
        self.root.option_add("*TCombobox*Listbox.selectForeground", TEXT)
        self.root.option_add("*Background", BG)
        self.root.option_add("*Foreground", TEXT)
        self.root.option_add("*selectBackground", selected)
        self.root.option_add("*selectForeground", TEXT)

    def _layout(self):
        from .rounded import RoundedButton
        from .ui_preferences import SlideSwitch
        shell = ttk.Frame(self.root, padding=(24, 12, 24, 18))
        shell.pack(fill="both", expand=True)
        header = ttk.Frame(shell)
        header.pack(fill="x", pady=(0, 14))
        self.brand_label = ttk.Label(header, image=self.brand_icons[0])
        self.brand_label.pack(side="left")
        controls = self.header_controls = ttk.Frame(header)
        controls.pack(side="right")
        self.theme_switch = SlideSwitch(controls, ("☀", "☾"), self.theme == "dark",
            lambda dark: self.set_preference("theme", "dark" if dark else "light"), "Light / Dark")
        self.theme_switch.pack(side="left", padx=(0, 12))
        self.info_button = RoundedButton(controls, text="Thông tin", command=self.open_information, width=120)
        self.info_button.pack(side="left")
        self.tabs = ttk.Notebook(shell, style="HDM.TNotebook")
        self.tabs.pack(fill="both", expand=True)
        downloads = ttk.Frame(self.tabs)
        self.tabs.add(downloads, text="Tải xuống")
        self._downloads(downloads)
        self.close_to_tray = tk.BooleanVar(value=self.store.setting("close_to_tray", False))
        self.shutdown_after = tk.BooleanVar()

    def open_information(self):
        from .information_ui import information_menu
        previous = getattr(self, "information_menu", None)
        if previous:
            previous.destroy()
        self.information_menu = information_menu(self)
        try:
            self.information_menu.tk_popup(self.info_button.winfo_rootx(),
                                            self.info_button.winfo_rooty()+self.info_button.winfo_height()+4)
        finally:
            self.information_menu.grab_release()

    def open_preferences(self):
        from .information_ui import content_dialog
        return content_dialog(self, "preferences_dialog", "Thiết lập", [
            ("Chung", self._download_settings), ("An toàn", self._safety), ("Công cụ", self._tools)])

    def open_about(self):
        from .information_ui import content_dialog
        return content_dialog(self, "about_dialog", "Giới thiệu", [("", self._about)])

    def _download_settings(self, parent):
        ttk.Checkbutton(parent, text="Tự nhận link từ clipboard", variable=self.clipboard_enabled,
                        command=lambda: self.store.set_setting("clipboard_enabled", self.clipboard_enabled.get())).pack(
                            anchor="w", pady=10)
        ttk.Label(parent, text="Chỉ nhận link trên máy; chờ bạn bấm tải trước khi kết nối tới nguồn.",
                  style="Muted.TLabel", wraplength=800).pack(anchor="w")
        ttk.Label(parent, text="Thư mục tải mặc định", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(20, 8))
        destination = ttk.Frame(parent)
        destination.pack(fill="x")
        ttk.Entry(destination, textvariable=self.directory).pack(side="left", fill="x", expand=True)
        ttk.Button(destination, text="Chọn thư mục", command=self.choose_directory).pack(side="left", padx=8)
        startup = tk.BooleanVar(value=self.store.setting("startup_enabled", False))
        def toggle_startup():
            from .startup import set_enabled
            try:
                set_enabled(startup.get())
                self.store.set_setting("startup_enabled", startup.get())
            except (OSError, ValueError) as exc:
                startup.set(not startup.get())
                messagebox.showerror("HDM", str(exc), parent=self.root)
        ttk.Checkbutton(parent, text="Khởi động cùng hệ điều hành", variable=startup,
                        command=toggle_startup).pack(anchor="w", pady=14)
        self.startup_enabled = startup
        ttk.Button(parent, text="Check for update", command=self.check_update).pack(anchor="w", pady=12)
        ttk.Button(parent, text="Cập nhật bộ tải video…", command=self.update_ytdlp).pack(anchor="w", pady=12)

    def set_preference(self, key, value):
        self.store.set_setting(key, value)
        if key == "theme":
            self.theme = value
        else:
            self.locale.language = value
        self.apply_preferences()

    def _presentation_mapped(self, _event):
        if not getattr(self, "_presentation_pending", False):
            self._presentation_pending = True
            self.root.after_idle(self.apply_preferences)

    def apply_preferences(self):
        from .ui_preferences import DARK_COLORS, PALETTES, recolor
        global BG, PANEL, TEXT, MUTED, BLUE
        BG, PANEL, TEXT, MUTED, BLUE = PALETTES[self.theme]
        self._styles()
        colors = DARK_COLORS if self.theme == "light" else {value: key for key, value in reversed(DARK_COLORS.items())}
        style = ttk.Style(self.root)
        for name in ("Vertical.TScrollbar", "TNotebook.Tab"):
            for key, value in (style.configure(name) or {}).items():
                if str(value).lower() in colors:
                    style.configure(name, **{key: colors[str(value).lower()]})
        recolor(self.root, colors)
        if getattr(self, "_icon_theme", "dark") != self.theme:
            from .icons import load_icons
            old_icons = self.icons
            self.icons = load_icons(self.root, light=self.theme == "light")
            replacements = {str(old_icons[name]): image for name, image in self.icons.items()}

            def replace_images(parent):
                for widget in parent.winfo_children():
                    if "image" in set(widget.keys()):
                        image = widget.cget("image")
                        key = str(image[0]) if isinstance(image, tuple) and image else str(image)
                        if key in replacements:
                            match = next(name for name, old in old_icons.items() if str(old) == key)
                            widget.configure(image=self.primary_icons[match] if self.theme == "light"
                                and str(widget.cget("style")) == "Primary.TButton" else replacements[key])
                    replace_images(widget)
            replace_images(self.root)
            self.playback_icon.set_theme(self.theme == "light")
            self._icon_theme = self.theme
        self.theme_switch.theme = self.theme
        self.theme_switch.value = self.theme == "dark"
        self.theme_switch.draw()
        self.locale.apply()
        from .rounded import RoundedButton, RoundedPanel
        def present(parent):
            for widget in parent.winfo_children():
                if isinstance(widget, (RoundedPanel, RoundedButton)):
                    widget.set_presentation(self.theme, self.locale.text)
                present(widget)
        present(self.root)
        bandwidth_labels = ("Tối đa", "Vừa (4 MB/s)", "Nhẹ (512 KB/s)")
        self.bandwidth_selector.configure(values=tuple(self.locale.text(value) for value in bandwidth_labels))
        self.bandwidth_display.set(self.locale.text(self.bandwidth_mode.get()))
        self.last_jobs.clear()
        self._presentation_pending = False

    def scrollable(self, parent):
        canvas = tk.Canvas(parent, bg=BG, highlightthickness=0, height=1, width=1)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True)
        canvas.configure(yscrollcommand=scrollbar.set)
        content = ttk.Frame(canvas)
        window = canvas.create_window(0, 0, window=content, anchor="nw")
        content.bind("<Configure>", lambda _: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window, width=event.width))
        return content

    def _downloads(self, parent):
        from .rounded import RoundedPanel
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(2, weight=1)
        self.url_panel = RoundedPanel(parent, height=72)
        self.url_panel.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        form = self.url_panel.content
        form.columnconfigure(1, weight=1)
        ttk.Label(form, text="Link", background=PANEL,
                  foreground=MUTED).grid(row=0, column=0, sticky="w", padx=(0, 12))
        self.url_entry = ttk.Entry(form, textvariable=self.url)
        self.url_entry.grid(row=0, column=1, sticky="ew")
        ttk.Label(form, text="Enter", background=PANEL, foreground=MUTED).grid(row=0, column=2, padx=(12, 0))
        self.url_entry.bind("<Return>", lambda _event: self.prepare_download())
        self.editor_panel = RoundedPanel(parent, height=240, padding=16)
        self.source_hint = tk.StringVar(value="Tệp gốc · tối đa 32 kết nối · kiểm tra an toàn sau tải")
        self.clipboard_frame = ttk.Frame(form, style="Card.TFrame")
        self.clipboard_frame.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        ttk.Label(self.clipboard_frame, textvariable=self.clipboard_notice, background=PANEL,
                  foreground=MUTED).pack(side="left")
        self.clipboard_button = ttk.Button(self.clipboard_frame, text="Dùng link mới", command=self.use_clipboard_link)
        self.clipboard_frame.grid_remove()
        self.url.trace_add("write", self.link_changed)
        self.footer = ttk.Frame(parent)
        self.footer.grid(row=3, column=0, sticky="ew", pady=(14, 0))
        self.speed = tk.StringVar(value="0 B/s")
        ttk.Label(self.footer, textvariable=self.speed, font=("Segoe UI", 13, "bold")).pack(side="left", padx=(0, 16))
        self.bandwidth_display = tk.StringVar(value=self.bandwidth_mode.get())
        self.bandwidth_selector = ttk.Combobox(self.footer, textvariable=self.bandwidth_display,
            state="readonly", width=18, values=("Tối đa", "Vừa (4 MB/s)", "Nhẹ (512 KB/s)"))
        self.bandwidth_selector.pack(side="left")
        def set_bandwidth(_event):
            label = self.bandwidth_display.get()
            self.bandwidth_mode.set(self.locale.reverse.get(label, label))
            self.manager.set_bandwidth(
                {"Tối đa": "maximum", "Vừa (4 MB/s)": "medium", "Nhẹ (512 KB/s)": "light"}[self.bandwidth_mode.get()])
        self.bandwidth_selector.bind("<<ComboboxSelected>>", set_bandwidth)
        self.transfer_button = ttk.Button(self.footer, text="Tiếp tục", command=self.toggle_transfer)
        self.transfer_button.pack(side="right")
        ttk.Label(self.footer, textvariable=self.status, style="Muted.TLabel", width=48,
                  wraplength=360).pack(side="left", padx=16)
        self.queue_panel = RoundedPanel(parent, padding=14, dashed=True)
        self.queue_panel.grid(row=2, column=0, sticky="nsew")
        columns = ("name", "status", "progress", "size", "speed", "connections", "safety", "action")
        table_frame = self.queue_panel.content
        self.table = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse", height=4)
        for col, label, width in zip(columns, ("TÊN TỆP", "TRẠNG THÁI", "TIẾN ĐỘ", "ĐÃ TẢI / TỔNG", "TỐC ĐỘ", "LUỒNG", "AN TOÀN", ""),
                                     (240, 100, 65, 140, 85, 65, 130, 150)):
            self.table.heading(col, text=label)
            self.table.column(col, width=width, minwidth=65, stretch=col == "name")
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.table.yview)
        def scrolled(first, last):
            scrollbar.set(first, last)
            self.root.after_idle(self.update_safety_buttons)
        self.table.configure(yscrollcommand=scrolled)
        scrollbar.pack(side="right", fill="y")
        self.table.pack(fill="both", expand=True)
        self.empty_state = ttk.Frame(table_frame, style="Card.TFrame", padding=(16, 12))
        ttk.Label(self.empty_state, image=self.icons["download"], background=PANEL).pack(pady=(0, 12))
        ttk.Label(self.empty_state, text="Bắt đầu lượt tải đầu tiên", background=PANEL,
                  font=("Segoe UI", 16, "bold")).pack()
        ttk.Label(self.empty_state, text="Dán đường dẫn ở trên hoặc nhập danh sách từ bảng tính.",
                  background=PANEL, foreground=MUTED).pack(pady=(8, 0))
        self.empty_state.place(x=2, y=44, relwidth=1, width=-22, relheight=1, height=-46)
        self.row_safety_buttons = {}
        self.table.bind("<Configure>", lambda _: self.root.after_idle(self.update_safety_buttons))
        self.table.bind("<MouseWheel>", lambda _: self.root.after_idle(self.update_safety_buttons), add="+")
        self.table.bind("<<TreeviewSelect>>", self.show_details)
        self.table.bind("<Double-1>", lambda _: self.open_folder())
        self.table.bind("<Button-3>", self.context_menu)
        self.detail = tk.StringVar(value="Chọn một lượt tải để xem chi tiết. Bấm chuột phải để đổi link hoặc nơi lưu.")



    def dismiss_download(self):
        editor = getattr(self, "download_editor", None)
        if editor and editor.winfo_exists():
            editor.destroy()
        self.download_editor = None
        self.editor_panel.grid_remove()
        self.url_entry.focus_set()

    def prepare_download(self):
        from .download_ui import DownloadEditor
        from .links import describe_source, link_kind
        previous = getattr(self, "download_editor", None)
        if previous and previous.winfo_exists():
            if previous.original == self.url.get().strip():
                previous.focus_set()
                return
            self.dismiss_download()
        if getattr(self, "source_busy", False):
            return
        original = self.url.get().strip()
        def ready(description):
            kind, resolved = description["kind"], description["url"]
            self.source_busy = False
            if self.url.get().strip() != original:
                self.status.set(self.locale.text("Link đã thay đổi; bấm tải lại để dùng link mới."))
                return
            if kind in {"spotify", "torrent"}:
                self.add(resolved_source=(kind, resolved))
                return
            self.download_editor = DownloadEditor(self, description)
            self.download_editor.pack(fill="both", expand=True)
            self.editor_panel.grid(row=1, column=0, sticky="ew", pady=(0, 12))
            self.editor_panel.reveal()
            self.status.set(self.locale.text("Xem thông tin và bấm Tải xuống để bắt đầu."))
        def action():
            kind = link_kind(original)
            if kind in {"spotify", "torrent"}:
                ready({"original": original, "kind": kind, "url": original})
                return
            self.source_busy = True
            self.status.set(self.locale.text("Đang nhận diện nguồn tải…"))
            def worker():
                try:
                    result = describe_source(original)
                    self.events.put(lambda: ready(result))
                except Exception as error:  # noqa: BLE001 -- Restore controls after source detection.
                    self.events.put(lambda error=str(error): failed(error))
            def failed(error):
                self.source_busy = False
                self.status.set(error)
            thread = threading.Thread(target=worker, daemon=True)
            self.background_threads.append(thread)
            thread.start()
        self.guarded(action)

    def _safety(self, parent):
        ttk.Label(parent, text="Kiểm tra trước khi mở tệp", font=("Segoe UI", 18, "bold")).pack(anchor="w", pady=(8, 12))
        ttk.Label(parent, text="Tệp thực thi, tài liệu macro, ký tự đảo chiều và tệp sai SHA-256 sẽ được đổi đuôi .chuakiemtra.\n"
                  "Đây là kiểm tra sơ bộ, không phải phần mềm diệt virus. Tệp thông thường chưa được chứng nhận sạch.",
                  style="Muted.TLabel", wraplength=950).pack(anchor="w", pady=(0, 20))
        actions = ttk.Frame(parent)
        actions.pack(fill="x")
        ttk.Button(actions, text="Tính SHA-256 của tệp…", command=self.hash_file).pack(side="left", padx=(0, 10))
        if os.name == "nt":
            ttk.Button(actions, text="Quét bằng Windows Defender…", command=self.defender).pack(side="left")
        ttk.Button(actions, text="Kiểm tra ZIP / chữ ký…", command=self.inspect_safety).pack(side="left", padx=8)
        self.hash_value = tk.StringVar()
        ttk.Entry(parent, textvariable=self.hash_value).pack(fill="x", pady=20)
        self.hash_service = tk.StringVar(value="VirusTotal")
        ttk.Combobox(parent, textvariable=self.hash_service, values=("VirusTotal", "MetaDefender", "Kaspersky"),
                     state="readonly", width=22).pack(anchor="w", pady=(0, 8))
        ttk.Button(parent, text="Tra mã băm trên dịch vụ đã chọn", command=self.lookup_hash).pack(anchor="w")
        self.high_security = tk.BooleanVar(value=self.store.setting("high_security", False))
        self.auto_defender = tk.BooleanVar(value=self.store.setting("auto_defender", False))
        ttk.Checkbutton(parent, text="Tự quét bằng Windows Defender sau khi tải", variable=self.auto_defender,
                        state="normal" if os.name == "nt" else "disabled",
                        command=lambda: self.store.set_setting("auto_defender", self.auto_defender.get())).pack(
                            anchor="w", pady=10)
        ttk.Checkbutton(parent, text="An toàn cao: cách ly chương trình chưa có chữ ký Windows hợp lệ",
                        state="normal" if os.name == "nt" else "disabled",
                        variable=self.high_security, command=lambda: self.store.set_setting(
                            "high_security", self.high_security.get())).pack(anchor="w", pady=10)
        ttk.Button(parent, text="Bật/tắt bảo vệ thư mục tải của trình duyệt…", command=self.toggle_guard).pack(anchor="w", pady=10)
        ttk.Button(parent, text="Xem nhật ký cách ly thư mục…", command=self.guard_log).pack(anchor="w", pady=5)
        ttk.Label(parent, text="Tra cứu chỉ gửi mã băm trong URL tới dịch vụ đã chọn, không tải tệp lên.\n"
                  "Để khôi phục tệp cách ly: chọn lượt tải → chuột phải → Khôi phục tên gốc…",
                  style="Muted.TLabel", wraplength=950).pack(anchor="w", pady=24)

    def _browser(self, parent):
        ttk.Label(parent, text="Kết nối trình duyệt", font=("Segoe UI", 18, "bold")).pack(anchor="w", pady=12)
        ttk.Label(parent, text="Chrome / Edge / Brave / Cốc Cốc: nạp thư mục browser-extension ở chế độ nhà phát triển, "
                  "sao chép Extension ID rồi đăng ký bên dưới. Quyền tùy chọn và bộ lọc được quản lý trong popup extension.",
                  wraplength=950, style="Muted.TLabel").pack(anchor="w", pady=12)
        self.extension_id = tk.StringVar(value=self.store.setting("extension_id", ""))
        ttk.Entry(parent, textvariable=self.extension_id).pack(fill="x", pady=12)
        def register():
            import shutil
            import sys

            from .browser import register
            name = "HDMBridge.exe" if os.name == "nt" else "HDMBridge"
            if getattr(sys, "frozen", False):
                suggested = Path(sys.executable).parent/name
                if sys.platform == "darwin":
                    suggested = Path(sys.executable).parents[1]/"Helpers"/name
            else:
                installed = Path(sys.executable).parent/("hdm-bridge.exe" if os.name == "nt" else "hdm-bridge")
                suggested = installed if installed.exists() else Path(shutil.which("hdm-bridge") or str(Path.cwd()/"dist"/name))
            bridge = str(suggested) if suggested.exists() else filedialog.askopenfilename(title="Chọn native bridge")
            if bridge:
                def action():
                    result = register(self.extension_id.get().strip(), bridge, self.data_dir)
                    self.store.set_setting("extension_id", self.extension_id.get().strip())
                    self.status.set(f"Đã đăng ký: {result}")
                self.guarded(action)
        ttk.Button(parent, text="Đăng ký kết nối cho tài khoản này", command=register).pack(anchor="w", pady=12)
        ttk.Label(parent, text="Dùng menu chuột phải “Tải bằng HDM” hoặc bấm popup để hiện nút tải phía trên video. "
                  "Yêu cầu được lưu trên máy. Chuyển phiên đăng nhập từ tiện ích hiện chỉ hỗ trợ Windows, với mã hóa DPAPI. Trên macOS/Linux, chọn tệp cookie trong tùy chọn nâng cao.",
                  wraplength=950, style="Muted.TLabel").pack(anchor="w", pady=16)
        ttk.Label(parent, text="Bộ lọc hỗ trợ quy tắc mạng, chặn tab quảng cáo đã nhận diện, chọn phần tử và thống kê. "
                  "Dùng popup để quản lý quyền, ngoại lệ và luồng HLS/DASH; một số cú pháp bộ lọc chưa được hỗ trợ.", wraplength=950, style="Muted.TLabel").pack(anchor="w", pady=12)

    def _tools(self, parent):
        ttk.Label(parent, text="Tùy chọn tải", font=("Segoe UI", 18, "bold")).pack(anchor="w", pady=12)
        for label, callback in (("Nhập danh sách…", self.batch_dialog),
                                ("Tiếp quản tệp trình duyệt tải dở…", self.adopt_partial),
                                ("Torrent / magnet — chọn từng tệp…", self.torrent_dialog),
                                ("Mở lại torrent đã lưu…", self.torrent_history),
                                ("Giải nén ZIP sau khi kiểm tra…", self.extract_zip),
                                ("Xuất lịch sử tải CSV…", self.export_history),
                                ("Xuất báo cáo danh sách từng dòng…", self.export_batch_report)):
            ttk.Button(parent, text=label, command=callback).pack(anchor="w", pady=7)
        self.auto_category = tk.BooleanVar(value=self.store.setting("auto_category", False))
        ttk.Checkbutton(parent, text="Tự chia thư mục Video / Music / Images / Documents / Archives cho lượt tải mới",
                        variable=self.auto_category, command=lambda: self.store.set_setting("auto_category", self.auto_category.get())).pack(anchor="w", pady=15)
        self.auto_extract = tk.BooleanVar(value=self.store.setting("auto_extract", False))
        ttk.Checkbutton(parent, text="Tự giải nén ZIP sau khi tải và kiểm tra an toàn thành công",
                        variable=self.auto_extract, command=lambda: self.store.set_setting(
                            "auto_extract", self.auto_extract.get())).pack(anchor="w", pady=6)
        ttk.Checkbutton(parent, text="Thu xuống khay hệ thống khi đóng cửa sổ (dùng menu khay để thoát)",
                        variable=self.close_to_tray, command=lambda: self.store.set_setting("close_to_tray", self.close_to_tray.get())).pack(anchor="w", pady=6)
        ttk.Checkbutton(parent, text="Tắt máy sau khi các lượt HTTP đang chờ đều hoàn tất (đếm ngược 60 giây)",
                        state="normal" if os.name == "nt" else "disabled",
                        variable=self.shutdown_after, command=lambda: setattr(self, "power_seen_work", False)).pack(anchor="w", pady=6)
        if os.name == "nt":
            ttk.Button(parent, text="Hủy lệnh tắt máy đã hẹn", command=self.cancel_shutdown).pack(anchor="w", pady=6)

    def _about(self, parent):
        ttk.Label(parent, text=f"Hngoos Download Manager · HDM {__version__}",
                  font=("Segoe UI", 18, "bold")).pack(anchor="w", pady=12)
        for heading, body in (
            ("Tải nhanh", "Tối đa 32 kết nối, chia khối cho luồng đang rảnh; tự giảm khi nguồn giới hạn. Tạm dừng, tiếp tục, thử lại và thay link hết hạn."),
            ("Bảo vệ người dùng", "Kiểm tra nội dung, tệp giả dạng, macro, tệp nén và mã băm. Cách ly tệp rủi ro; tích hợp quét Windows Defender khi có sẵn."),
            ("Một nơi để tải", "Tự nhận link clipboard. Tải tệp trực tiếp, link lưu trữ đám mây, video, MP3/M4A và torrent từ nguồn được hỗ trợ."),
            ("Tiện ích hằng ngày", "Nhập danh sách, hẹn giờ, đổi nơi lưu, giới hạn băng thông, chạy nền và tùy chọn khởi động cùng hệ điều hành."),
            ("Giới hạn nguồn", "Số kết nối thực tùy máy chủ. Một số nguồn yêu cầu đăng nhập; nội dung DRM, gồm nhạc Spotify, không tải trực tiếp thành MP3. Kiểm tra sơ bộ không chứng nhận tệp sạch."),
        ):
            ttk.Label(parent, text=heading, font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(14, 4))
            ttk.Label(parent, text=body, style="Muted.TLabel", wraplength=800).pack(anchor="w")
        ttk.Button(parent, text="Check for update", command=self.check_update).pack(anchor="w", pady=20)

    def guarded(self, action):
        try:
            return action()
        except Exception as exc:  # noqa: BLE001 -- UI boundary must display worker/input errors.
            messagebox.showerror("HDM", str(exc), parent=self.root)

    def open_invoices(self):
        folder = self.data_dir/"invoices"
        folder.mkdir(parents=True, exist_ok=True)
        self.guarded(lambda: open_path(folder))

    def add(self, resolved_source=None):
        from .links import link_kind, resolve_source
        url = self.url.get().strip()
        if getattr(self, "source_busy", False):
            return
        def choose(kind, value):
            self.source_busy = False
            if self.url.get().strip() != url:
                self.status.set(self.locale.text("Link đã thay đổi; bấm tải lại để dùng link mới."))
                return
            if kind == "spotify":
                messagebox.showinfo("HDM", self.locale.text("Nhạc Spotify có DRM: không thể tải trực tiếp thành MP3."),
                                    parent=self.root)
                return
            if kind == "torrent":
                from .dialogs import torrent_dialog
                self.guarded(lambda: torrent_dialog(self, value, self.directory.get()))
                return
            if kind == "media" or self.download_format.get() in {"MP4", "MP3", "M4A"}:
                self.media_url.set(value)
                self.start_media({"MP3": "mp3", "M4A": "m4a"}.get(self.download_format.get(), ""))
                return
            digest = self.expected_hash.get().strip()
            algorithm = self.hash_algorithm.get().lower().replace("-", "")
            directory, name, connections = self.directory.get(), self.filename.get(), int(self.connections.get())
            mirrors = [value.strip() for value in self.mirrors.get().split("|") if value.strip()]
            def accepted(_job):
                if self.url.get().strip() == url:
                    self.url.set("")
                    self.filename.set("")
                    self.expected_hash.set("")
                    self.mirrors.set("")
                self.status.set(self.locale.text("Đã thêm lượt tải; sẽ kiểm tra trước khi hoàn tất."))
            self.background(lambda: self.manager.add(value, directory, name or filename_from_url(value),
                connections, digest if algorithm == "sha256" else "",
                expected_hashes={algorithm: digest} if digest else {}, mirrors=mirrors), accepted)
        def action():
            if resolved_source is not None:
                choose(*resolved_source)
                return
            kind = link_kind(url)
            if kind != "file":
                choose(kind, url)
                return
            self.source_busy = True
            force_file = self.download_format.get() == "Original"
            self.status.set(self.locale.text("Đang nhận diện nguồn tải…"))
            def resolve():
                try:
                    result = resolve_source(url, force_file)
                    self.events.put(lambda result=result: self.guarded(lambda: choose(*result)))
                except Exception as exc:  # noqa: BLE001 -- Worker errors must restore the input state.
                    self.events.put(lambda error=str(exc): failed(error))
            def failed(error):
                self.source_busy = False
                self.status.set(error)
            worker = threading.Thread(target=resolve, daemon=True)
            self.background_threads.append(worker)
            worker.start()
        self.guarded(action)

    def link_changed(self, *_args):
        from .links import link_kind
        try:
            kind = link_kind(self.url.get())
        except ValueError:
            kind = "file"
        hints = {"file": "Tệp gốc · tối đa 32 kết nối · kiểm tra an toàn sau tải",
                 "media": "Đã nhận link video/nhạc · chọn MP4, MP3 hoặc M4A rồi tải",
                 "torrent": "Đã nhận magnet · chọn tệp cần tải trong bước tiếp theo",
                 "spotify": "Nhạc Spotify có DRM: không thể tải trực tiếp thành MP3."}
        self.source_hint.set(self.locale.text(hints[kind]))
        if self.url.get().strip() != self.browser_session_url:
            self.video_inbox_busy = False
            self.browser_session = self.browser_session_url = ""
        self.media_format.set("")

    def check_clipboard(self):
        if getattr(self, "_closing", False):
            return
        if not self.clipboard_enabled.get() or time.monotonic()-self.clipboard_checked < 1:
            return
        self.clipboard_checked = time.monotonic()
        try:
            text = self.root.clipboard_get()
        except tk.TclError:
            return
        if text == self.clipboard_last:
            return
        self.clipboard_last = text
        from .links import clipboard_link
        link = clipboard_link(text)
        if not link:
            return
        self.clipboard_pending = link
        if not self.url.get().strip():
            self.use_clipboard_link()
        elif self.url.get().strip() != link:
            self.clipboard_notice.set(self.locale.text("Có link mới trong clipboard. Giữ nguyên link bạn đang sửa."))
            self.clipboard_frame.grid()
            self.url_panel.configure(height=110)
            self.clipboard_button.pack(side="right")

    def use_clipboard_link(self):
        if self.clipboard_pending:
            self.url.set(self.clipboard_pending)
            self.clipboard_notice.set(self.locale.text("Đã nhận link từ clipboard · bấm tải để xem lựa chọn."))
            self.clipboard_frame.grid()
            self.url_panel.configure(height=110)
            self.clipboard_button.pack_forget()

    def choose_directory(self):
        folder = filedialog.askdirectory(initialdir=self.directory.get())
        if folder:
            self.directory.set(folder)
            self.store.set_setting("download_directory", folder)

    def paste_url(self):
        def paste():
            self.clipboard_pending = self.root.clipboard_get().strip()
            self.use_clipboard_link()
        self.guarded(paste)

    def selected(self):
        selected = self.table.selection()
        return selected[0] if selected else None

    def resume(self):
        if job_id := self.selected():
            job = self.store.get(job_id)
            if job.get("kind") == "media":
                self.resume_media(job)
            else:
                self.manager.start(job_id)

    def pause(self):
        if job_id := self.selected():
            if self.store.get(job_id).get("kind") == "media":
                self.media_stop.set()
            else:
                self.manager.pause(job_id)

    def open_folder(self):
        job = self.store.get(self.selected()) if self.selected() else None
        folder = Path(job["directory"] if job else self.directory.get())
        if folder.exists():
            self.guarded(lambda: open_path(folder))

    def show_details(self, _event=None):
        if job_id := self.selected():
            job = self.store.get(job_id)
            location = job["error"] or job["output"] or f"Lưu tại: {job['directory']}"
            self.detail.set(location+" · "+self.locale.text(job.get("safety_note", "Chưa kiểm tra")))

    def context_menu(self, event):
        row = self.table.identify_row(event.y)
        if not row:
            return
        self.table.selection_set(row)
        job = self.store.get(row)
        menu = tk.Menu(self.root, tearoff=False, bg=PANEL, fg=TEXT)
        if job["state"] in {"paused", "error"}:
            menu.add_command(label="Tiếp tục tải", command=self.resume)
            if job.get("kind") != "media":
                menu.add_command(label="Thay link tải…", command=self.replace_url_dialog)
                menu.add_command(label="Đổi thư mục lưu…", command=self.relocate)
        if job["state"] in {"downloading", "queued", "verifying"}:
            menu.add_command(label="Tạm dừng", command=self.pause)
            if job.get("kind") != "media":
                menu.add_command(label="Đổi nơi lưu trong lúc tải…", command=self.relocate)
        if job["state"] in {"paused", "error", "scheduled"} and job.get("kind") != "media":
            menu.add_command(label="Hẹn giờ tải…", command=self.schedule_dialog)
        if job["state"] in {"complete", "quarantined"} and job.get("output"):
            menu.add_command(label="Kiểm tra an toàn", command=self.check_selected_safety)
        menu.add_command(label="Mở thư mục", command=self.open_folder)
        if job["sha256"]:
            menu.add_command(label="Chép SHA-256", command=lambda: self.copy(job["sha256"]))
        if job["state"] == "quarantined" and len(job.get("outputs", [])) <= 1:
            menu.add_command(label="Khôi phục tên gốc…", command=self.restore_dialog)
        menu.add_command(label="Nhật ký lượt tải…", command=self.job_log)
        for index in range((menu.index("end") or 0)+1):
            menu.entryconfigure(index, label=self.locale.text(menu.entrycget(index, "label")))
        menu.tk_popup(event.x_root, event.y_root)

    def copy(self, value):
        self.root.clipboard_clear()
        self.root.clipboard_append(value)

    def replace_url_dialog(self):
        from tkinter.simpledialog import askstring
        job_id = self.selected()
        value = askstring("Thay link", "Dán link mới. Phần cũ chỉ dùng lại khi ETag mạnh và kích thước trùng.", parent=self.root)
        if value:
            self.guarded(lambda: self.manager.replace_url(job_id, value))

    def relocate(self):
        job_id = self.selected()
        job = self.store.get(job_id)
        folder = filedialog.askdirectory(title="Đổi nơi lưu — giữ phần đã tải, tự tiếp tục")
        if not folder or Path(folder).resolve() == Path(job["directory"]).resolve():
            return
        self.background(lambda: self.manager.relocate(job_id, folder),
                        lambda _: self.status.set("Đã yêu cầu chuyển nơi lưu; lượt đang tải sẽ tiếp tục sau khi chuyển."))

    def restore_dialog(self):
        job_id = self.selected()
        job = self.store.get(job_id)
        dialog = tk.Toplevel(self.root)
        dialog.title("Khôi phục tệp cách ly")
        dialog.configure(bg=BG)
        dialog.transient(self.root)
        dialog.grab_set()
        frame = ttk.Frame(dialog, padding=24)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text=job["error"], wraplength=500).pack(anchor="w", pady=12)
        consent = tk.BooleanVar()
        ttk.Checkbutton(frame, text="Tôi hiểu rủi ro khi khôi phục tệp này", variable=consent).pack(anchor="w", pady=12)
        def restore():
            if not consent.get():
                return
            def action():
                source = Path(job["output"])
                target = source.with_name(job["filename"])
                if target.exists():
                    raise ValueError("Tên tệp gốc đã tồn tại. Hãy đổi tên hoặc di chuyển tệp đó trước.")
                source.rename(target)
                if os.name == "nt":
                    try:
                        Path(str(target) + ":Zone.Identifier").write_text("[ZoneTransfer]\nZoneId=3\n")
                    except OSError:
                        pass
                self.store.update(job_id, output=str(target), state="complete", error="Đã khôi phục theo yêu cầu người dùng")
                dialog.destroy()
            self.guarded(action)
        ttk.Button(frame, text="Khôi phục tên gốc", command=restore).pack(anchor="e", pady=12)

    def batch_dialog(self):
        from .batch_ui import open_batch
        return open_batch(self)

    def export_batch_report(self):
        from .batch_ui import export_batch_report
        path = filedialog.asksaveasfilename(title="Báo cáo danh sách", defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if path:
            self.guarded(lambda: export_batch_report(self.store, path))

    def background(self, action, success):
        def run():
            try:
                result = action()
                self.events.put(lambda result=result: success(result))
            except Exception as exc:  # noqa: BLE001 -- Route optional-library failures to the UI.
                self.events.put(lambda error=str(exc): messagebox.showerror("HDM", error, parent=self.root))
        worker = threading.Thread(target=run, daemon=True)
        self.background_threads.append(worker)
        worker.start()

    def start_media(self, audio, job=None):
        from dataclasses import asdict

        from .media import MediaOptions, download_video
        if getattr(self, "media_busy", False):
            self.status.set(self.locale.text("Đang có lượt tải video/nhạc. Hãy chờ hoặc tạm dừng lượt đó."))
            return
        url = job["url"] if job else self.media_url.get().strip()
        directory = job["directory"] if job else self.directory.get()
        options = MediaOptions(**job["media_options"]) if job else MediaOptions(
            height=int(self.media_quality.get()), audio=audio, playlist=self.media_playlist.get(),
            subtitles=self.media_subtitles.get(), cookie_file=self.media_cookie.get(),
            format_id=self.media_format.get(), connections=int(self.connections.get()),
            filename="" if self.media_playlist.get() else self.filename.get().strip())
        if url == self.browser_session_url:
            options.referrer = getattr(self, "browser_referrer", "")
        session = self.browser_session if url == self.browser_session_url else ""
        if session:
            self.browser_session = self.browser_session_url = ""
        if job:
            job_id = job["id"]
        else:
            row = self.store.create(url, directory, self.filename.get() or filename_from_url(url),
                                    int(self.connections.get()))
            job_id = row["id"]
            saved_options = asdict(options)
            saved_options["cookie_file"] = ""
            self.store.update(job_id, kind="media", media_options=saved_options)
        self.store.update(job_id, state="downloading", error="", safety_note="Chờ kiểm tra", speed=0)
        self.media_busy = True
        self.media_job_id = job_id
        self.media_stop.clear()
        if self.url.get().strip() == url:
            self.url.set("")
            self.filename.set("")
        if not options.cookie_file:
            options.cookie_file = self.media_cookie.get()
        high_security = self.store.setting("high_security", False)
        def action():
            from .media import MediaCancelled
            from .policy import TransferCancelled
            last_write = [0.0]
            safety_notes = []
            def progress(data):
                now = time.monotonic()
                if data.get("safety_note"):
                    safety_notes.append(data["safety_note"])
                    self.store.update(job_id, state="verifying", safety_note="Đang kiểm tra")
                    return
                if "downloaded_bytes" not in data and data.get("status") != "finished":
                    return
                if now-last_write[0] < 0.4 and data.get("status") != "finished":
                    return
                last_write[0] = now
                changes = {"downloaded": int(data.get("downloaded_bytes") or 0),
                           "total": int(data.get("total_bytes") or data.get("total_bytes_estimate") or 0),
                           "speed": float(data.get("speed") or 0)}
                title = (data.get("info_dict") or {}).get("title")
                if title:
                    changes["filename"] = title
                if data.get("status") == "finished":
                    changes.update(state="verifying", safety_note="Đang kiểm tra")
                else:
                    changes["state"] = "downloading"
                self.store.update(job_id, **changes)
            try:
                kwargs = {"progress": progress, "options": options, "stop": self.media_stop,
                          "high_security": high_security, "staging_root": self.data_dir/"media-staging",
                          "antivirus": self.store.setting("auto_defender", False) and os.name == "nt"}
                if session:
                    import tempfile

                    from .vault import cookie_jar, decrypt
                    with tempfile.TemporaryDirectory(prefix="hdm-session-", dir=self.data_dir) as temporary:
                        cookie_path = Path(temporary)/"cookies.txt"
                        cookie_path.write_text(cookie_jar(decrypt(session)), encoding="utf-8")
                        options.cookie_file = str(cookie_path)
                        outputs = download_video(url, directory, **kwargs)
                else:
                    outputs = download_video(url, directory, **kwargs)
                quarantined = any(path.name.endswith(".chuakiemtra") for path in outputs)
                size = sum(path.stat().st_size for path in outputs)
                self.store.update(job_id, state="quarantined" if quarantined else "complete", speed=0,
                    filename=outputs[0].name.removesuffix(".chuakiemtra") if len(outputs) == 1 else f"{len(outputs)} files · {outputs[0].name}",
                    output=str(outputs[0]), outputs=[str(path) for path in outputs], total=size, downloaded=size,
                    sha256=sha256_file(outputs[0]),
                    safety_note="Cách ly" if quarantined else (
                        "Sơ bộ + Defender" if safety_notes and all(note == "Sơ bộ + Defender" for note in safety_notes)
                        else "Sơ bộ · Defender chưa quét" if "Sơ bộ · Defender chưa quét" in safety_notes
                        else "Đã kiểm tra sơ bộ"),
                    error="Có tệp rủi ro đã được cách ly." if quarantined else "")
            except (MediaCancelled, TransferCancelled):
                self.store.update(job_id, state="paused", speed=0)
            except Exception as exc:  # noqa: BLE001 -- Persist extraction errors in the download list.
                self.store.update(job_id, state="error", speed=0, error=str(exc))
            finally:
                self.events.put(reset)
        def reset():
            self.media_busy = False
            self.video_inbox_busy = False
        worker = threading.Thread(target=action, daemon=True)
        self.background_threads.append(worker)
        worker.start()

    def resume_media(self, job):
        self.start_media("", job=job)

    def stop_media(self):
        self.media_stop.set()
        if not getattr(self, "media_busy", False):
            self.video_inbox_busy = False
            self.browser_session = ""
            self.browser_session_url = ""
            self.media_url.set("")

    def convert(self):
        from .media import convert_mp4
        source = filedialog.askopenfilename(title="Chọn video")
        if not source:
            return
        destination = filedialog.asksaveasfilename(title="Lưu MP4", defaultextension=".mp4",
                                                  initialfile=Path(source).stem + "-h264.mp4")
        if destination:
            self.status.set("Đang chuyển video sang MP4…")
            self.background(lambda: convert_mp4(source, destination),
                            lambda path: self.status.set(f"Đã chuyển xong: {path}"))

    def media_tools(self, initial=None):
        from .dialogs import media_tools
        self.guarded(lambda: media_tools(self, initial))

    def redact_pdf(self):
        from .dialogs import redact_pdf
        self.guarded(lambda: redact_pdf(self))

    def choose_cookie(self):
        path = filedialog.askopenfilename(title="Chọn cookies.txt do bạn chủ động xuất", filetypes=[("Netscape cookie file", "*.txt")])
        if path:
            self.media_cookie.set(path)
            self.media_status.set("Đã chọn tệp cookie cho lượt video tiếp theo. Không chia sẻ tệp này.")

    def inspect_video(self):
        from .media import MediaOptions, inspect_video
        options = MediaOptions(playlist=self.media_playlist.get(), cookie_file=self.media_cookie.get())
        url = self.url.get().strip() or self.media_url.get()
        def show(info):
            dialog = tk.Toplevel(self.root)
            dialog.title("HDM · "+self.locale.text("Xem định dạng"))
            dialog.geometry("760x500")
            dialog.transient(self.root)
            frame = ttk.Frame(dialog, padding=20)
            frame.pack(fill="both", expand=True)
            ttk.Label(frame, text=info.get("title", ""), wraplength=700).pack(anchor="w", pady=(0, 12))
            columns = ("id", "ext", "height", "audio", "size")
            table = ttk.Treeview(frame, columns=columns, show="headings", selectmode="browse")
            for column in columns:
                table.heading(column, text=column.upper())
                table.column(column, width=120)
            table.pack(fill="both", expand=True)
            for item in info.get("formats", []):
                table.insert("", "end", values=(item["format_id"], item["ext"], item.get("height") or "—",
                    item.get("acodec") or "—", human(item["filesize"]) if item.get("filesize") else "—"))
            ttk.Label(frame, text="Format ID chọn một luồng cụ thể; chọn Auto để tự ghép video và âm thanh.",
                      style="Muted.TLabel", wraplength=700).pack(anchor="w", pady=10)
            def choose():
                if self.url.get().strip() != url:
                    dialog.destroy()
                    return
                if selected := table.selection():
                    self.media_format.set(str(table.item(selected[0], "values")[0]))
                    dialog.destroy()
            ttk.Button(frame, text="Dùng định dạng này", command=choose).pack(side="right")
            self.locale.apply(dialog)
        self.background(lambda: inspect_video(url, options), show)

    def schedule_dialog(self):
        from datetime import datetime
        from tkinter.simpledialog import askstring
        job_id = self.selected()
        value = askstring("Hẹn giờ", "Nhập ngày giờ trên máy: YYYY-MM-DD HH:MM", parent=self.root)
        if value:
            def action():
                stamp = datetime.strptime(value.strip(), "%Y-%m-%d %H:%M").timestamp()
                if stamp <= __import__("time").time():
                    raise ValueError("Hãy chọn thời điểm trong tương lai.")
                self.store.update(job_id, scheduled_at=stamp, state="scheduled", error="")
            self.guarded(action)

    def job_log(self):
        from datetime import datetime
        job_id = self.selected()
        job = self.store.get(job_id)
        dialog = tk.Toplevel(self.root)
        dialog.title("Nhật ký — " + job["filename"])
        editor = tk.Text(dialog, width=100, height=25, bg=PANEL, fg=TEXT, wrap="word")
        editor.pack(fill="both", expand=True)
        for stamp, kind, message in self.store.events(job_id):
            editor.insert("end", f"{datetime.fromtimestamp(stamp):%Y-%m-%d %H:%M:%S} [{kind}] {message}\n")
        for algorithm, digest in job.get("checksums", {}).items():
            editor.insert("end", f"{algorithm.upper()}: {digest}\n")
        editor.configure(state="disabled")

    def export_history(self):
        import csv
        path = filedialog.asksaveasfilename(defaultextension=".csv", initialfile="hngoos-downloads.csv")
        if path:
            def action():
                with Path(path).open("w", encoding="utf-8-sig", newline="") as stream:
                    writer = csv.writer(stream)
                    writer.writerow(["filename", "state", "bytes", "sha256", "output", "error"])
                    for job in reversed(self.store.all()):
                        # Spreadsheet formula injection is possible even in error messages/names.
                        values = [job["filename"], job["state"], job["downloaded"], job["sha256"], job["output"], job["error"]]
                        writer.writerow(["'"+str(value) if str(value).startswith(("=", "+", "-", "@", "\t", "\r")) else value for value in values])
                self.status.set(f"Đã xuất lịch sử (không chứa URL có token): {path}")
            self.guarded(action)

    def resolve_cloud(self):
        from tkinter.simpledialog import askstring

        from .cloud import resolve
        url = askstring("Link đám mây", "Dán link chia sẻ tệp công khai", parent=self.root)
        if url:
            self.background(lambda: resolve(url), lambda direct: (self.url.set(direct), self.tabs.select(0)))

    def adopt_partial(self):
        from tkinter.simpledialog import askstring
        partial = filedialog.askopenfilename(title="Chọn .crdownload/.part đã dừng trong trình duyệt")
        if not partial:
            return
        url = askstring("Tiếp quản", "Dán URL tải trực tiếp. Tệp gốc được giữ lại; toàn bộ phần cũ sẽ được xác minh.", parent=self.root)
        if url:
            directory = self.directory.get()
            name = Path(partial).name
            if name.endswith((".crdownload", ".part")):
                name = name.rsplit(".", 1)[0]
            connections = int(self.connections.get())
            self.background(lambda: self.manager.adopt_partial(url, partial, directory, name, connections),
                            lambda _: (self.tabs.select(0), self.status.set("Đã tiếp quản và tiếp tục phần còn lại.")))

    def torrent_dialog(self):
        from .dialogs import torrent_dialog
        self.guarded(lambda: torrent_dialog(self))

    def extract_zip(self):
        from .extraction import extract_zip
        source = filedialog.askopenfilename(filetypes=[("ZIP", "*.zip")])
        if source:
            parent = filedialog.askdirectory(title="Thư mục cha để tạo thư mục giải nén mới")
            if parent:
                target = Path(parent)/Path(source).stem
                self.background(lambda: extract_zip(source, target),
                                lambda path: self.status.set(f"Đã giải nén: {path}"))

    def find_subtitle(self):
        from tkinter.simpledialog import askstring

        from .subtitles import download_vietnamese
        movie = filedialog.askopenfilename(title="Chọn phim để tìm phụ đề tiếng Việt")
        if not movie:
            return
        api_key = askstring("OpenSubtitles", "Nhập API key của bạn (chỉ dùng cho tác vụ này)", show="*", parent=self.root)
        if not api_key:
            return
        token = askstring("OpenSubtitles", "JWT token nếu dịch vụ yêu cầu đăng nhập (có thể để trống)", show="*", parent=self.root)
        if token is None:
            return
        self.background(lambda: download_vietnamese(movie, api_key.strip(), token.strip()),
                        lambda path: self.status.set(f"Đã tải phụ đề khớp mã phim: {path}"))

    def inspect_safety(self):
        from tkinter.simpledialog import askstring

        from .safety import authenticode, inspect_file, installer_guidance
        source = filedialog.askopenfilename(title="Kiểm tra tệp / ZIP / RAR / 7z / chữ ký Windows")
        if not source:
            return
        password = askstring("ZIP có mật khẩu?", "Nếu ZIP có mật khẩu, nhập mật khẩu (có thể để trống)", show="*", parent=self.root)
        def action():
            import json
            reasons = inspect_file(source, Path(source).name, password,
                                   high_security=self.store.setting("high_security", False))
            signature = authenticode(source)
            guidance = installer_guidance(source, Path(source).name)
            return ("Dấu hiệu:\n" + "\n".join(reasons or ["Chưa thấy dấu hiệu trong phạm vi kiểm tra; không chứng minh tệp sạch."])
                    + "\n\nChữ ký Windows:\n" + json.dumps(signature, ensure_ascii=False)
                    + ("\n\nNguồn chính thức và đối chiếu nhà phát hành:\n"+json.dumps(guidance, ensure_ascii=False) if guidance else ""))
        self.background(action, lambda report: messagebox.showinfo("Kiểm tra sơ bộ", report, parent=self.root))

    def toggle_guard(self):
        from .guard import DirectoryGuard
        if getattr(self, "guard", None):
            self.guard.close()
            self.guard = None
            self.status.set("Đã tắt theo dõi thư mục tải.")
            return
        folder = filedialog.askdirectory(title="Theo dõi tệp mới/sửa đổi; tệp rủi ro được đổi đuôi .chuakiemtra")
        if folder:
            def action():
                self.guard = DirectoryGuard(folder, self.store)
                self.status.set(f"Đang bảo vệ tệp mới trong: {folder}")
            self.guarded(action)

    def update_safety_buttons(self):
        if not hasattr(self, "row_safety_buttons") or getattr(self, "_closing", False):
            return
        visible = set()
        for row in self.table.get_children():
            box = self.table.bbox(row, "action")
            if not box:
                continue
            job = self.store.get(row)
            if job["state"] not in {"complete", "quarantined"} or not job.get("output"):
                continue
            visible.add(row)
            button = self.row_safety_buttons.get(row)
            if button is None:
                button = ttk.Button(self.table, text=self.locale.text("Kiểm tra an toàn"),
                    image=self.icons["shield"], compound="left", command=lambda row=row: self.check_selected_safety(row))
                self.row_safety_buttons[row] = button
            x, y, width, height = box
            button.place(x=x+3, y=y+3, width=max(1, width-6), height=max(1, height-6))
        for row in list(self.row_safety_buttons):
            if row not in visible:
                self.row_safety_buttons.pop(row).destroy()

    def check_selected_safety(self, job_id=None):
        from .safety_ui import SafetyDialog
        if job_id := job_id or self.selected():
            self.table.selection_set(job_id)
            job = self.store.get(job_id)
            if job["state"] in {"complete", "quarantined"} and job.get("output"):
                previous = getattr(self, "safety_dialog", None)
                if previous and previous.winfo_exists():
                    previous.lift()
                    return
                self.safety_dialog = SafetyDialog(self, job)

    def check_update(self):
        from .update_ui import UpdateDialog
        if getattr(self, "update_dialog", None) and self.update_dialog.window.winfo_exists():
            self.update_dialog.window.lift()
            return
        self.update_dialog = UpdateDialog(self)

    def update_ytdlp(self):
        from .toolchain import update_ytdlp
        if getattr(self, "media_busy", False):
            messagebox.showinfo("yt-dlp", "Đợi tác vụ video kết thúc trước khi cập nhật bộ tải.", parent=self.root)
            return
        self.background(update_ytdlp, lambda version: self.media_status.set(f"Đã xác minh và cập nhật yt-dlp {version}"))

    def guard_log(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Nhật ký bảo vệ thư mục")
        dialog.geometry("950x500")
        frame = ttk.Frame(dialog, padding=16)
        frame.pack(fill="both", expand=True)
        entries = self.store.setting("guard_log", [])
        table = ttk.Treeview(frame, columns=("file", "reason"), show="headings", selectmode="browse")
        table.heading("file", text="TỆP CÁCH LY")
        table.heading("reason", text="LÝ DO")
        table.column("file", width=450)
        table.column("reason", width=400)
        table.pack(fill="both", expand=True)
        for index, entry in enumerate(entries):
            table.insert("", "end", iid=str(index), values=(entry["quarantine"], "; ".join(entry["reasons"])))
        understand = tk.BooleanVar()
        ttk.Checkbutton(frame, text="Tôi hiểu rủi ro khi khôi phục tên gốc của tệp được chọn", variable=understand).pack(anchor="w", pady=12)
        def selected():
            if not table.selection():
                raise ValueError("Chọn một tệp cách ly trước.")
            index = int(table.selection()[0])
            entry = entries[index]
            source, target = Path(entry["quarantine"]), Path(entry["source"])
            if source.parent != target.parent or source.name != target.name+".chuakiemtra":
                raise ValueError("Đường dẫn cách ly không hợp lệ.")
            return index, source, target
        def restore():
            def action():
                if not understand.get():
                    raise ValueError("Cần tích ô hiểu rủi ro trước khi khôi phục.")
                index, source, target = selected()
                if target.exists():
                    raise ValueError("Tên gốc đã tồn tại; không ghi đè.")
                source.rename(target)
                from .files import mark_internet
                mark_internet(target)
                if getattr(self, "guard", None):
                    self.guard.accept_restored(target)
                entries[index]["restored"] = True
                self.store.set_setting("guard_log", entries)
                table.item(str(index), values=(str(target), "Đã khôi phục theo yêu cầu"))
                understand.set(False)
            self.guarded(action)
        def remove():
            def action():
                index, source, _ = selected()
                if messagebox.askyesno("Xóa tệp cách ly", f"Xóa vĩnh viễn tệp này?\n{source}", parent=dialog):
                    source.unlink()
                    entries[index]["deleted"] = True
                    self.store.set_setting("guard_log", entries)
                    table.delete(str(index))
            self.guarded(action)
        actions = ttk.Frame(frame)
        actions.pack(fill="x")
        ttk.Button(actions, text="Khôi phục tên gốc", command=restore).pack(side="left", padx=6)
        ttk.Button(actions, text="Xóa tệp cách ly…", command=remove).pack(side="right", padx=6)

    def cancel_shutdown(self):
        from .power import cancel_shutdown
        cancel_shutdown()
        self.shutdown_after.set(False)
        self.status.set("Đã hủy tắt máy tự động.")

    def torrent_history(self):
        from .dialogs import torrent_history_dialog
        torrent_history_dialog(self)

    def capture_dialog(self):
        from .batch import parse_text
        from .capture import capture_page
        dialog = tk.Toplevel(self.root)
        dialog.title("Lưu website thành PDF / ảnh")
        dialog.geometry("750x450")
        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Mỗi dòng: link | tên tệp. Trang được mở bằng phiên Edge riêng, không lấy tài khoản đang đăng nhập.", wraplength=690).pack(anchor="w", pady=10)
        editor = tk.Text(frame, bg=PANEL, fg=TEXT, insertbackground=TEXT, height=12)
        editor.pack(fill="both", expand=True)
        as_image = tk.BooleanVar()
        ttk.Checkbutton(frame, text="Lưu ảnh PNG thay vì PDF", variable=as_image).pack(anchor="w", pady=10)
        def save():
            rows = self.guarded(lambda: parse_text(editor.get("1.0", "end")))
            if not rows:
                return
            folder = filedialog.askdirectory(title="Thư mục lưu trang")
            if not folder:
                return
            image = as_image.get()
            def task():
                results = []
                for url, name in rows:
                    try:
                        target = Path(folder) / (Path(name).stem + (".png" if image else ".pdf"))
                        results.append(str(capture_page(url, target, image)))
                    except Exception as exc:  # noqa: BLE001 -- Continue a batch after one website fails.
                        results.append(f"Lỗi {name}: {exc}")
                return "\n".join(results)
            self.background(task, lambda report: messagebox.showinfo("Lưu trang", report, parent=self.root))
            dialog.destroy()
        ttk.Button(frame, text="Chọn nơi lưu và bắt đầu…", command=save).pack(anchor="e", pady=10)

    def hash_file(self):
        path = filedialog.askopenfilename(title="Tính SHA-256")
        if path:
            self.status.set("Đang tính SHA-256…")
            self.background(lambda: sha256_file(path), lambda digest: (
                self.hash_value.set(digest), self.status.set("Đã tính xong SHA-256")))

    def defender(self):
        path = filedialog.askopenfilename(title="Chọn tệp để quét với Defender")
        if path:
            self.status.set("Đang quét bằng Windows Defender…")
            self.background(lambda: scan_defender(path), lambda result: messagebox.showinfo(
                "Windows Defender", f"Mã kết quả: {result.returncode}\n{result.stdout}\n{result.stderr}", parent=self.root))

    def lookup_hash(self):
        from .safety import hash_lookup_url
        self.guarded(lambda: webbrowser.open(hash_lookup_url(self.hash_value.get(), self.hash_service.get())))

    def refresh(self):
        try:
            while True:
                self.events.get_nowait()()
        except queue.Empty:
            pass
        self.check_clipboard()
        pending = self.store.inbox()
        if pending and pending[0][1]["kind"] == "video" and (self.video_inbox_busy or getattr(self, "media_busy", False)):
            pending = []
        if pending and not getattr(self, "inbox_dialog", False):
            self.inbox_dialog = True
            request_id, item = pending[0]
            try:
                self.store.acknowledge(request_id, "reviewing")
                if item["kind"] == "invoice":
                    from .invoices import save_invoice
                    destination = self.data_dir/"invoices"
                    def archived(path, request_id=request_id):
                        self.store.acknowledge(request_id)
                        self.status.set(f"Đã lưu phiếu: {path}")
                    self.background(lambda item=item: save_invoice(item["url"], item["html"], item["order_id"], destination),
                        archived)
                elif item["kind"] == "video":
                    self.video_inbox_busy = True
                    self.browser_session = item.get("session_dpapi", "")
                    self.browser_session_url = item["url"]
                    self.browser_referrer = item.get("referrer", "")
                    self.media_url.set(item["url"])
                    self.url.set(item["url"])
                    self.status.set("Đã nhận link video từ trình duyệt; chọn chất lượng rồi tải.")
                    self.store.acknowledge(request_id)
                else:
                    output = filedialog.asksaveasfilename(title="HDM — Lưu tệp từ trình duyệt",
                        initialdir=self.directory.get(), initialfile=item["filename"] or filename_from_url(item["url"]))
                    if output:
                        self.manager.add(item["url"], Path(output).parent, Path(output).name, int(self.connections.get()))
                    self.store.acknowledge(request_id, "accepted" if output else "cancelled")
            finally:
                self.inbox_dialog = False
        jobs = self.store.all()
        self.speed.set(human(sum(job.get("speed", 0) for job in jobs))+"/s")
        if jobs:
            self.empty_state.place_forget()
        elif not self.empty_state.winfo_manager():
            self.empty_state.place(x=2, y=44, relwidth=1, width=-22, relheight=1, height=-46)
        chosen = self.table.selection()
        current = next((job for job in jobs if chosen and job["id"] == chosen[0]), None)
        active = bool(current and current["state"] in {"queued", "downloading", "verifying"})
        self.transfer_button.configure(text=self.locale.text("Tạm dừng" if active else "Tiếp tục"))
        self.transfer_button.configure(state="normal" if current and current["state"] in {
            "queued", "downloading", "verifying", "paused", "error", "scheduled"} else "disabled")
        self.playback_icon.set_running(active)
        from .power import prevent_sleep
        running = bool(self.manager.active) or getattr(self, "media_busy", False) or any(
            not job.closed and not job.completed for job in getattr(self, "torrent_jobs", []))
        if running != self.sleep_prevented:
            prevent_sleep(running)
            self.sleep_prevented = running
        if self.shutdown_after.get():
            if self.manager.active:
                self.power_seen_work = True
            if (self.power_seen_work and jobs and not running
                    and all(job["state"] in {"complete", "quarantined"} for job in jobs)):
                self.shutdown_after.set(False)
                from .power import shutdown_in
                self.guarded(lambda: shutdown_in(60))
                self.status.set("Đã hẹn tắt máy sau 60 giây. Bấm Hủy trong Công cụ để hủy.")
        for job in jobs:
            progress = f"{min(100, job['downloaded']/job['total']*100):.0f}%" if job["total"] else "—"
            values = (job["filename"], self.locale.text(STATES.get(job["state"], job["state"])), progress,
                      f"{human(job['downloaded'])} / {human(job['total']) if job['total'] else '?'}",
                      f"{human(job['speed'])}/s" if job["speed"] else "—",
                      "—" if job.get("kind") == "media" else f"{job.get('active_connections', 0)}/{job['connections']}",
                      self.locale.text(job.get("safety_note", "Chưa kiểm tra")), "")
            if self.last_jobs.get(job["id"]) != values:
                if self.table.exists(job["id"]):
                    self.table.item(job["id"], values=values)
                else:
                    self.table.insert("", 0, iid=job["id"], values=values)
                self.last_jobs[job["id"]] = values
        self.update_safety_buttons()
        self.show_details()
        self.refresh_id = self.root.after(500, self.refresh)

    def toggle_transfer(self):
        def action():
            job_id = self.selected()
            if self.store.get(job_id)["state"] in {"queued", "downloading", "verifying"}:
                self.pause()
            else:
                self.resume()
        self.guarded(action)

    def close(self):
        self.root.after_cancel(self.refresh_id)
        self._closing = True
        if getattr(self, "update_dialog", None):
            self.update_dialog.close()
        self.media_stop.set()
        for stop in getattr(self, "processing_stops", []):
            stop.set()
        for job in getattr(self, "torrent_jobs", []):
            job.close()
        if getattr(self, "guard", None):
            self.guard.close()
        if getattr(self, "tray", None):
            self.tray.close()
        from .power import prevent_sleep
        prevent_sleep(False)
        self.manager.close()
        self.root.destroy()

    def request_close(self):
        if self.close_to_tray.get():
            try:
                if not getattr(self, "tray", None):
                    from .tray import Tray
                    self.tray = Tray(self)
                self.tray.hide()
                return
            except (ImportError, RuntimeError) as exc:
                messagebox.showerror("Khay hệ thống", str(exc), parent=self.root)
        self.close()


def main():
    parser = argparse.ArgumentParser(description="hngoos-download-manager")
    parser.add_argument("--smoke-test", action="store_true", help="Build UI then close")
    parser.add_argument("--self-test-report", type=Path, help="Run offline packaged feature checks; write JSON")
    parser.add_argument("--data-dir", type=Path, help="Override local metadata directory")
    parser.add_argument("--native-messaging", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.native_messaging:
        from .bridge import main as bridge_main
        bridge_main()
        return
    if args.self_test_report:
        from .diagnostics import run_diagnostics
        raise SystemExit(run_diagnostics(args.self_test_report))
    if os.name == "nt":
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("hngoos.HDM")
    root = tk.Tk()
    data_dir = args.data_dir or data_directory()
    try:
        instance = InstanceLock(data_dir / "instance.lock")
    except RuntimeError as exc:
        root.withdraw()
        messagebox.showinfo("HDM", str(exc), parent=root)
        root.destroy()
        return
    app = App(root, data_dir)
    if args.smoke_test:
        root.after(1500, app.close)
    try:
        root.mainloop()
    finally:
        # Keep the process lock until all file workers have stopped.
        app.manager.close()
        app.manager.pool.shutdown(wait=True)
        instance.close()


if __name__ == "__main__":
    main()
