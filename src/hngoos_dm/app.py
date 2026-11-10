"""Native Windows and macOS desktop interface built with Tkinter."""

import argparse
import os
import queue
import sys
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
from .rounded import RoundedButton
from .safety import filename_from_url, scan_defender, sha256_file
from .store import Store
from .ui_preferences import buffered_presentation

BG, PANEL, TEXT, MUTED, BLUE = "#121212", "#121212", "#eeeeee", "#a6a6a6", "#67d1f4"
STATES = {"queued": "Đang chờ", "downloading": "Đang tải", "paused": "Tạm dừng",
          "assembling": "Đang hoàn tất",
          "verifying": "Đang xác minh", "complete": "Hoàn tất", "quarantined": "Cách ly", "error": "Lỗi",
          "scheduled": "Đã hẹn giờ"}


def human(size):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


class App:
    def __init__(self, root, data_dir=None, *, register_startup=False):
        self.root = root
        self.root.title("Hngoos Download Manager")
        self.root.geometry("1280x800")
        self.root.minsize(800, 500)
        self.root.configure(bg=BG)
        data_dir = data_dir or data_directory()
        self.store = Store(data_dir / "downloads.sqlite3")
        from .preferences import initialize
        self.register_startup = register_startup
        initialize(self.store, register_startup=register_startup)
        self.data_dir = data_dir
        from .ui_preferences import PALETTES, Localizer
        self.theme = self.store.setting("theme", "dark")
        if self.theme not in PALETTES:
            self.theme = "dark"
        self.locale = Localizer(root, self.store.setting("language", "en"))
        self.manager = DownloadManager(self.store)
        self.manager.hosts.default_limit = 32
        self.store.set_setting("transfer_mode", "maximum")
        self.manager.set_bandwidth("maximum")
        self.events = queue.Queue()
        self.background_threads = []
        from .automatic_updates import AutomaticUpdates, AutomaticVideoUpdates
        self.automatic_updates = AutomaticUpdates(self)
        self.automatic_video_updates = AutomaticVideoUpdates(self)
        self.history_maintained_at = 0
        self.last_jobs = {}
        self.pending_removals = set()
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
        self.media_bitrate = tk.StringVar(value="320")
        self.media_playlist = tk.BooleanVar()
        self.media_subtitles = tk.BooleanVar()
        self.media_cookie = tk.StringVar()
        self.media_format = tk.StringVar()
        self.download_format = tk.StringVar(value="Auto")
        self.media_status = tk.StringVar()
        self.browser_session = ""
        self.browser_session_url = ""
        self.video_inbox_busy = False
        self.power_seen_work = False
        self.sleep_prevented = False
        self.status = tk.StringVar(value="Sẵn sàng · dữ liệu tải được lưu trên máy của bạn")
        self._styles()
        from .icons import decorate_buttons, load_brand_icons, load_icons
        self.brand_icons = load_brand_icons(root)
        self.icons = load_icons(root)
        self.primary_icons = self.icons
        self._layout()
        decorate_buttons(root, self.icons)
        self.apply_preferences()
        self.resize_source_card()
        from .preferences_surface import PreferencesSurface
        self.presentation_surface = PreferencesSurface(self)
        self.root.bind_all("<Map>", self._presentation_mapped, add="+")
        self.root.protocol("WM_DELETE_WINDOW", self.request_close)
        self.refresh_id = self.root.after(200, self.refresh)
        if register_startup:
            from .browser import connect_bundled_extension
            self.background(lambda: connect_bundled_extension(self.data_dir),
                            lambda _identity: self.store.set_setting("browser_connection_error", ""),
                            lambda error: self.store.set_setting("browser_connection_error", error))

    def _styles(self):
        self._scaled_font_metrics = None
        style = ttk.Style(self.root)
        if style.theme_use() != "clam":
            style.theme_use("clam")
        light = self.theme == "light"
        control = "#ececec" if light else "#272727"
        hover = "#e4e4e4" if light else "#333333"
        border = "#d0d0d0" if light else "#3a3a3a"
        selected = "#e0e0e0" if light else "#383838"
        primary = BLUE
        primary_text = "white" if light else "#10252f"
        style.configure(".", background=BG, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("TFrame", background=BG)
        style.configure("Card.TFrame", background=PANEL)
        style.configure("TLabel", background=BG, foreground=TEXT)
        style.configure("Muted.TLabel", foreground=MUTED)
        style.configure("Card.TLabel", background=PANEL, foreground=TEXT)
        style.configure("Source.Card.TLabel", background=PANEL, foreground=TEXT, font=("Segoe UI", 12))
        style.configure("Title.TLabel", font=("Segoe UI", 26, "bold"))
        style.configure("TButton", padding=(12, 8), background=control, foreground=TEXT,
                        borderwidth=0, bordercolor=BG, lightcolor=BG, darkcolor=BG)
        style.map("TButton", background=[("active", hover)], foreground=[("disabled", MUTED)])
        style.configure("Primary.TButton", background=primary, foreground=primary_text)
        style.map("Primary.TButton", background=[("active", "#076581" if light else "#8bdef9")],
                  foreground=[("disabled", MUTED), ("!disabled", primary_text)])
        style.configure("Nav.TButton", background=BG, foreground=MUTED, anchor="w", padding=(12, 14))
        style.map("Nav.TButton", background=[("active", control)], foreground=[("active", TEXT)])
        style.configure("ActiveNav.TButton", background="#e2e2e2" if light else "#303030",
                        foreground=BLUE if light else "#b6eaff", anchor="w", padding=(12, 14))
        style.map("ActiveNav.TButton", background=[("active", "#e2e2e2" if light else "#303030")],
                  foreground=[("active", BLUE if light else "#b6eaff")])
        style.configure("Rounded.TEntry", borderwidth=0, padding=0, background=PANEL, fieldbackground=PANEL,
                        foreground=TEXT, insertcolor=TEXT, bordercolor=PANEL, lightcolor=PANEL, darkcolor=PANEL)
        style.layout("Rounded.TEntry", [("Entry.padding", {"sticky": "nswe", "children": [
            ("Entry.textarea", {"sticky": "nswe"})]})])
        style.map("Rounded.TEntry", background=[("readonly", PANEL), ("disabled", PANEL)],
                  fieldbackground=[("readonly", PANEL), ("disabled", PANEL)],
                  foreground=[("readonly", TEXT), ("disabled", MUTED)])
        style.configure("Rounded.TCombobox", borderwidth=0, padding=0, bordercolor=PANEL, lightcolor=PANEL, darkcolor=PANEL)
        style.map("Rounded.TCombobox", fieldbackground=[("readonly", PANEL)], foreground=[("readonly", TEXT)])
        style.configure("TEntry", fieldbackground=PANEL, foreground=TEXT, insertcolor=TEXT,
                        padding=8, bordercolor=border, lightcolor=border, darkcolor=border)
        style.map("TEntry", selectbackground=[("!disabled", selected)], selectforeground=[("!disabled", TEXT)])
        style.configure("TCombobox", fieldbackground=PANEL, foreground=TEXT, padding=8,
                        background=control, arrowcolor=MUTED, bordercolor=border, lightcolor=border, darkcolor=border)
        style.map("TCombobox", fieldbackground=[("readonly", PANEL)], foreground=[("readonly", TEXT)])
        style.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=TEXT,
                        rowheight=38, borderwidth=0, bordercolor=PANEL, lightcolor=PANEL, darkcolor=PANEL)
        style.configure("Treeview.Heading", background=PANEL, foreground=MUTED, padding=(8, 10), borderwidth=0,
                        bordercolor=PANEL, lightcolor=PANEL, darkcolor=PANEL, relief="flat")
        style.map("Treeview.Heading", background=[("pressed", PANEL), ("active", PANEL)],
                  foreground=[("pressed", MUTED), ("active", MUTED)])
        style.map("Treeview", background=[("selected", selected)], foreground=[("selected", TEXT)])
        style.configure("TCheckbutton", background=BG, foreground=TEXT, indicatorbackground=PANEL)
        style.map("TCheckbutton", background=[("active", BG)],
                  foreground=[("disabled", MUTED), ("active", TEXT)],
                  indicatorbackground=[("selected", primary), ("!selected", PANEL)])
        style.configure("Card.TCheckbutton", background=PANEL, foreground=TEXT)
        style.map("Card.TCheckbutton", background=[("active", PANEL), ("!active", PANEL)],
                  foreground=[("active", TEXT), ("!active", TEXT)])
        from .ui_preferences import apply_checkbox_style
        apply_checkbox_style(self.root, style, self.theme)
        style.configure("TRadiobutton", background=BG, foreground=TEXT)
        style.map("TRadiobutton", background=[("active", BG)], foreground=[("active", TEXT)])
        style.configure("Horizontal.TProgressbar", troughcolor=control, background=BLUE,
                        bordercolor=control, lightcolor=BLUE, darkcolor=BLUE)
        style.configure("TNotebook", borderwidth=0)
        style.layout("HDM.TNotebook.Tab", [])
        style.configure("HDM.TNotebook", borderwidth=0, tabmargins=0, bordercolor=BG, lightcolor=BG, darkcolor=BG)
        style.configure("Vertical.TScrollbar", background="#3a3a3a", troughcolor=PANEL,
                        arrowcolor=MUTED, bordercolor=PANEL, lightcolor=PANEL, darkcolor=PANEL)
        style.configure("TNotebook.Tab", background=PANEL, foreground=MUTED, padding=(20, 12))
        style.map("TNotebook.Tab", background=[("selected", "#e2e2e2" if light else "#303030")],
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
        # The download table is a journal; legacy cleanup settings must not erase it.
        for key in ("remove_missing", "remove_completed"):
            if self.store.setting(key) is not False:
                self.store.set_setting(key, False)
        shell = self.shell = ttk.Frame(self.root, padding=(8, 12, 8, 18))
        shell.pack(fill="both", expand=True)
        header = self.header = ttk.Frame(shell)
        header.pack(fill="x", padx=18, pady=(0, 14))
        header.columnconfigure(1, weight=1)
        self.header_left = ttk.Frame(header, height=272)
        self.header_left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.header_left.grid_propagate(False)
        self.brand_label = ttk.Label(self.header_left, image=self.brand_icons[0], cursor="hand2", takefocus=True, padding=0, borderwidth=0)
        self.brand_label.grid(row=0, column=0, sticky="nw")
        self.brand_label.bind("<Button-1>", self.open_information)
        self.brand_label.bind("<Return>", self.open_information)
        self.brand_label.bind("<space>", self.open_information)
        self.root.bind("<F1>", self.open_information)
        self.view_host = ttk.Frame(shell)
        self.view_host.pack(fill="both", expand=True)
        self.page_stack = []
        self.tabs = ttk.Notebook(self.view_host, style="HDM.TNotebook")
        self.tabs.pack(fill="both", expand=True)
        downloads = ttk.Frame(self.tabs)
        self.tabs.add(downloads, text="Tải xuống")
        self._downloads(downloads)
        self.close_to_tray = tk.BooleanVar(value=self.store.setting("close_to_tray", True))
        self.shutdown_after = tk.BooleanVar()

    def open_information(self, event=None):
        if event is not None:
            # Drain a burst of input before navigating, and ignore events arriving
            # while the new page is being laid out. Never replay a click backlog.
            if not getattr(self, "navigation_timer", None):
                def navigate():
                    self.open_information()
                    self.navigation_timer = self.root.after_idle(finished)
                def finished():
                    self.navigation_timer = None
                self.navigation_timer = self.root.after_idle(navigate)
            return "break"
        card = getattr(self, "modal_card", None)
        if card and card.winfo_exists():
            card.dismiss()
        if self.page_stack:
            self.page_stack[0].hide()
        else:
            self.open_preferences()

    @buffered_presentation
    def open_preferences(self):
        from .information_ui import preferences_page
        return preferences_page(self)

    def open_about(self):
        from .information_ui import CenteredCard
        previous = getattr(self, "about_dialog", None)
        if previous and previous.winfo_exists():
            previous.lift()
            return previous
        dialog = self.about_dialog = CenteredCard(self, height=250)
        self._about(dialog.body)
        self.apply_preferences()
        return dialog

    def open_bug_report(self):
        return webbrowser.open("https://github.com/hngoos/hngoos-download-manager/issues/new?labels=bug")

    def _download_settings(self, parent):
        from .rounded import ChoiceRow
        self.preference_flags = {}
        self.preference_rows = {}
        def row(label):
            frame = ttk.Frame(parent)
            frame.pack(fill="x", pady=5)
            caption = ttk.Label(frame, text=label, width=12, anchor="w", font=("Segoe UI", 12))
            caption.pack(side="left", padx=(0, 12))
            content = ttk.Frame(frame)
            content.pack(side="left", fill="x", expand=True)
            self.preference_rows[label] = (caption, content)
            return content
        theme_value = tk.StringVar(value=self.theme)
        self.preference_theme = ChoiceRow(row("Giao diện"), theme_value, [("Sáng", "light"), ("Tối", "dark")],
            lambda: self.set_preference("theme", theme_value.get()), self)
        self.preference_theme.pack(fill="x")
        language_value = tk.StringVar(value=self.locale.language)
        self.preference_language = ChoiceRow(row("Ngôn ngữ"), language_value, [("Tiếng Việt", "vi"), ("Tiếng Anh", "en")],
            lambda: self.set_preference("language", language_value.get()), self)
        self.preference_language.pack(fill="x")

    def _transfer_settings(self, parent):
        from .information_ui import build_browser_capture_settings
        from .preferences import build_automation_settings
        from .rounded import RoundedEntry
        ttk.Label(parent, text="Tải xuống", font=("Segoe UI", 16, "bold")).pack(anchor="w", pady=(0, 10))
        destination = ttk.Frame(parent)
        destination.pack(fill="x", pady=(0, 8))
        ttk.Label(destination, text="Lưu tại:", font=("Segoe UI", 12)).pack(side="left", padx=(0, 8))
        self.preference_directory = RoundedEntry(destination, textvariable=self.directory, font=("Segoe UI", 12),
            action_image=self.icons["folder"], action_command=self.choose_directory)
        self.preference_directory.pack(side="left", fill="x", expand=True)
        self.preference_directory.bind("<Return>", lambda _: self.save_directory())
        self.preference_directory.bind("<FocusOut>", lambda _: self.save_directory(), add="+")
        build_automation_settings(self, parent, "download")
        build_browser_capture_settings(self, parent)
        self._safety(parent)
        self.auto_category = tk.BooleanVar(value=self.store.setting("auto_category", False))
        ttk.Checkbutton(parent, text="Tự chia thư mục theo loại tệp", variable=self.auto_category,
            command=lambda: self.store.set_setting("auto_category", self.auto_category.get())).pack(anchor="w", pady=4)
        self.auto_extract = tk.BooleanVar(value=self.store.setting("auto_extract", False))
        ttk.Checkbutton(parent, text="Tự giải nén ZIP sau khi tải và kiểm tra an toàn thành công",
            variable=self.auto_extract, command=lambda: self.store.set_setting("auto_extract", self.auto_extract.get())).pack(anchor="w", pady=4)

    def _system_settings(self, parent):
        ttk.Label(parent, text="Hệ thống", font=("Segoe UI", 16, "bold")).pack(anchor="w", pady=(0, 10))
        startup = tk.BooleanVar(value=self.store.setting("startup_enabled", True))
        def toggle_startup():
            from .startup import set_enabled
            try:
                set_enabled(startup.get())
                self.store.set_setting("startup_enabled", startup.get())
            except (OSError, ValueError) as exc:
                startup.set(not startup.get())
                messagebox.showerror(self.locale.text("HDM"), self.locale.text(str(exc)), parent=self.root)
        ttk.Checkbutton(parent, text="Khởi động cùng hệ điều hành", variable=startup,
                        command=toggle_startup).pack(anchor="w", pady=4)
        self.startup_enabled = startup
        from .preferences import build_automation_settings
        build_automation_settings(self, parent, "system")
        ttk.Checkbutton(parent, text="Thu xuống khay hệ thống khi đóng cửa sổ",
            variable=self.close_to_tray, command=lambda: self.store.set_setting("close_to_tray", self.close_to_tray.get())).pack(anchor="w", pady=4)
        ttk.Checkbutton(parent, text="Tắt máy sau khi tải xong", state="normal" if os.name == "nt" else "disabled",
            variable=self.shutdown_after, command=lambda: setattr(self, "power_seen_work", False)).pack(anchor="w", pady=4)
        actions = ttk.Frame(parent)
        actions.pack(anchor="w", pady=12)
        self.preference_report_button = RoundedButton(actions, text="Báo lỗi", command=self.open_bug_report, width=140)
        self.preference_report_button.pack(side="left", padx=(0, 10))
        self.preference_update_button = RoundedButton(actions, text="Kiểm tra cập nhật", command=self.check_update, width=180)
        self.preference_update_button.pack(side="left", padx=(0, 10))
        self.preference_reset_button = RoundedButton(actions, text="Đặt lại mặc định", command=self.reset_preferences, width=180)
        self.preference_reset_button.pack(side="left")

    def reset_preferences(self):
        if not messagebox.askyesno(self.locale.text("Khôi phục cài đặt mặc định"),
                self.locale.text("Đặt lại thiết lập HDM? Tệp, lịch sử tải và khóa dịch vụ được giữ nguyên."), parent=self.root):
            return
        from .preferences import reset
        values = self.guarded(lambda: reset(self.store, register_startup=self.register_startup))
        if values is None:
            return
        self.theme = values["theme"]
        self.locale.language = values["language"]
        self.directory.set(values["download_directory"])
        self.close_to_tray.set(values["close_to_tray"])
        self.shutdown_after.set(False)
        self.set_transfer_mode("maximum")
        self.automatic_updates.ready = None
        page = getattr(self, "preferences_dialog", None)
        if page and page.winfo_exists():
            page.destroy()
            self.open_preferences()
        self.apply_preferences()

    @buffered_presentation
    def set_preference(self, key, value):
        self.store.set_setting(key, value)
        if key == "theme":
            self.theme = value
        else:
            self.locale.language = value
        self.apply_preferences()

    def schedule_redraw(self):
        if getattr(self, "_closing", False) or getattr(self, "redraw_timer", None):
            return
        def redraw():
            self.redraw_timer = None
            from .ui_preferences import redraw_window
            redraw_window(self.root)
            surface = getattr(self, "presentation_surface", None)
            if surface:
                surface.show()
        def layout():
            if not self.page_stack:
                self.resize_queue_columns()
            # Let Tk commit geometry for the heading and cell overlays before
            # invalidating the corresponding Windows child surfaces.
            self.redraw_timer = self.root.after_idle(redraw)
        self.redraw_timer = self.root.after_idle(layout)

    def _presentation_mapped(self, event):
        if getattr(event.widget, "_hdm_presentation", None) == (self.theme, self.locale.language):
            return
        if not getattr(self, "_presentation_pending", False):
            self._presentation_pending = True
            self.presentation_timer = self.root.after_idle(self.apply_preferences)

    @buffered_presentation
    def apply_preferences(self):
        if getattr(self, "presentation_timer", None):
            self.root.after_cancel(self.presentation_timer)
            self.presentation_timer = None
        self.root.title(self.locale.text("Hngoos Download Manager"))
        from .rounded import RoundedButton, RoundedField, RoundedPanel, RoundedScrollbar
        from .ui_preferences import DARK_COLORS, PALETTES, apply_window_theme, recolor
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
        apply_window_theme(self.root, self.theme)
        self.fit_icons()
        self.locale.apply()
        for attribute, value in (("preference_theme", self.theme), ("preference_language", self.locale.language)):
            choices = getattr(self, attribute, None)
            if choices and choices.winfo_exists():
                choices.variable.set(value)
        page = getattr(self, "preferences_dialog", None)
        if page and page.winfo_exists() and hasattr(page, "fit"):
            page._fit_signature = None
            page.fit()
        for column, icon in {"name": "grid", "status": "progress", "speed": "transfer", "properties": "alert"}.items():
            self.heading_icons[column].configure(image=self.icons[icon])
        def wheel(event):
            ancestor = event.widget
            while ancestor is not None:
                if ancestor == self.queue_panel:
                    step = (-1 if getattr(event, "num", None) == 4 else 1) if not event.delta else -int(event.delta/120)
                    self.table.yview_scroll(step, "units")
                    self.root.after_idle(self.update_safety_buttons)
                    break
                ancestor = getattr(ancestor, "master", None)
            return "break"
        for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.root.bind_class("HDM.NoScroll", sequence, wheel)
        def present(parent):
            parent._hdm_presentation = (self.theme, self.locale.language)
            for widget in parent.winfo_children():
                tags = widget.bindtags()
                if "HDM.NoScroll" not in tags and not getattr(widget, "_hdm_shared_surface", False):
                    widget.bindtags(("HDM.NoScroll",)+tags)
                if isinstance(widget, tk.Toplevel):
                    apply_window_theme(widget, self.theme)
                if isinstance(widget, (RoundedPanel, RoundedButton, RoundedField, RoundedScrollbar)):
                    widget.set_presentation(self.theme, self.locale.text)
                present(widget)
        present(self.root)
        self.last_jobs.clear()
        self._presentation_pending = False
        self.update_safety_buttons()
        self.schedule_redraw()
        self.schedule_source_resize()

    def scrollable(self, parent, centered=False):
        from .rounded import RoundedScrollbar
        card = str(parent.cget("style")) == "Card.TFrame" if isinstance(parent, ttk.Frame) else False
        canvas = tk.Canvas(parent, bg=PANEL if card else BG, highlightthickness=0, height=1, width=1)
        scrollbar = RoundedScrollbar(parent, command=canvas.yview)
        canvas.pack(fill="both", expand=True)
        canvas.configure(yscrollcommand=scrollbar.set)
        content = ttk.Frame(canvas, style="Card.TFrame" if card else "TFrame")
        content.scrollbar = scrollbar
        if centered:
            # Download cards never scroll. Keep their layout model mapped behind
            # the scene; Canvas window items may unmap when obscured.
            content.place(x=0, y=0, relwidth=1)
        else:
            window = canvas.create_window(0, 0, window=content, anchor="nw")
        def arrange(_event=None):
            if centered:
                height = content.winfo_reqheight()
                content.place_configure(y=max(0, (canvas.winfo_height()-height)//2))
                canvas.configure(scrollregion=(0, 0, canvas.winfo_width(), max(height, canvas.winfo_height())))
            else:
                canvas.itemconfigure(window, width=canvas.winfo_width())
                canvas.configure(scrollregion=canvas.bbox("all"))
        content.bind("<Configure>", arrange)
        canvas.bind("<Configure>", arrange)
        return content

    def _downloads(self, parent):
        from .rounded import RoundedButton, RoundedPanel, RoundedScrollbar, UnderlinedEntry
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        # The upper form shares the window background; only the journal is framed.
        self.empty_panel = ttk.Frame(self.header, height=208, style="Card.TFrame")
        self.empty_panel.grid(row=0, column=1, sticky="nsew", padx=(12, 0))
        self.empty_panel.grid_propagate(False)
        self.empty_panel.columnconfigure(0, weight=1)
        self.empty_panel.rowconfigure(0, weight=1)
        self.input_content = ttk.Frame(self.empty_panel, style="Card.TFrame")
        self.input_content.grid(row=0, column=0, sticky="nsew")
        self.input_content.columnconfigure(0, weight=1)
        self.input_content.columnconfigure(1, minsize=130)
        form = self.url_form = ttk.Frame(self.input_content, style="Card.TFrame")
        form.grid(row=0, column=0, sticky="ew", padx=(0, 20))
        form.columnconfigure(1, weight=1)
        ttk.Label(form, text="URL:", background=PANEL, font=("Segoe UI", 14),
                  foreground=TEXT).grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.url_entry = UnderlinedEntry(form, textvariable=self.url, font=("Segoe UI", 14), fill_width=True)
        self.url_entry.configure(height=44)
        self.url_entry.grid(row=0, column=1, sticky="ew")
        self.url_entry.bind("<Return>", lambda _event: self.submit_download())
        self.url_entry.bind("<<Paste>>", self.manual_paste, add="+")
        self.download_button = RoundedButton(self.input_content, text="Tải xuống", flat=True,
            command=self.submit_download, width=130, height=44)
        self.download_button.label_font.configure(size=14)
        self.download_button.grid(row=0, column=1, sticky="new")
        self.cancel_button = RoundedButton(form, text="", image=self.icons["close"], flat=True,
            command=self.cancel_download, width=36, height=44)
        self.cancel_button.grid(row=0, column=2, sticky="e", padx=(6, 0))
        self.url_panel = ttk.Frame(self.input_content, style="Card.TFrame")
        self.url_panel.grid(row=1, column=0, sticky="nsew", padx=(0, 20), pady=(4, 0))
        self.source_content = ttk.Frame(self.url_panel, style="Card.TFrame")
        self.source_content.pack(fill="both", expand=True)
        self.source_message = tk.StringVar()
        self.source_message_label = ttk.Label(self.input_content, textvariable=self.source_message,
                                              style="Card.TLabel", foreground=MUTED)
        self.source_hint = tk.StringVar(value="Tệp gốc · tối đa 32 kết nối · kiểm tra an toàn sau tải")
        self.url.trace_add("write", self.link_changed)
        self.header.bind("<Configure>", lambda _: self.schedule_source_resize(), add="+")
        self.shell.bind("<Configure>", lambda _: self.schedule_source_resize(), add="+")
        self.footer = ttk.Frame(parent)
        from .toolbar import SpeedMeter
        self.speed_meter = SpeedMeter(self, self.footer)
        self.speed_meter.pack(side="left")
        self.update_notice = RoundedButton(self.header_left, text="HDM có bản cập nhật mới",
            command=self.check_update, width=200, height=30)
        self.queue_panel = RoundedPanel(parent, padding=14)
        self.queue_panel.grid(row=0, column=0, sticky="nsew", padx=16)
        columns = ("name", "status", "speed", "properties")
        table_frame = self.queue_panel.content
        self.table = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="none", height=4)
        self.column_proportions = (.4, .3, .125, .175)
        for col, label, width in zip(columns, ("Tệp", "Trạng thái", "Tốc độ", "Xóa"),
                                     (350, 260, 110, 160)):
            anchor = "w" if col == "name" else "center"
            self.table.heading(col, text="", anchor=anchor)
            self.table.column(col, width=width, minwidth=65, stretch=False, anchor=anchor)
        scrollbar = RoundedScrollbar(table_frame, command=self.table.yview)
        def scrolled(first, last):
            scrollbar.set(first, last)
            self.root.after_idle(self.update_safety_buttons)
        self.table.configure(yscrollcommand=scrolled)
        self.journal_scrollbar = scrollbar
        scrollbar.pack(side="right", fill="y")
        self.table.pack(fill="both", expand=True)
        self.heading_icons = {column: ttk.Label(self.table, image=self.icons[icon], style="Card.TLabel")
                              for column, icon in {"name": "grid", "status": "progress", "speed": "transfer", "properties": "alert"}.items()}
        self.heading_separators = [ttk.Label(self.table, text="|", style="Card.TLabel", foreground=MUTED)
                                   for _ in columns[:-1]]
        for separator in self.heading_separators:
            separator.configure(cursor="arrow", width=2, anchor="center")
        self.table.bind("<Configure>", lambda _: self.root.after_idle(self.resize_queue_columns), add="+")
        self.row_safety_buttons = {}
        self.row_more_buttons = {}
        self.row_remove_buttons = {}
        self.row_cell_labels = {}
        self.row_separators = {}
        self.table.bind("<Configure>", lambda _: self.root.after_idle(self.update_safety_buttons), add="+")
        self.table.bind("<<TreeviewSelect>>", lambda event: (self.show_details(event), self.update_safety_buttons()))
        self.table.bind("<Button-1>", self.open_download_folder)
        self.detail = tk.StringVar(value="Chọn một lượt tải để xem chi tiết. Bấm chuột phải để đổi link hoặc nơi lưu.")
        from .download_ui import DownloadEditor
        self.download_placeholder = DownloadEditor(self, {"kind": "empty", "url": "", "original": ""})
        self.download_placeholder.pack(fill="both", expand=True)



    def set_bandwidth(self, mode):
        self.manager.set_bandwidth(mode)
        self.bandwidth_mode.set({"maximum": "Tối đa", "medium": "Vừa (4 MB/s)", "light": "Nhẹ (512 KB/s)"}[mode])

    def set_transfer_mode(self, mode):
        if mode not in {"normal", "maximum"}:
            raise ValueError("Invalid transfer mode")
        self.store.set_setting("transfer_mode", mode)
        with self.manager.hosts.condition:
            self.manager.hosts.default_limit = 8 if mode == "normal" else 32
            self.manager.hosts.condition.notify_all()
        self.set_bandwidth("medium" if mode == "normal" else "maximum")

    def dismiss_download(self):
        editor = getattr(self, "download_editor", None)
        if editor and editor.winfo_exists():
            editor.destroy()
        self.download_editor = None
        self.download_placeholder.pack(fill="both", expand=True)
        self.show_source_controls(False)
        self.source_message.set("")
        self.source_message_label.grid_remove()
        self.resize_source_card()
        self.download_requested = None
        self.url_entry.focus_set()

    def show_source_controls(self, visible):
        self.source_controls_visible = visible
        for widget in (self.url_panel, self.download_button):
            if visible and not self.page_stack:
                widget.grid()
            else:
                widget.grid_remove()
        if self.url.get() and not self.page_stack:
            self.cancel_button.grid()
        else:
            self.cancel_button.grid_remove()

    def show_update_notice(self, available):
        if available:
            self.update_notice.configure(width=max(160, self.header_logo.width()))
            self.update_notice.grid(row=1, column=0, sticky="sw", pady=(8, 0))
        else:
            self.update_notice.grid_remove()
        self.schedule_redraw()

    def save_directory(self):
        if self.directory.get().strip():
            self.store.set_setting("download_directory", self.directory.get().strip())

    def position_heading_separators(self):
        offset = 0
        for column, label in self.heading_icons.items():
            width = self.table.column(column, "width")
            label.place(x=offset+8 if column == "name" else offset+width/2, y=19,
                        anchor="w" if column == "name" else "center")
            offset += width
        boundary = 0
        for column, separator in zip(self.table["columns"], self.heading_separators):
            boundary += self.table.column(column, "width")
            separator.place(x=boundary+1, y=19, anchor="center")

    def resize_queue_columns(self):
        width = max(1, self.table.winfo_width()-2)
        used = 0
        for index, column in enumerate(self.table["columns"]):
            size = width-used if index == len(self.table["columns"])-1 else round(width*self.column_proportions[index])
            self.table.column(column, width=max(65, size))
            used += size
        self.position_heading_separators()
        self.update_safety_buttons()

    def begin_column_resize(self, event, index):
        columns = self.table["columns"]
        left, right = columns[index:index+2]
        self.column_drag = (event.x_root, left, right, self.table.column(left, "width"), self.table.column(right, "width"))
        return "break"

    def drag_column(self, event):
        if not getattr(self, "column_drag", None):
            return "break"
        start, left, right, width_left, width_right = self.column_drag
        delta = max(65-width_left, min(event.x_root-start, width_right-65))
        self.table.column(left, width=width_left+delta)
        self.table.column(right, width=width_right-delta)
        self.position_heading_separators()
        self.update_safety_buttons()
        return "break"

    def end_column_resize(self, _event):
        self.column_drag = None
        widths = [self.table.column(column, "width") for column in self.table["columns"]]
        self.column_proportions = tuple(width/sum(widths) for width in widths)
        return "break"

    def fit_icons(self):
        from .ui_scale import WindowScale
        size = WindowScale(self.root).size(24, 16)
        from .rounded import RoundedButton
        if getattr(self, "_icon_dimensions", None) != (self.theme, size):
            from .icons import load_icons
            old_icons = self.icons
            self.icons = load_icons(self.root, light=self.theme == "light", size=size)
            replacements = {str(old_icons[name]): image for name, image in self.icons.items()}

            def replace_images(parent):
                for widget in parent.winfo_children():
                    if isinstance(widget, RoundedButton):
                        key = str(widget.image)
                        if key in replacements:
                            widget.configure(image=replacements[key])
                    elif "image" in set(widget.keys()):
                        image = widget.cget("image")
                        key = str(image[0]) if isinstance(image, tuple) and image else str(image)
                        if key in replacements:
                            match = next(name for name, old in old_icons.items() if str(old) == key)
                            widget.configure(image=self.primary_icons[match] if self.theme == "light"
                                and str(widget.cget("style")) == "Primary.TButton" else replacements[key])
                    replace_images(widget)
            replace_images(self.root)
            self._icon_theme = self.theme
            self._icon_dimensions = (self.theme, size)

    def schedule_source_resize(self):
        if getattr(self, "_closing", False) or getattr(self, "source_resize_timer", None):
            return
        def resize():
            self.source_resize_timer = None
            self.resize_source_card()
        # Coalesce a burst of native Configure/idle events into one frame.
        self.source_resize_timer = self.root.after(16, resize)

    def resize_source_card(self):
        if getattr(self, "_resizing_source", False) or not self.url_panel.winfo_exists():
            return
        page = getattr(self, "preferences_dialog", None)
        editor = getattr(self, "download_editor", None) or getattr(self, "download_placeholder", None)
        signature = (self.root.winfo_width(), self.root.winfo_height(), self.root.tk.call("tk", "scaling"),
                     self.theme, self.locale.language, editor, tuple(self.page_stack),
                     self.empty_panel.winfo_width(), self._scaled_font_metrics is None)
        if getattr(self, "_source_layout_signature", None) == signature:
            if self.page_stack and page and page.winfo_exists():
                page.fit()
            return
        self._source_layout_signature = signature
        self._resizing_source = True
        try:
            logo_height = max(1, round(self.root.winfo_height()/5))
            logo_size = (round(logo_height*416/316), logo_height)
            if getattr(self, "_header_logo_size", None) != (logo_size, self.theme):
                from .icons import load_header_logo
                self.header_logo = load_header_logo(self.root, *logo_size, theme=self.theme)
                self._header_logo_size = (logo_size, self.theme)
            self.brand_label.configure(image=self.header_logo)
            logo_width = self.header_logo.width()
            from .ui_scale import WindowScale
            scale = WindowScale(self.root)
            self.fit_icons()
            style = ttk.Style(self.root)
            metrics = scale.font_size(10, 9), scale.size(38, 30)
            if self._scaled_font_metrics != metrics:
                style.configure(".", font=("Segoe UI", metrics[0]))
                style.configure("Treeview", font=("Segoe UI", metrics[0]), rowheight=metrics[1])
                self._scaled_font_metrics = metrics
            # Reserve four rows before recognition so the journal never jumps.
            height = max(scale.size(208, 192), logo_height+scale.size(38, 28))
            self.header.columnconfigure(0, minsize=logo_width+8)
            self.header.columnconfigure(2, minsize=0, weight=0)
            self.input_content.columnconfigure(1, minsize=scale.size(150, 100))
            self.download_button.configure(width=scale.size(130, 100), height=scale.size(44, 38))
            if self.download_button.label_font.actual("size") != scale.font_size(14, 11):
                self.download_button.label_font.configure(size=scale.font_size(14, 11))
            self.cancel_button.configure(image=self.icons["close"], width=scale.size(36, 28),
                                         height=scale.size(44, 38))
            self.url_entry.configure_font(("Segoe UI", scale.font_size(14, 11)))
            self.url_entry.configure(height=scale.size(44, 38))
            for label in self.url_form.winfo_children():
                if isinstance(label, ttk.Label):
                    label.configure(font=("Segoe UI", scale.font_size(14, 11)))
            if editor and editor.winfo_exists():
                editor.fit(scale)
            self.header_left.configure(width=logo_width, height=logo_height if self.page_stack else height)
            self.empty_panel.configure(height=height)
            self.source_message_label.configure(wraplength=max(120, self.empty_panel.winfo_width()-160))
            if self.page_stack and page and page.winfo_exists():
                page.fit()
            self.position_heading_separators()
            self.update_safety_buttons()
        finally:
            self._resizing_source = False

    def cancel_download(self):
        if getattr(self, "browser_submitting", None):
            return
        self.finish_browser_request("cancelled")
        if getattr(self, "paste_timer", None):
            self.root.after_cancel(self.paste_timer)
            self.paste_timer = None
        self.url.set("")
        self.dismiss_download()

    def submit_download(self):
        if getattr(self, "paste_timer", None):
            self.root.after_cancel(self.paste_timer)
            self.paste_timer = None
        original = self.url.get().strip()
        editor = getattr(self, "download_editor", None)
        if editor and editor.winfo_exists() and editor.original == original and not editor.description.get("metadata_error"):
            editor.confirm()
            return "break"
        self.prepare_download()
        self.download_requested = original
        return "break"

    def manual_paste(self, _event=None):
        """Only a paste inside the URL entry schedules source recognition."""
        timer = getattr(self, "paste_timer", None)
        if timer:
            self.root.after_cancel(timer)
        self.paste_timer = self.root.after(350, self._prepare_pasted_link)

    def _prepare_pasted_link(self):
        self.paste_timer = None
        from .links import clipboard_link
        if clipboard_link(self.url.get()):
            self.prepare_download()

    def prepare_download(self):
        from .download_ui import DownloadEditor
        from .links import describe_source, link_kind
        previous = getattr(self, "download_editor", None)
        if previous and previous.winfo_exists():
            if previous.original == self.url.get().strip() and not previous.description.get("metadata_error"):
                previous.focus_set()
                return
            self.dismiss_download()
        original = self.url.get().strip()
        if getattr(self, "source_busy", False):
            self.pending_source = original
            return
        self.pending_source = None
        def ready(description):
            kind, resolved = description["kind"], description["url"]
            self.source_busy = False
            if self.url.get().strip() != original:
                if self.pending_source == self.url.get().strip():
                    self.prepare_download()
                return
            if kind in {"spotify", "torrent"}:
                self.add(resolved_source=(kind, resolved))
                return
            self.source_message_label.grid_remove()
            self.download_editor = DownloadEditor(self, description)
            self.download_editor.pack(fill="both", expand=True)
            self.resize_source_card()
            if getattr(self, "download_requested", None) == original:
                self.download_requested = None
                self.download_editor.confirm()
        def action():
            kind = link_kind(original)
            if kind in {"spotify", "torrent"}:
                ready({"original": original, "kind": kind, "url": original})
                return
            self.source_busy = True
            self.show_source_controls(True)
            self.source_message.set(self.locale.text("Đang nhận diện nguồn tải…"))
            self.source_message_label.grid(row=2, column=0, sticky="w", pady=(4, 0))
            self.resize_source_card()
            session = self.browser_session if original == self.browser_session_url else ""
            cookie_file = self.media_cookie.get()
            def worker():
                try:
                    from contextlib import ExitStack
                    from tempfile import TemporaryDirectory

                    proxy = self.store.setting("proxy")
                    options = {"proxy": proxy} if proxy else {}
                    with ExitStack() as stack:
                        if session:
                            from .vault import cookie_jar, decrypt
                            temporary = stack.enter_context(TemporaryDirectory(prefix="hdm-preview-session-", dir=self.data_dir))
                            cookie_path = Path(temporary)/"cookies.txt"
                            cookie_path.write_text(cookie_jar(decrypt(session)), encoding="utf-8")
                            options["cookie_file"] = str(cookie_path)
                        elif cookie_file:
                            options["cookie_file"] = cookie_file
                        result = describe_source(original, **options)
                    self.events.put(lambda: ready(result))
                except Exception as error:  # noqa: BLE001 -- Restore controls after source detection.
                    self.events.put(lambda error=str(error): failed(error))
            def failed(error):
                self.source_busy = False
                if self.url.get().strip() == original:
                    self.source_message.set(error)
                if self.pending_source and self.pending_source != original:
                    self.prepare_download()
            thread = threading.Thread(target=worker, daemon=True)
            self.background_threads.append(thread)
            thread.start()
        self.guarded(action)

    def _safety(self, parent):
        self.high_security = tk.BooleanVar(value=self.store.setting("high_security", False))
        self.auto_defender = tk.BooleanVar(value=self.store.setting("auto_defender", False))
        ttk.Checkbutton(parent, text="Tự quét bằng Windows Defender sau khi tải", variable=self.auto_defender,
                        state="normal" if os.name == "nt" else "disabled",
                        command=lambda: self.store.set_setting("auto_defender", self.auto_defender.get())).pack(
                            anchor="w", pady=4)
        ttk.Checkbutton(parent, text="An toàn cao: cách ly chương trình chưa có chữ ký Windows hợp lệ",
                        state="normal" if os.name == "nt" else "disabled",
                        variable=self.high_security, command=lambda: self.store.set_setting(
                            "high_security", self.high_security.get())).pack(anchor="w", pady=4)

    def _about(self, parent):
        from .information_ui import build_contact_links

        ttk.Label(parent, text="Hngoos Download Manager", style="Card.TLabel",
                  font=("Segoe UI", 16, "bold")).pack(pady=(4, 8))
        ttk.Label(parent, text=f"HDM {__version__}", style="Card.TLabel").pack()
        build_contact_links(self, parent).pack(pady=(8, 0))

    def guarded(self, action):
        try:
            return action()
        except Exception as exc:  # noqa: BLE001 -- UI boundary must display worker/input errors.
            messagebox.showerror(self.locale.text("HDM"), self.locale.text(str(exc)), parent=self.root)

    def open_invoices(self):
        folder = self.data_dir/"invoices"
        folder.mkdir(parents=True, exist_ok=True)
        self.guarded(lambda: open_path(folder))

    def add(self, resolved_source=None):
        from .links import link_kind, resolve_source
        if getattr(self, "browser_submitting", None):
            return
        url = self.url.get().strip()
        if getattr(self, "source_busy", False):
            return
        def choose(kind, value):
            self.source_busy = False
            if self.url.get().strip() != url:
                self.status.set(self.locale.text("Link đã thay đổi; bấm tải lại để dùng link mới."))
                return
            if kind == "spotify":
                messagebox.showinfo(self.locale.text("HDM"), self.locale.text("Nhạc Spotify có DRM: không thể tải trực tiếp thành MP3."),
                                    parent=self.root)
                return
            if kind == "torrent":
                from .dialogs import torrent_dialog
                self.guarded(lambda: torrent_dialog(self, value, self.directory.get()))
                return
            if kind == "media" or self.download_format.get() in {"MP4", "MOV", "MP3", "M4A", "WAV"}:
                self.media_url.set(value)
                self.start_media({"MP3": "mp3", "M4A": "m4a", "WAV": "wav"}.get(self.download_format.get(), ""))
                return
            digest = self.expected_hash.get().strip()
            algorithm = self.hash_algorithm.get().lower().replace("-", "")
            directory, name, connections = self.directory.get(), self.filename.get(), int(self.connections.get())
            mirrors = [value.strip() for value in self.mirrors.get().split("|") if value.strip()]
            def accepted(_job):
                if browser_request:
                    self.browser_submitting = None
                    self.finish_browser_request("accepted", browser_request[0])
                if self.url.get().strip() == url:
                    self.url.set("")
                    self.filename.set("")
                    self.expected_hash.set("")
                    self.mirrors.set("")
                self.status.set(self.locale.text("Đã thêm lượt tải; sẽ kiểm tra trước khi hoàn tất."))
            browser_request = getattr(self, "browser_request", None)
            if browser_request and browser_request[1] != url:
                browser_request = None
            def create():
                try:
                    job = self.manager.add(value, directory, name or filename_from_url(value),
                        connections, digest if algorithm == "sha256" else "",
                        expected_hashes={algorithm: digest} if digest else {}, mirrors=mirrors,
                        **({"start": False} if browser_request else {}))
                except Exception:
                    if browser_request:
                        self.store.acknowledge(browser_request[0], "cancelled")
                    raise
                if browser_request:
                    # Persist ownership before starting work, even if the UI closes.
                    self.store.acknowledge(browser_request[0], "accepted")
                    self.manager.start(job)
                return job
            def failed(error):
                if browser_request:
                    self.browser_submitting = None
                    self.browser_request = None
                messagebox.showerror(self.locale.text("HDM"), self.locale.text(error), parent=self.root)
            if browser_request:
                self.browser_submitting = browser_request[0]
            self.background(create, accepted, failed, daemon=not bool(browser_request))
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
            proxy = self.store.setting("proxy")
            self.status.set(self.locale.text("Đang nhận diện nguồn tải…"))
            def resolve():
                try:
                    result = resolve_source(url, force_file, proxy=proxy)
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
        if self.url.get() and not self.page_stack:
            self.cancel_button.grid()
        else:
            self.cancel_button.grid_remove()
        request = getattr(self, "browser_request", None)
        if request and request[1] != self.url.get().strip():
            self.finish_browser_request("cancelled")
        editor = getattr(self, "download_editor", None)
        if editor and editor.winfo_exists() and editor.original != self.url.get().strip():
            self.dismiss_download()
        if not self.url.get().strip():
            self.show_source_controls(False)
            self.source_message_label.grid_remove()
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
        self.schedule_source_resize()
        if self.url.get().strip() != self.browser_session_url:
            self.video_inbox_busy = False
            self.browser_session = self.browser_session_url = ""
        self.media_format.set("")

    def choose_directory(self):
        folder = filedialog.askdirectory(initialdir=self.directory.get())
        if folder:
            self.directory.set(folder)
            self.store.set_setting("download_directory", folder)

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

    def open_download_folder(self, event):
        if self.table.identify_region(event.x, event.y) != "cell" or self.table.identify_column(event.x) != "#1":
            return "break"
        row = self.table.identify_row(event.y)
        if row:
            job = self.store.get(row)
            from .ui_fonts import metrics_font
            x, _y, width, _height = self.table.bbox(row, "name")
            font = metrics_font(self.root, ttk.Style(self.root).lookup("Treeview", "font") or ("Segoe UI", 10))
            if not x+4 <= event.x <= x+min(width-4, font.measure(job["filename"])+4):
                return "break"
            folder = Path(job["output"]).parent if job.get("output") else Path(job["directory"])
            if folder.is_dir():
                self.guarded(lambda: open_path(folder))
        return "break"

    def show_details(self, _event=None):
        if job_id := self.selected():
            job = self.store.get(job_id)
            location = job["error"] or job["output"] or f"Lưu tại: {job['directory']}"
            self.detail.set(location+" · "+self.locale.text(job.get("safety_note", "Chưa kiểm tra")))

    def delete_job(self, row, delete_file=False):
        """Delete only an inactive, explicitly chosen download; file removal needs confirmation."""
        job = self.store.get(row)
        media_active = getattr(self, "media_busy", False) and getattr(self, "media_job_id", None) == row
        if media_active or row in self.manager.active or job["state"] not in {"complete", "quarantined", "paused", "error"}:
            return
        if delete_file:
            outputs = job.get("outputs") or [job.get("output")]
            paths = [Path(value) for value in outputs if value]
            prompt = self.locale.text("Xóa vĩnh viễn các tệp sau?")+"\n\n"+"\n".join(str(path) for path in paths)
            if not messagebox.askyesno(self.locale.text("HDM"), self.locale.text(prompt), parent=self.root):
                return
            try:
                for path in paths:
                    path.unlink(missing_ok=True)
            except OSError as error:
                messagebox.showerror(self.locale.text("HDM"), self.locale.text(str(error)), parent=self.root)
                return
        self.store.delete(row)
        self.last_jobs.pop(row, None)

    def copy(self, value):
        self.root.clipboard_clear()
        self.root.clipboard_append(value)

    def replace_url_dialog(self):
        from tkinter.simpledialog import askstring
        job_id = self.selected()
        value = askstring(self.locale.text("Thay link"), self.locale.text("Dán link mới. Phần cũ chỉ dùng lại khi ETag mạnh và kích thước trùng."), parent=self.root)
        if value:
            self.guarded(lambda: self.manager.replace_url(job_id, value))

    def relocate(self):
        job_id = self.selected()
        job = self.store.get(job_id)
        folder = filedialog.askdirectory(title=self.locale.text("Đổi nơi lưu — giữ phần đã tải, tự tiếp tục"))
        if not folder or Path(folder).resolve() == Path(job["directory"]).resolve():
            return
        self.background(lambda: self.manager.relocate(job_id, folder),
                        lambda _: self.status.set("Đã yêu cầu chuyển nơi lưu; lượt đang tải sẽ tiếp tục sau khi chuyển."))

    def restore_dialog(self):
        job_id = self.selected()
        job = self.store.get(job_id)
        dialog = tk.Toplevel(self.root)
        dialog.title(self.locale.text("Khôi phục tệp cách ly"))
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
        path = filedialog.asksaveasfilename(title=self.locale.text("Báo cáo danh sách"), defaultextension=".csv", filetypes=[(self.locale.text("CSV"), "*.csv")])
        if path:
            self.guarded(lambda: export_batch_report(self.store, path))

    def background(self, action, success, failure=None, *, daemon=True):
        def run():
            try:
                result = action()
                self.events.put(lambda result=result: success(result))
            except Exception as exc:  # noqa: BLE001 -- Route optional-library failures to the UI.
                if failure:
                    self.events.put(lambda error=str(exc): failure(error))
                else:
                    self.events.put(lambda error=str(exc): messagebox.showerror(self.locale.text("HDM"), self.locale.text(error), parent=self.root))
        worker = threading.Thread(target=run, daemon=daemon)
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
            height=int(self.media_quality.get()), audio="" if self.media_format.get() else audio, playlist=self.media_playlist.get(),
            subtitles=self.media_subtitles.get(), cookie_file=self.media_cookie.get(),
            format_id=self.media_format.get(), connections=int(self.connections.get()),
            filename="" if self.media_playlist.get() else self.filename.get().strip(),
            container=self.download_format.get().lower() if self.download_format.get() in {"MP4", "MOV", "WEBM", "MKV"} else "mp4",
            audio_bitrate=int(self.media_bitrate.get()))
        if url == self.browser_session_url:
            options.referrer = getattr(self, "browser_referrer", "")
        options.proxy = self.store.setting("proxy")
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
        auto_scan = self.store.setting("auto_defender", False) and os.name == "nt"
        def action():
            from .media import MediaCancelled
            from .policy import TransferCancelled
            last_write = [0.0]
            safety_notes = []
            def progress(data):
                now = time.monotonic()
                if data.get("safety_note"):
                    safety_notes.append(data["safety_note"])
                    self.store.update(job_id, state="verifying" if high_security or self.store.setting("auto_defender", False) else "assembling",
                                      safety_note="Đang kiểm tra" if high_security or self.store.setting("auto_defender", False) else "")
                    return
                if "downloaded_bytes" not in data:
                    return
                if now-last_write[0] < 0.4 and data.get("status") != "finished":
                    return
                last_write[0] = now
                changes = {"downloaded": int(data.get("downloaded_bytes") or 0),
                           "total": int(data.get("total_bytes") or data.get("total_bytes_estimate") or 0),
                           "total_estimated": bool(data.get("total_estimated")),
                           "speed": float(data.get("speed") or 0)}
                title = (data.get("info_dict") or {}).get("title")
                if title:
                    changes["filename"] = title
                if data.get("status") == "finished":
                    changes.update(state="assembling")
                else:
                    changes["state"] = "downloading"
                self.store.update(job_id, **changes)
            try:
                kwargs = {"progress": progress, "options": options, "stop": self.media_stop,
                          "high_security": high_security, "staging_root": self.data_dir/"media-staging",
                          "antivirus": False}
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
                    output=str(outputs[0]), outputs=[str(path) for path in outputs], total=size, downloaded=size, total_estimated=False,
                    sha256=sha256_file(outputs[0]) if high_security else "",
                    safety_note="Cách ly" if quarantined else (
                        "Sơ bộ + Defender" if safety_notes and all(note == "Sơ bộ + Defender" for note in safety_notes)
                        else "Sơ bộ · Defender chưa quét" if "Sơ bộ · Defender chưa quét" in safety_notes
                        else "Đã kiểm tra sơ bộ" if high_security else ""),
                    error="Có tệp rủi ro đã được cách ly." if quarantined else "")
                if auto_scan:
                    self.events.put(lambda: self.check_selected_safety(job_id))
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
        source = filedialog.askopenfilename(title=self.locale.text("Chọn video"))
        if not source:
            return
        destination = filedialog.asksaveasfilename(title=self.locale.text("Lưu MP4"), defaultextension=".mp4",
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
        path = filedialog.askopenfilename(title=self.locale.text("Chọn cookies.txt do bạn chủ động xuất"), filetypes=[(self.locale.text("Netscape cookie file"), "*.txt")])
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
        value = askstring(self.locale.text("Hẹn giờ"), self.locale.text("Nhập ngày giờ trên máy: YYYY-MM-DD HH:MM"), parent=self.root)
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
        dialog.title(self.locale.text("Nhật ký — " + job["filename"]))
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
        url = askstring(self.locale.text("Link đám mây"), self.locale.text("Dán link chia sẻ tệp công khai"), parent=self.root)
        if url:
            self.background(lambda: resolve(url), lambda direct: (self.url.set(direct), self.tabs.select(0)))

    def adopt_partial(self):
        from tkinter.simpledialog import askstring
        partial = filedialog.askopenfilename(title=self.locale.text("Chọn .crdownload/.part đã dừng trong trình duyệt"))
        if not partial:
            return
        url = askstring(self.locale.text("Tiếp quản"), self.locale.text("Dán URL tải trực tiếp. Tệp gốc được giữ lại; toàn bộ phần cũ sẽ được xác minh."), parent=self.root)
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
        source = filedialog.askopenfilename(filetypes=[(self.locale.text("ZIP"), "*.zip")])
        if source:
            parent = filedialog.askdirectory(title=self.locale.text("Thư mục cha để tạo thư mục giải nén mới"))
            if parent:
                target = Path(parent)/Path(source).stem
                self.background(lambda: extract_zip(source, target),
                                lambda path: self.status.set(f"Đã giải nén: {path}"))

    def find_subtitle(self):
        from tkinter.simpledialog import askstring

        from .subtitles import download_vietnamese
        movie = filedialog.askopenfilename(title=self.locale.text("Chọn phim để tìm phụ đề tiếng Việt"))
        if not movie:
            return
        api_key = askstring(self.locale.text("OpenSubtitles"), self.locale.text("Nhập API key của bạn (chỉ dùng cho tác vụ này)"), show="*", parent=self.root)
        if not api_key:
            return
        token = askstring(self.locale.text("OpenSubtitles"), self.locale.text("JWT token nếu dịch vụ yêu cầu đăng nhập (có thể để trống)"), show="*", parent=self.root)
        if token is None:
            return
        self.background(lambda: download_vietnamese(movie, api_key.strip(), token.strip()),
                        lambda path: self.status.set(f"Đã tải phụ đề khớp mã phim: {path}"))

    def inspect_safety(self):
        from tkinter.simpledialog import askstring

        from .safety import authenticode, inspect_file, installer_guidance
        source = filedialog.askopenfilename(title=self.locale.text("Kiểm tra tệp / ZIP / RAR / 7z / chữ ký Windows"))
        if not source:
            return
        password = askstring(self.locale.text("ZIP có mật khẩu?"), self.locale.text("Nếu ZIP có mật khẩu, nhập mật khẩu (có thể để trống)"), show="*", parent=self.root)
        def action():
            import json
            reasons = inspect_file(source, Path(source).name, password,
                                   high_security=self.store.setting("high_security", False))
            signature = authenticode(source)
            guidance = installer_guidance(source, Path(source).name)
            return ("Dấu hiệu:\n" + "\n".join(reasons or ["Chưa thấy dấu hiệu trong phạm vi kiểm tra; không chứng minh tệp sạch."])
                    + "\n\nChữ ký Windows:\n" + json.dumps(signature, ensure_ascii=False)
                    + ("\n\nNguồn chính thức và đối chiếu nhà phát hành:\n"+json.dumps(guidance, ensure_ascii=False) if guidance else ""))
        self.background(action, lambda report: messagebox.showinfo(self.locale.text("Kiểm tra sơ bộ"), self.locale.text(report), parent=self.root))

    def toggle_guard(self):
        from .guard import DirectoryGuard
        if getattr(self, "guard", None):
            self.guard.close()
            self.guard = None
            self.status.set("Đã tắt theo dõi thư mục tải.")
            return
        folder = filedialog.askdirectory(title=self.locale.text("Theo dõi tệp mới/sửa đổi; tệp rủi ro được đổi đuôi .chuakiemtra"))
        if folder:
            def action():
                self.guard = DirectoryGuard(folder, self.store)
                self.status.set(f"Đang bảo vệ tệp mới trong: {folder}")
            self.guarded(action)

    def update_safety_buttons(self):
        if not hasattr(self, "row_safety_buttons") or getattr(self, "_closing", False):
            return
        visible, safe_visible, remove_visible = set(), set(), set()
        for row in self.table.get_children():
            box = self.table.bbox(row, "properties")
            if not box:
                continue
            job = self.store.get(row)
            visible.add(row)
            more = self.row_more_buttons.get(row)
            if more is None:
                from .rounded import RoundedButton
                more = RoundedButton(self.table, text="Xóa",
                                     command=lambda row=row: self.journal_action(row), flat=True)
                more.set_presentation(self.theme, self.locale.text)
                # Scrolling maps fresh controls. They are already presented;
                # resetting all styles here would undo scaled row heights.
                more._hdm_presentation = (self.theme, self.locale.language)
                self.row_more_buttons[row] = more
            x, y, _width, height = box
            more.surface_background = ("#e0e0e0" if self.theme == "light" else "#383838") if row in self.table.selection() else PANEL
            from .ui_scale import WindowScale
            font_size = WindowScale(self.root).font_size(10, 9)
            if more.label_font.actual("size") != font_size:
                more.label_font.configure(size=font_size)
            self.update_colored_cells(row, job, more.surface_background)
            active = (job["state"] not in {"complete", "quarantined"} and
                      (row in self.manager.active or (getattr(self, "media_busy", False) and getattr(self, "media_job_id", None) == row)))
            action_text = ("Dừng" if active or job["state"] in {"queued", "downloading", "scheduled"}
                           else "Tiếp tục" if job["state"] in {"paused", "error"} else "Xóa")
            more.configure(text=action_text,
                state="normal" if row not in self.pending_removals and (active or job["state"] in {"queued", "downloading", "scheduled", "complete", "quarantined", "paused", "error"}) else "disabled")
            more.draw()
            split = active or job["state"] in {"queued", "downloading", "scheduled", "paused", "error"}
            action_width = (_width-8)//2 if split else _width-8
            more_width = min(action_width, max(64, more.label_font.measure(self.locale.text(action_text))+12))
            more.place(x=x+4+(action_width-more_width)//2, y=y+3, width=more_width, height=max(1, height-6))
            if split:
                remove_visible.add(row)
                remove = self.row_remove_buttons.get(row)
                if remove is None:
                    remove = RoundedButton(self.table, text="Xóa",
                        command=lambda row=row: self.remove_journal_job(row), flat=True)
                    remove.set_presentation(self.theme, self.locale.text)
                    remove._hdm_presentation = (self.theme, self.locale.language)
                    self.row_remove_buttons[row] = remove
                remove.surface_background = more.surface_background
                if remove.label_font.actual("size") != font_size:
                    remove.label_font.configure(size=font_size)
                remove.configure(state="disabled" if row in self.pending_removals else "normal")
                remove.draw()
                remove.place(x=x+4+action_width, y=y+3, width=action_width, height=max(1, height-6))
                self.journal_separator(row, "actions_separator", x+4+action_width-6, y, height, more.surface_background)
            elif (label := self.row_cell_labels.pop((row, "actions_separator"), None)) is not None:
                label.destroy()
            separator = self.row_separators.get(row)
            if separator is None:
                separator = tk.Frame(self.table, borderwidth=0, takefocus=False)
                self.row_separators[row] = separator
            separator.configure(background="#d4d4d4" if self.theme == "light" else "#353535")
            separator._hdm_presentation = (self.theme, self.locale.language)
            separator.place(x=2, y=y+height-1, width=max(1, self.table.winfo_width()-4), height=1)
            label = self.safety_status(job)
            retry_scan = job.get("safety_check", {}).get("status") == "error"
            if (label and not retry_scan) or job["state"] not in {"complete", "quarantined"} or not job.get("output") or self.file_missing(job):
                continue
            safe_visible.add(row)
            button = self.row_safety_buttons.get(row)
            if button is None:
                from .rounded import RoundedButton
                button = RoundedButton(self.table, text="", image=self.icons["shield"],
                    command=lambda row=row: self.check_selected_safety(row), flat=True)
                button.set_presentation(self.theme, self.locale.text)
                button._hdm_presentation = (self.theme, self.locale.language)
                self.row_safety_buttons[row] = button
            x, y, _width, height = self.table.bbox(row, "status")
            button.surface_background = more.surface_background
            button.configure(image=self.icons["shield"])
            button.draw()
            status_label = self.row_cell_labels[row, "check" if retry_scan else "status"]
            placement = status_label.place_info()
            button.place(x=int(placement["x"])+int(placement["width"])+(6 if retry_scan else 18), y=y+3,
                         width=30, height=max(1, height-6))
        for row in list(self.row_safety_buttons):
            if row not in safe_visible:
                self.row_safety_buttons.pop(row).destroy()
        for row in list(self.row_more_buttons):
            if row not in visible:
                self.row_more_buttons.pop(row).destroy()
        for row in list(self.row_remove_buttons):
            if row not in remove_visible:
                self.row_remove_buttons.pop(row).destroy()
        for key in list(self.row_cell_labels):
            if key[0] not in visible:
                self.row_cell_labels.pop(key).destroy()
        for row in list(self.row_separators):
            if row not in visible:
                self.row_separators.pop(row).destroy()
        surface = getattr(self, "presentation_surface", None)
        if surface and not self.page_stack:
            surface.schedule()

    def journal_action(self, row):
        """Resolve the current job state at click time, without relying on selection."""
        if row in self.pending_removals:
            return
        try:
            job = self.store.get(row)
        except KeyError:
            return  # A second click may arrive before the removed row redraws.
        active = row in self.manager.active or (getattr(self, "media_busy", False)
                                               and getattr(self, "media_job_id", None) == row)
        if job["state"] in {"complete", "quarantined"}:
            if active:
                self.pending_removals.add(row)
            else:
                self.delete_job(row, False)
        elif active or job["state"] in {"queued", "downloading", "scheduled"}:
            self.stop_job(row)
        elif job["state"] in {"paused", "error"}:
            if job.get("kind") == "media":
                self.guarded(lambda: self.resume_media(job))
            else:
                self.manager.start(row)

    def remove_journal_job(self, row):
        """Stop writers before removing a journal entry; preserve finished files."""
        try:
            job = self.store.get(row)
        except KeyError:
            self.pending_removals.discard(row)
            return
        with self.manager.lock:
            active = row in self.manager.active or (getattr(self, "media_busy", False)
                                                   and getattr(self, "media_job_id", None) == row)
            if active or job["state"] in {"assembling", "verifying"}:
                self.pending_removals.add(row)
                self.stop_job(row)
                return
            self.manager.pause(row)
            if job["state"] in {"queued", "downloading"}:
                self.store.update(row, state="paused", retry_at=0, scheduled_at=0)
            self.delete_job(row, False)
            self.pending_removals.discard(row)

    def stop_job(self, row):
        if getattr(self, "media_busy", False) and getattr(self, "media_job_id", None) == row:
            self.media_stop.set()
        else:
            self.manager.pause(row)

    def journal_separator(self, row, name, x, y, height, background):
        key = row, name
        label = self.row_cell_labels.get(key)
        if label is None:
            label = self.row_cell_labels[key] = ttk.Label(self.table, text="|", anchor="center", style="Card.TLabel")
            label.translate_text = False
            label._hdm_presentation = (self.theme, self.locale.language)
        label.configure(foreground=MUTED, background=background)
        label.place(x=x, y=y+1, width=12, height=max(1, height-2))

    def update_colored_cells(self, row, job, background):
        from .ui_fonts import metrics_font
        from .ui_preferences import SEMANTIC_COLORS, speed_color
        colors = SEMANTIC_COLORS[self.theme]
        status_color = colors["danger"] if self.file_missing(job) else colors["safe"] if job["state"] == "complete" else TEXT
        check = job.get("safety_check", {}).get("status")
        check_color = colors.get({"clean": "safe", "threat": "risk", "risk": "risk", "danger": "danger",
                                  "error": "risk"}.get(check), MUTED)
        for column, text, color in (
                ("status", self.table.set(row, "status"), status_color),
                ("speed", self.table.set(row, "speed"), speed_color(job["speed"] if job["state"] == "downloading" else 0, self.theme)),
                ("check", self.safety_status(job), check_color)):
            key = row, column
            label = self.row_cell_labels.get(key)
            if not text:
                if label is not None:
                    self.row_cell_labels.pop(key).destroy()
                continue
            box = self.table.bbox(row, "status" if column == "check" else column)
            if not box:
                continue
            if label is None:
                label = ttk.Label(self.table, anchor="center", style="Card.TLabel", padding=0)
                label.translate_text = False
                label._hdm_presentation = (self.theme, self.locale.language)
                self.row_cell_labels[key] = label
            label.configure(text=text, foreground=color, background=background)
            x, y, width, height = box
            if column in {"status", "check"} and job["state"] in {"complete", "quarantined"} and job.get("output") and not self.file_missing(job):
                font = metrics_font(self.root, ttk.Style(self.root).lookup("Card.TLabel", "font") or "TkDefaultFont")
                status_width = font.measure(self.table.set(row, "status"))+4
                check_width = font.measure(self.safety_status(job))+4 if self.safety_status(job) else 30
                retry_width = 36 if check == "error" else 0
                x += max(1, (width-status_width-check_width-18-retry_width)//2)
                if column == "check":
                    x += status_width+18
                width = check_width if column == "check" else status_width
                label.place(x=x, y=y+1, width=width, height=max(1, height-2))
                continue
            label.place(x=x+1, y=y+1, width=max(1, width-2), height=max(1, height-2))
        if job["state"] in {"complete", "quarantined"} and job.get("output") and not self.file_missing(job):
            status = self.row_cell_labels[row, "status"].place_info()
            self.journal_separator(row, "status_separator", int(status["x"])+int(status["width"])+3,
                                   y, height, background)
        elif (label := self.row_cell_labels.pop((row, "status_separator"), None)) is not None:
            label.destroy()

    def safety_status(self, job):
        labels = {"scanning": "Đang quét", "clean": "An toàn", "threat": "Có rủi ro", "risk": "Có rủi ro",
                  "danger": "Nguy hiểm", "error": "Lỗi quét"}
        return self.locale.text(labels.get(job.get("safety_check", {}).get("status"), ""))

    @staticmethod
    def file_missing(job):
        if job["state"] not in {"complete", "quarantined"}:
            return False
        paths = job.get("outputs") or ([job["output"]] if job.get("output") else [])
        try:
            return any(not Path(path).is_file() for path in paths)
        except OSError:
            return False

    def check_selected_safety(self, job_id=None):
        job_id = job_id or self.selected()
        if not job_id:
            return
        try:
            job = self.store.get(job_id)
        except KeyError:
            return  # A queued automatic scan may outlive its journal entry.
        if job["state"] not in {"complete", "quarantined"} or not job.get("output"):
            return
        if not hasattr(self, "safety_scanning"):
            self.safety_scanning = set()
        if job_id in self.safety_scanning:
            return
        self.safety_scanning.add(job_id)
        self.store.update(job_id, safety_check={"provider": "defender", "status": "scanning"})
        self.update_safety_buttons()
        paths = list(dict.fromkeys(job.get("outputs") or [job["output"]]))
        identities = {}
        def finish(status, detail="", threats=()):
            self.safety_scanning.discard(job_id)
            if not any(job["id"] == job_id for job in self.store.all()):
                return
            if status == "clean":
                from .safety_ui import file_identity
                current = self.store.get(job_id)
                current_paths = list(dict.fromkeys(current.get("outputs") or [current["output"]]))
                try:
                    unchanged = current_paths == paths and all(file_identity(path) == identities[path] for path in paths)
                except OSError:
                    unchanged = False
                if not unchanged:
                    status, detail = "error", "Tệp thay đổi trong lúc kiểm tra; hãy quét lại."
            if status == "threat":
                from .files import deliver
                current = self.store.get(job_id)
                outputs = list(current.get("outputs") or [current["output"]])
                failures = []
                for index, value in enumerate(outputs):
                    path = Path(value)
                    if value in threats and not path.name.endswith(".chuakiemtra"):
                        try:
                            outputs[index] = str(deliver(path, path.parent, path.name+".chuakiemtra"))
                            self.store.update(job_id, state="quarantined", output=outputs[0], outputs=outputs,
                                              safety_note="Cách ly")
                        except OSError as error:
                            failures.append(value+": "+str(error))
                if failures:
                    detail = "\n".join(filter(None, (detail, *failures)))
            self.store.update(job_id, safety_check={"provider": "defender", "status": status,
                                                  "detail": detail, "checked_at": time.time()})
            self.update_safety_buttons()
        def worker():
            try:
                from .safety_ui import file_identity, scan_files
                identities.update((path, file_identity(path)) for path in paths)
                status, detail, threats = scan_files(paths, lambda path: scan_defender(path, stop=self.manager.scheduler_stop))
                self.events.put(lambda: finish(status, detail, threats))
            except Exception as exc:  # noqa: BLE001 -- Scanner failure must never be shown as clean.
                self.events.put(lambda error=str(exc): finish("error", error))
        thread = threading.Thread(target=worker, daemon=True)
        self.background_threads.append(thread)
        thread.start()

    def check_update(self):
        from .update_ui import UpdateDialog
        if getattr(self, "update_dialog", None) and self.update_dialog.window.winfo_exists():
            self.update_dialog.window.lift()
            return
        self.update_dialog = UpdateDialog(self, ready=self.automatic_updates.ready)

    def update_ytdlp(self):
        from .toolchain import update_ytdlp
        if any(getattr(self, flag, False) for flag in ("media_tool_busy", "media_busy", "source_busy")):
            return
        self.media_tool_busy = True
        def finish(version=None, error=None):
            self.media_tool_busy = False
            if error:
                self.store.set_setting("video_tool_update_error", error)
            else:
                checked = time.time()
                self.store.set_setting("last_video_tool_check", checked)
                self.store.set_setting("video_tool_version", version)
                self.store.set_setting("video_tool_update_error", "")
                self.automatic_video_updates.next_check = checked+24*3600
        def worker():
            try:
                version = update_ytdlp()
                self.events.put(lambda: finish(version=version))
            except Exception as error:  # noqa: BLE001 -- Optional background failures never interrupt downloads.
                self.events.put(lambda error=str(error): finish(error=error))
        thread = threading.Thread(target=worker, daemon=True)
        self.background_threads.append(thread)
        thread.start()

    def guard_log(self):
        dialog = tk.Toplevel(self.root)
        dialog.title(self.locale.text("Nhật ký bảo vệ thư mục"))
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
                if messagebox.askyesno(self.locale.text("Xóa tệp cách ly"), self.locale.text(f"Xóa vĩnh viễn tệp này?\n{source}"), parent=dialog):
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
        dialog.title(self.locale.text("Lưu website thành PDF / ảnh"))
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
            folder = filedialog.askdirectory(title=self.locale.text("Thư mục lưu trang"))
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
            self.background(task, lambda report: messagebox.showinfo(self.locale.text("Lưu trang"), self.locale.text(report), parent=self.root))
            dialog.destroy()
        ttk.Button(frame, text="Chọn nơi lưu và bắt đầu…", command=save).pack(anchor="e", pady=10)

    def hash_file(self):
        path = filedialog.askopenfilename(title=self.locale.text("Tính SHA-256"))
        if path:
            self.status.set("Đang tính SHA-256…")
            self.background(lambda: sha256_file(path), lambda digest: (
                self.hash_value.set(digest), self.status.set("Đã tính xong SHA-256")))

    def defender(self):
        path = filedialog.askopenfilename(title=self.locale.text("Chọn tệp để quét với Defender"))
        if path:
            self.status.set("Đang quét bằng Windows Defender…")
            self.background(lambda: scan_defender(path), lambda result: messagebox.showinfo(
                self.locale.text("Windows Defender"), self.locale.text(f"Mã kết quả: {result.returncode}\n{result.stdout}\n{result.stderr}"), parent=self.root))

    def lookup_hash(self):
        from .safety import hash_lookup_url
        self.guarded(lambda: webbrowser.open(hash_lookup_url(self.hash_value.get(), self.hash_service.get())))

    def refresh(self):
        if getattr(self, "_closing", False):
            return
        try:
            while not getattr(self, "_closing", False):
                try:
                    callback = self.events.get_nowait()
                except queue.Empty:
                    break
                try:
                    callback()
                except Exception:  # noqa: BLE001 -- A failed result must not disable tray commands.
                    self.root.report_callback_exception(*sys.exc_info())
            if not getattr(self, "_closing", False):
                self._refresh_state()
        except Exception:  # noqa: BLE001 -- Report the failure and keep the event pump alive.
            self.root.report_callback_exception(*sys.exc_info())
        finally:
            if not getattr(self, "_closing", False):
                self.refresh_id = self.root.after(500, self.refresh)

    def finish_browser_request(self, state, request_id=None):
        request = getattr(self, "browser_request", None)
        if state == "cancelled" and request and request[0] == getattr(self, "browser_submitting", None):
            return
        if request and (request_id is None or request[0] == request_id):
            self.store.acknowledge(request[0], state)
            self.browser_request = None

    def review_browser_download(self, request_id, item):
        from .download_ui import DownloadEditor
        # The bridge has already resolved this file; discard stale page previews.
        self.source_busy = False
        self.pending_source = None
        self.download_requested = None
        self.url.set(item["url"])
        self.dismiss_download()
        self.filename.set(item["filename"] or filename_from_url(item["url"]))
        self.browser_request = (request_id, item["url"])
        self.download_editor = DownloadEditor(self, {"original": item["url"], "url": item["url"],
            "kind": "file", "filename": self.filename.get()})
        self.download_editor.pack(fill="both", expand=True)
        self.resize_source_card()

    def _refresh_state(self):
        from .links import link_kind
        from .platforms import activate_window

        instance = getattr(self, "instance", None)
        if instance and instance.consume_show_request():
            activate_window(self.root)
        self.automatic_updates.tick()
        self.automatic_video_updates.tick()
        now = time.monotonic()
        if now-getattr(self, "history_maintained_at", 0) >= 5:
            self.manager.maintain_history()
            self.history_maintained_at = now
        pending = self.store.inbox()
        if getattr(self, "browser_request", None):
            pending = []
        if pending and pending[0][1]["kind"] == "video" and (self.video_inbox_busy or getattr(self, "media_busy", False)):
            pending = []
        if pending and not getattr(self, "inbox_dialog", False):
            self.inbox_dialog = True
            request_id, item = pending[0]
            try:
                if item["kind"] != "invoice":
                    if self.page_stack:
                        self.page_stack[0].hide()
                    activate_window(self.root)
                self.store.acknowledge(request_id, "reviewing")
                if item["kind"] == "invoice":
                    from .invoices import save_invoice
                    destination = self.data_dir/"invoices"
                    def archived(path, request_id=request_id):
                        self.store.acknowledge(request_id)
                        self.status.set(f"Đã lưu phiếu: {path}")
                    self.background(lambda item=item: save_invoice(item["url"], item["html"], item["order_id"], destination),
                        archived)
                elif item["kind"] == "video" or link_kind(item["url"]) == "media":
                    self.video_inbox_busy = True
                    self.browser_session = item.get("session_dpapi", "")
                    self.browser_session_url = item["url"]
                    self.browser_referrer = item.get("referrer", "")
                    self.media_url.set(item["url"])
                    self.url.set(item["url"])
                    self.status.set("Đã nhận link video từ trình duyệt; chọn chất lượng rồi tải.")
                    self.store.acknowledge(request_id)
                    self.prepare_download()
                else:
                    suggested = item["filename"] or filename_from_url(item["url"])
                    if item.get("auto_start"):
                        self.manager.add(item["url"], self.directory.get(), suggested, int(self.connections.get()))
                        self.store.acknowledge(request_id)
                    else:
                        self.review_browser_download(request_id, item)
            finally:
                self.inbox_dialog = False
        for row in tuple(self.pending_removals):
            self.remove_journal_job(row)
        jobs = self.store.all()
        down = sum(job.get("speed", 0) for job in jobs if job["state"] == "downloading")
        up = 0
        for torrent in getattr(self, "torrent_jobs", []):
            if not torrent.closed:
                state = torrent.status()
                down += state["download_rate"]
                up += state["upload_rate"]
        self.speed_meter.update_rates(down, up)
        visible = jobs
        visible_ids = {job["id"] for job in visible}
        for row in self.table.get_children():
            if row not in visible_ids:
                self.table.delete(row)
        from .automatic_updates import has_active_work
        from .power import prevent_sleep
        running = has_active_work(self)
        if running != self.sleep_prevented:
            prevent_sleep(running)
            self.sleep_prevented = running
        if self.shutdown_after.get():
            if self.manager.active or getattr(self, "media_busy", False):
                self.power_seen_work = True
            if (self.power_seen_work and jobs and not running
                    and all(job["state"] in {"complete", "quarantined"} for job in jobs)):
                self.shutdown_after.set(False)
                from .power import shutdown_in
                self.guarded(lambda: shutdown_in(60))
                self.status.set("Đã hẹn tắt máy sau 60 giây. Bấm Hủy trong Công cụ để hủy.")
        for job in visible:
            total = (("≈" if job.get("total_estimated") else "")+human(job["total"])) if job["total"] else (
                "Determining size" if self.locale.language == "en" else "Đang xác định dung lượng")
            progress = f"{human(job['downloaded'])} / {total}"
            state = ("Done" if self.locale.language == "en" else "Hoàn tất") if job["state"] == "complete" else (progress if job["state"] == "downloading"
                     else self.locale.text(STATES.get(job["state"], job["state"]))+" · "+progress)
            if self.file_missing(job):
                state = self.locale.text("Tệp đã bị xóa")
            values = (job["filename"], state,
                      f"{human(job['speed'])}/s" if job["speed"] else "—",
                      "")
            if self.last_jobs.get(job["id"]) != values or not self.table.exists(job["id"]):
                if self.table.exists(job["id"]):
                    self.table.item(job["id"], values=values)
                else:
                    self.table.insert("", 0, iid=job["id"], values=values)
                self.last_jobs[job["id"]] = values
        self.position_heading_separators()
        self.update_safety_buttons()
        self.show_details()

    def close(self):
        if getattr(self, "_closing", False):
            return
        self._closing = True
        self.finish_browser_request("cancelled")
        def finish(action, *args):
            try:
                action(*args)
            except Exception:  # noqa: BLE001 -- One failed cleanup cannot leave other workers running.
                self.root.report_callback_exception(*sys.exc_info())
        for name in ("navigation_timer", "presentation_timer", "redraw_timer", "source_resize_timer",
                     "refresh_id", "paste_timer"):
            if timer := getattr(self, name, None):
                finish(self.root.after_cancel, timer)
                setattr(self, name, None)
        self.media_stop.set()
        # Signal downloads and security scans before waiting for optional components.
        finish(self.manager.close)
        if getattr(self, "update_dialog", None):
            finish(self.update_dialog.close)
        for stop in getattr(self, "processing_stops", []):
            stop.set()
        for job in getattr(self, "torrent_jobs", []):
            finish(job.close)
        if getattr(self, "guard", None):
            finish(self.guard.close)
        if getattr(self, "tray", None):
            finish(self.tray.close)
        from .power import prevent_sleep
        finish(prevent_sleep, False)
        finish(self.root.destroy)

    def request_close(self):
        if self.close_to_tray.get():
            try:
                if not getattr(self, "tray", None):
                    from .tray import Tray
                    self.tray = Tray(self)
                self.tray.hide()
                return
            except (ImportError, RuntimeError) as exc:
                messagebox.showerror(self.locale.text("Khay hệ thống"), self.locale.text(str(exc)), parent=self.root)
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
        try:
            InstanceLock.request_show(data_dir / "instance.lock")
        except OSError:
            from .ui_preferences import Localizer
            locale = Localizer(root, Store(data_dir / "downloads.sqlite3").setting("language", "en"))
            messagebox.showinfo("HDM", locale.text(str(exc)), parent=root)
        root.destroy()
        return
    app = None
    try:
        app = App(root, data_dir, register_startup=bool(getattr(sys, "frozen", False)) and not args.smoke_test)
        app.instance = instance
        if args.smoke_test:
            root.after(1500, app.close)
        root.mainloop()
    finally:
        # Keep the process lock until all file workers have stopped.
        if app:
            app.manager.close()
            app.manager.pool.shutdown(wait=True)
        instance.close()


if __name__ == "__main__":
    main()
