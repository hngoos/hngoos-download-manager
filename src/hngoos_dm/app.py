"""Vietnamese desktop UI for Windows, macOS and Linux with Tkinter."""

import argparse
import os
import queue
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from . import __version__
from .engine import DownloadManager
from .instance import InstanceLock
from .paths import data_directory
from .platforms import open_path, platform_label
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
        self.data_dir = data_dir
        self.manager = DownloadManager(self.store)
        self.events = queue.Queue()
        self.background_threads = []
        self.last_jobs = {}
        self.directory = tk.StringVar(value=str(Path.home() / "Downloads"))
        self.url = tk.StringVar()
        self.filename = tk.StringVar()
        self.connections = tk.StringVar(value="8")
        self.expected_hash = tk.StringVar()
        self.hash_algorithm = tk.StringVar(value="SHA-256")
        self.mirrors = tk.StringVar()
        self.bandwidth_mode = tk.StringVar(value={"maximum": "Tối đa", "medium": "Vừa (4 MB/s)", "light": "Nhẹ (512 KB/s)"}[
            self.store.setting("bandwidth_mode", "maximum")])
        self.media_stop = threading.Event()
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
        self._layout()
        decorate_buttons(root, self.icons)
        self.playback_icon = MorphPlayback(self.transfer_button)
        for index, icon in enumerate(("download", "video", "shield", "globe", "settings", "info")):
            self.tabs.tab(index, image=self.icons[icon], compound="left")
        self.root.protocol("WM_DELETE_WINDOW", self.request_close)
        self.root.after(200, self.refresh)

    def _styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(".", background=BG, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("TFrame", background=BG)
        style.configure("Card.TFrame", background=PANEL)
        style.configure("TLabel", background=BG, foreground=TEXT)
        style.configure("Muted.TLabel", foreground=MUTED)
        style.configure("Title.TLabel", font=("Segoe UI", 26, "bold"))
        style.configure("TButton", padding=(12, 8), background="#242b3e", foreground=TEXT,
                        borderwidth=0, bordercolor=BG, lightcolor=BG, darkcolor=BG)
        style.map("TButton", background=[("active", "#344e73")])
        style.configure("Primary.TButton", background="#7c3aed", foreground="white")
        style.map("Primary.TButton", background=[("active", "#8b5cf6")])
        style.configure("Nav.TButton", background=BG, foreground=MUTED, anchor="w", padding=(12, 14))
        style.map("Nav.TButton", background=[("active", "#242b3e")])
        style.configure("ActiveNav.TButton", background="#2e2249", foreground="#d9c8ff", anchor="w", padding=(12, 14))
        style.configure("TEntry", fieldbackground=PANEL, foreground=TEXT, insertcolor=TEXT,
                        padding=8, bordercolor="#30364b", lightcolor="#30364b", darkcolor="#30364b")
        style.configure("TCombobox", fieldbackground=PANEL, foreground=TEXT, padding=8,
                        background="#242b3e", arrowcolor=MUTED, bordercolor="#30364b", lightcolor="#30364b", darkcolor="#30364b")
        style.map("TCombobox", fieldbackground=[("readonly", PANEL)], foreground=[("readonly", TEXT)])
        style.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=TEXT,
                        rowheight=38, borderwidth=0, bordercolor=PANEL, lightcolor=PANEL, darkcolor=PANEL)
        style.configure("Treeview.Heading", background="#242b3e", foreground=MUTED, padding=10,
                        bordercolor=PANEL, lightcolor=PANEL, darkcolor=PANEL, relief="flat")
        style.map("Treeview", background=[("selected", "#3c2c61")])
        style.configure("TNotebook", borderwidth=0)
        style.layout("HDM.TNotebook.Tab", [])
        style.configure("HDM.TNotebook", borderwidth=0, tabmargins=0, bordercolor=BG, lightcolor=BG, darkcolor=BG)
        style.configure("Vertical.TScrollbar", background="#30364b", troughcolor=PANEL,
                        arrowcolor=MUTED, bordercolor=PANEL, lightcolor=PANEL, darkcolor=PANEL)
        style.configure("TNotebook.Tab", background=PANEL, foreground=MUTED, padding=(20, 12))
        style.map("TNotebook.Tab", background=[("selected", "#263d5c")], foreground=[("selected", TEXT)])
        self.root.option_add("*TCombobox*Listbox.background", PANEL)
        self.root.option_add("*TCombobox*Listbox.foreground", TEXT)

    def _layout(self):
        sidebar = ttk.Frame(self.root, padding=(16, 22), width=190)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        ttk.Label(sidebar, text=" HDM", image=self.brand_icons[1], compound="left",
                  foreground=TEXT, font=("Segoe UI", 24, "bold")).pack(anchor="w")
        ttk.Label(sidebar, text="Hngoos Download\nManager", style="Muted.TLabel", wraplength=150,
                  font=("Segoe UI", 9)).pack(anchor="w", padx=10, pady=(3, 28))
        shell = ttk.Frame(self.root, padding=(6, 22, 22, 18))
        shell.pack(side="left", fill="both", expand=True)
        header = ttk.Frame(shell)
        header.pack(fill="x", pady=(0, 12))
        self.page_title = tk.StringVar(value="Tải xuống")
        ttk.Label(header, textvariable=self.page_title, style="Title.TLabel").pack(side="left")
        ttk.Label(header, text=f"HDM {__version__}  ·  {platform_label()}", style="Muted.TLabel").pack(side="right")
        ttk.Label(shell, textvariable=self.status, style="Muted.TLabel", wraplength=1100).pack(side="bottom", fill="x", pady=(12, 0))
        tabs = ttk.Notebook(shell, style="HDM.TNotebook")
        tabs.pack(fill="both", expand=True)
        self.tabs = tabs
        downloads, media, safety, browser, tools, about = [ttk.Frame(tabs, padding=16) for _ in range(6)]
        self.media_tab = media
        nav_buttons = []
        for index, (tab, title, icon) in enumerate(zip((downloads, media, safety, browser, tools, about),
                              ("Tải xuống", "Video & nhạc", "An toàn", "Trình duyệt", "Công cụ", "Thông tin"),
                              ("download", "video", "shield", "globe", "settings", "info"), strict=True)):
            tabs.add(tab, text=title)
            button = ttk.Button(sidebar, text=title, image=self.icons[icon], compound="left",
                style="ActiveNav.TButton" if index == 0 else "Nav.TButton", command=lambda i=index: tabs.select(i))
            button.pack(fill="x", pady=4)
            nav_buttons.append(button)
        ttk.Label(sidebar, text="Tải. Sắp xếp. Hoàn tất.", style="Muted.TLabel", wraplength=150).pack(side="bottom", pady=12)
        def select_page(_event):
            selected = tabs.index(tabs.select())
            self.page_title.set(tabs.tab(selected, "text"))
            for index, button in enumerate(nav_buttons):
                button.configure(style="ActiveNav.TButton" if index == selected else "Nav.TButton")
        tabs.bind("<<NotebookTabChanged>>", select_page)
        self._downloads(downloads)
        self._media(self.scrollable(media))
        self._safety(self.scrollable(safety))
        self._browser(self.scrollable(browser))
        self._tools(tools)
        self._about(self.scrollable(about))

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
        from .widgets import QueueOverview
        self.overview = QueueOverview(parent)
        self.overview.pack(fill="x", pady=(0, 12))
        form = ttk.Frame(parent)
        form.pack(fill="x")
        form.columnconfigure(1, weight=1)
        ttk.Label(form, text="Đường dẫn").grid(row=0, column=0, sticky="w", padx=(0, 12))
        url_entry = ttk.Entry(form, textvariable=self.url)
        url_entry.grid(row=0, column=1, columnspan=3, sticky="ew")
        url_entry.bind("<Return>", lambda _event: self.add())
        ttk.Button(form, text="Dán", command=self.paste_url).grid(row=0, column=4, padx=(8, 0))
        ttk.Label(form, text="Tên tệp").grid(row=1, column=0, sticky="w", pady=8)
        ttk.Entry(form, textvariable=self.filename).grid(row=1, column=1, sticky="ew", pady=8)
        ttk.Label(form, text="Luồng").grid(row=1, column=2, padx=10)
        ttk.Combobox(form, textvariable=self.connections, values=(1, 2, 4, 8, 16, 32),
                     width=5, state="readonly").grid(row=1, column=3)
        ttk.Button(form, text="Thêm lượt tải", style="Primary.TButton", command=self.add).grid(
            row=1, column=4, padx=(8, 0))
        ttk.Label(form, text="Lưu tại").grid(row=2, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.directory).grid(row=2, column=1, columnspan=3, sticky="ew")
        ttk.Button(form, text="Chọn thư mục", command=self.choose_directory).grid(row=2, column=4, padx=(8, 0))
        self.advanced_options = ttk.Frame(form)
        advanced = self.advanced_options
        advanced.columnconfigure(1, weight=1)
        ttk.Label(advanced, text="Mã băm", width=10).grid(row=0, column=0, sticky="w", pady=8)
        ttk.Entry(advanced, textvariable=self.expected_hash).grid(row=0, column=1, sticky="ew", pady=8)
        ttk.Combobox(advanced, textvariable=self.hash_algorithm, values=("SHA-256", "MD5", "SHA-1", "SHA-512"),
                     width=11, state="readonly").grid(row=0, column=2, padx=(8, 0))
        ttk.Label(advanced, text="Mirror").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(advanced, textvariable=self.mirrors).grid(row=1, column=1, sticky="ew")
        ttk.Label(advanced, text="Link cách bởi dấu |", style="Muted.TLabel").grid(row=1, column=2, padx=8)
        def toggle_advanced():
            visible = bool(advanced.winfo_manager())
            if visible:
                advanced.grid_remove()
            else:
                advanced.grid(row=4, column=0, columnspan=5, sticky="ew")
            advanced_button.configure(text="Tùy chọn nâng cao  ▸" if visible else "Thu gọn tùy chọn  ▾")
        advanced_button = ttk.Button(form, text="Tùy chọn nâng cao  ▸", command=toggle_advanced)
        advanced_button.grid(row=3, column=0, columnspan=5, sticky="w", pady=(10, 0))
        actions = ttk.Frame(parent)
        actions.pack(fill="x", pady=(12, 12))
        self.transfer_button = ttk.Button(actions, text="Tiếp tục", command=self.toggle_transfer)
        self.transfer_button.pack(side="left", padx=(0, 8))
        for label, command in (("Nhập danh sách…", self.batch_dialog), ("Mở thư mục", self.open_folder)):
            ttk.Button(actions, text=label, command=command).pack(side="left", padx=(0, 8))
        bandwidth = ttk.Combobox(actions, textvariable=self.bandwidth_mode, state="readonly", width=18,
                                 values=("Tối đa", "Vừa (4 MB/s)", "Nhẹ (512 KB/s)"))
        bandwidth.pack(side="right")
        bandwidth.bind("<<ComboboxSelected>>", lambda _: self.manager.set_bandwidth(
            {"Tối đa": "maximum", "Vừa (4 MB/s)": "medium", "Nhẹ (512 KB/s)": "light"}[self.bandwidth_mode.get()]))
        columns = ("name", "status", "progress", "size", "speed")
        table_frame = ttk.Frame(parent)
        table_frame.pack(fill="both", expand=True)
        self.table = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse", height=4)
        for col, label, width in zip(columns, ("TÊN TỆP", "TRẠNG THÁI", "TIẾN ĐỘ", "ĐÃ TẢI / TỔNG", "TỐC ĐỘ"),
                                     (330, 125, 85, 180, 110)):
            self.table.heading(col, text=label)
            self.table.column(col, width=width, minwidth=65, stretch=col == "name")
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.table.pack(fill="both", expand=True)
        self.empty_state = ttk.Frame(table_frame, style="Card.TFrame", padding=(16, 12))
        ttk.Label(self.empty_state, image=self.icons["download"], background=PANEL).pack(pady=(0, 12))
        ttk.Label(self.empty_state, text="Bắt đầu lượt tải đầu tiên", background=PANEL,
                  font=("Segoe UI", 16, "bold")).pack()
        ttk.Label(self.empty_state, text="Dán đường dẫn ở trên hoặc nhập danh sách từ bảng tính.",
                  background=PANEL, foreground=MUTED).pack(pady=(8, 0))
        self.empty_state.place(relx=0.5, rely=0.56, anchor="center")
        self.table.bind("<<TreeviewSelect>>", self.show_details)
        self.table.bind("<Double-1>", lambda _: self.open_folder())
        self.table.bind("<Button-3>", self.context_menu)
        self.detail = tk.StringVar(value="Chọn một lượt tải để xem chi tiết. Bấm chuột phải để đổi link hoặc nơi lưu.")
        ttk.Label(parent, textvariable=self.detail, style="Muted.TLabel", wraplength=1000).pack(
            anchor="w", pady=(12, 0))

    def _media(self, parent):
        ttk.Label(parent, text="Lưu video hoặc tách MP3", font=("Segoe UI", 18, "bold")).pack(anchor="w", pady=(8, 12))
        ttk.Label(parent, text="Dùng yt-dlp tùy chọn. Chỉ tải nội dung bạn có quyền truy cập; không hỗ trợ DRM.",
                  style="Muted.TLabel", wraplength=900).pack(anchor="w", pady=(0, 20))
        self.media_url = tk.StringVar()
        ttk.Entry(parent, textvariable=self.media_url).pack(fill="x", pady=(0, 12))
        options = ttk.Frame(parent)
        options.pack(fill="x", pady=(0, 12))
        self.media_quality = tk.StringVar(value="1080")
        self.media_playlist = tk.BooleanVar()
        self.media_subtitles = tk.BooleanVar()
        self.media_cookie = tk.StringVar()
        ttk.Label(options, text="Độ cao tối đa").pack(side="left")
        ttk.Combobox(options, textvariable=self.media_quality, values=(360, 480, 720, 1080, 1440, 2160),
                     state="readonly", width=7).pack(side="left", padx=8)
        ttk.Checkbutton(options, text="Cả danh sách phát", variable=self.media_playlist).pack(side="left", padx=8)
        ttk.Checkbutton(options, text="Phụ đề vi/en", variable=self.media_subtitles).pack(side="left", padx=8)
        ttk.Button(options, text="Chọn cookie do bạn xuất…", command=self.choose_cookie).pack(side="right")
        actions = ttk.Frame(parent)
        actions.pack(fill="x")
        self.media_buttons = []
        for label, audio in (("Tải video", ""), ("Tải MP3", "mp3"), ("Tải M4A", "m4a")):
            button = ttk.Button(actions, text=label, style="Primary.TButton",
                                command=lambda a=audio: self.start_media(a))
            button.pack(side="left", padx=(0, 10))
            self.media_buttons.append(button)
        ttk.Button(actions, text="Xem định dạng", command=self.inspect_video).pack(side="left", padx=8)
        ttk.Button(actions, text="Dừng / bỏ link đang chọn", command=self.stop_media).pack(side="right")
        self.media_status = tk.StringVar(value="Lưu vào thư mục đã chọn ở thẻ Tải xuống.")
        ttk.Label(parent, textvariable=self.media_status, wraplength=950).pack(anchor="w", pady=20)
        ttk.Separator(parent).pack(fill="x", pady=12)
        ttk.Label(parent, text="Chuyển video sang MP4 H.264 / AAC", font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=12)
        ttk.Label(parent, text="Cần FFmpeg trong PATH. Tệp gốc được giữ lại; thao tác có thể mất vài phút.",
                  style="Muted.TLabel").pack(anchor="w", pady=(0, 12))
        ttk.Button(parent, text="Chọn video để chuyển…", command=self.convert).pack(anchor="w")
        ttk.Button(parent, text="Cắt / ghép / nén / tách nhạc…", command=self.media_tools).pack(anchor="w", pady=10)
        ttk.Button(parent, text="Cập nhật yt-dlp từ nguồn chính thức…", command=self.update_ytdlp).pack(anchor="w", pady=5)
        ttk.Label(parent, text='Cài hỗ trợ video: pip install ".[media,processing]"\nTệp cookie là tùy chọn; app không tự đọc tài khoản trình duyệt.',
                  style="Muted.TLabel").pack(anchor="w", pady=24)

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
                  "Yêu cầu được lưu trên máy. Chuyển phiên đăng nhập từ tiện ích hiện chỉ hỗ trợ Windows, với mã hóa DPAPI. Trên macOS/Linux, dùng tệp cookie bạn tự chọn trong mục Video & nhạc.",
                  wraplength=950, style="Muted.TLabel").pack(anchor="w", pady=16)
        ttk.Label(parent, text="Bộ lọc hỗ trợ quy tắc mạng, chặn tab quảng cáo đã nhận diện, chọn phần tử và thống kê. "
                  "Dùng popup để quản lý quyền, ngoại lệ và luồng HLS/DASH; một số cú pháp bộ lọc chưa được hỗ trợ.", wraplength=950, style="Muted.TLabel").pack(anchor="w", pady=12)

    def _tools(self, parent):
        parent = self.scrollable(parent)
        ttk.Label(parent, text="Tài liệu và tác vụ bổ sung", font=("Segoe UI", 18, "bold")).pack(anchor="w", pady=12)
        for label, callback in (("Che thông tin PDF bằng vùng kéo chuột…", self.redact_pdf),
                                ("Lưu trang web thành PDF / ảnh…", self.capture_dialog),
                                ("Cắt / ghép / nén video, nhạc…", self.media_tools),
                                ("Giải mã link Drive / Dropbox / OneDrive / MediaFire…", self.resolve_cloud),
                                ("Tiếp quản tệp trình duyệt tải dở…", self.adopt_partial),
                                ("Torrent / magnet — chọn từng tệp…", self.torrent_dialog),
                                ("Mở lại torrent đã lưu…", self.torrent_history),
                                ("Mở thư mục phiếu giao hàng…", self.open_invoices),
                                ("Giải nén ZIP sau khi kiểm tra…", self.extract_zip),
                                ("Tìm phụ đề Việt khớp tệp phim…", self.find_subtitle),
                                ("Xuất lịch sử tải CSV…", self.export_history)):
            ttk.Button(parent, text=label, command=callback).pack(anchor="w", pady=7)
        ttk.Button(parent, text="Kiểm tra bản cập nhật ký số…", command=self.check_update).pack(anchor="w", pady=7)
        ttk.Button(parent, text="Xuất báo cáo danh sách từng dòng…", command=self.export_batch_report).pack(anchor="w", pady=7)
        self.auto_category = tk.BooleanVar(value=self.store.setting("auto_category", False))
        ttk.Checkbutton(parent, text="Tự chia thư mục Video / Music / Images / Documents / Archives cho lượt tải mới",
                        variable=self.auto_category, command=lambda: self.store.set_setting("auto_category", self.auto_category.get())).pack(anchor="w", pady=15)
        self.auto_extract = tk.BooleanVar(value=self.store.setting("auto_extract", False))
        ttk.Checkbutton(parent, text="Tự giải nén ZIP sau khi tải và kiểm tra an toàn thành công",
                        variable=self.auto_extract, command=lambda: self.store.set_setting(
                            "auto_extract", self.auto_extract.get())).pack(anchor="w", pady=6)
        self.close_to_tray = tk.BooleanVar(value=self.store.setting("close_to_tray", False))
        ttk.Checkbutton(parent, text="Thu xuống khay hệ thống khi đóng cửa sổ (dùng menu khay để thoát)",
                        variable=self.close_to_tray, command=lambda: self.store.set_setting("close_to_tray", self.close_to_tray.get())).pack(anchor="w", pady=6)
        self.shutdown_after = tk.BooleanVar()
        ttk.Checkbutton(parent, text="Tắt máy sau khi các lượt HTTP đang chờ đều hoàn tất (đếm ngược 60 giây)",
                        state="normal" if os.name == "nt" else "disabled",
                        variable=self.shutdown_after, command=lambda: setattr(self, "power_seen_work", False)).pack(anchor="w", pady=6)
        if os.name == "nt":
            ttk.Button(parent, text="Hủy lệnh tắt máy đã hẹn", command=self.cancel_shutdown).pack(anchor="w", pady=6)

    def _about(self, parent):
        ttk.Label(parent, text=f"hngoos-download-manager {__version__}", font=("Segoe UI", 18, "bold")).pack(anchor="w", pady=12)
        paragraphs = [
            "HDM là ứng dụng quản lý tải cho Windows, macOS và Linux, tích hợp các trình duyệt nhân Chromium.",
            (f"HDM v{__version__}: giao diện với Morphicons, bộ nhớ tải HTTP cục bộ, tiếp quản lượt tải trình duyệt, "
             "khôi phục torrent, nén video hai lượt và lưu phiếu in thử nghiệm."),
            ("Máy chủ không có ETag mạnh hoặc không cho tải theo Range sẽ dùng một luồng. "
             "Nếu không xác minh được nội dung cũ, ứng dụng tải lại từ đầu để tránh ghép sai tệp."),
            "HDM giúp tải, quản lý và xử lý tệp trên máy của bạn. Các công cụ có điều kiện hỗ trợ riêng theo nền tảng, máy chủ và định dạng.",
            "Biểu tượng dùng Morphicons kết hợp Lucide. Thiết kế giao diện tham khảo React Bits."
        ]
        for paragraph in paragraphs:
            ttk.Label(parent, text=paragraph, wraplength=950, style="Muted.TLabel").pack(anchor="w", pady=10)
        ttk.Button(parent, text="Mở GitHub", command=lambda: webbrowser.open(
            "https://github.com/hngoos/hngoos-download-manager")).pack(anchor="w", pady=12)

    def guarded(self, action):
        try:
            return action()
        except Exception as exc:  # noqa: BLE001 -- UI boundary must display worker/input errors.
            messagebox.showerror("HDM", str(exc), parent=self.root)

    def open_invoices(self):
        folder = self.data_dir/"invoices"
        folder.mkdir(parents=True, exist_ok=True)
        self.guarded(lambda: open_path(folder))

    def add(self):
        def action():
            url = self.url.get().strip()
            digest = self.expected_hash.get().strip()
            algorithm = self.hash_algorithm.get().lower().replace("-", "")
            self.manager.add(url, self.directory.get(), self.filename.get() or filename_from_url(url),
                             int(self.connections.get()), digest if algorithm == "sha256" else "",
                             expected_hashes={algorithm: digest} if digest else {},
                             mirrors=[value.strip() for value in self.mirrors.get().split("|") if value.strip()])
            self.url.set("")
            self.filename.set("")
            self.expected_hash.set("")
            self.mirrors.set("")
        self.guarded(action)

    def choose_directory(self):
        folder = filedialog.askdirectory(initialdir=self.directory.get())
        if folder:
            self.directory.set(folder)

    def paste_url(self):
        self.guarded(lambda: self.url.set(self.root.clipboard_get().strip()))

    def selected(self):
        selected = self.table.selection()
        return selected[0] if selected else None

    def resume(self):
        if job_id := self.selected():
            self.manager.start(job_id)

    def pause(self):
        if job_id := self.selected():
            self.manager.pause(job_id)

    def open_folder(self):
        job = self.store.get(self.selected()) if self.selected() else None
        folder = Path(job["directory"] if job else self.directory.get())
        if folder.exists():
            self.guarded(lambda: open_path(folder))

    def show_details(self, _event=None):
        if job_id := self.selected():
            job = self.store.get(job_id)
            self.detail.set(job["error"] or job["output"] or f"Lưu tại: {job['directory']}")

    def context_menu(self, event):
        row = self.table.identify_row(event.y)
        if not row:
            return
        self.table.selection_set(row)
        job = self.store.get(row)
        menu = tk.Menu(self.root, tearoff=False, bg=PANEL, fg=TEXT)
        if job["state"] in {"paused", "error"}:
            menu.add_command(label="Tiếp tục tải", command=self.resume)
            menu.add_command(label="Thay link tải…", command=self.replace_url_dialog)
            menu.add_command(label="Đổi thư mục lưu…", command=self.relocate)
        if job["state"] in {"downloading", "queued", "verifying"}:
            menu.add_command(label="Tạm dừng", command=self.pause)
            menu.add_command(label="Đổi nơi lưu trong lúc tải…", command=self.relocate)
        if job["state"] in {"paused", "error", "scheduled"}:
            menu.add_command(label="Hẹn giờ tải…", command=self.schedule_dialog)
        menu.add_command(label="Mở thư mục", command=self.open_folder)
        if job["sha256"]:
            menu.add_command(label="Chép SHA-256", command=lambda: self.copy(job["sha256"]))
        if job["state"] == "quarantined":
            menu.add_command(label="Khôi phục tên gốc…", command=self.restore_dialog)
        if job["output"] and Path(job["filename"]).suffix.lower() in {".mp4", ".mkv", ".webm", ".mov", ".mp3", ".m4a", ".wav", ".flac"}:
            menu.add_command(label="Cắt / ghép / nén…", command=lambda: self.media_tools(job["output"]))
        menu.add_command(label="Nhật ký lượt tải…", command=self.job_log)
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

    def start_media(self, audio):
        from .media import MediaOptions, download_video
        url, directory = self.media_url.get(), self.directory.get()
        if getattr(self, "media_busy", False):
            return
        self.media_busy = True
        self.media_stop.clear()
        options = MediaOptions(height=int(self.media_quality.get()), audio=audio,
                               playlist=self.media_playlist.get(), subtitles=self.media_subtitles.get(),
                               cookie_file=self.media_cookie.get())
        if url == self.browser_session_url:
            options.referrer = getattr(self, "browser_referrer", "")
        session = self.browser_session if url == self.browser_session_url else ""
        if session:
            self.browser_session = ""
            self.browser_session_url = ""
        for button in self.media_buttons:
            button.configure(state="disabled")
        self.media_status.set("Đang lấy thông tin và tải…")
        def action():
            try:
                Path(directory).mkdir(parents=True, exist_ok=True)
                def progress(data):
                    text = data.get("_percent_str", data["status"])
                    self.events.put(lambda: self.media_status.set(f"Video: {text}"))
                if session:
                    import tempfile

                    from .vault import cookie_jar, decrypt
                    with tempfile.TemporaryDirectory(prefix="hngoos-session-", dir=self.data_dir) as temporary:
                        cookie_path = Path(temporary)/"cookies.txt"
                        cookie_path.write_text(cookie_jar(decrypt(session)), encoding="utf-8")
                        options.cookie_file = str(cookie_path)
                        download_video(url, directory, progress=progress, options=options, stop=self.media_stop)
                else:
                    download_video(url, directory, progress=progress, options=options, stop=self.media_stop)
                return directory
            finally:
                self.events.put(reset)
        def reset():
            self.media_busy = False
            self.video_inbox_busy = False
            for button in self.media_buttons:
                button.configure(state="normal")
        self.background(action, lambda folder: self.media_status.set(f"Đã tải xong vào: {folder}"))

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
        import json

        from .media import MediaOptions, inspect_video
        options = MediaOptions(playlist=self.media_playlist.get(), cookie_file=self.media_cookie.get())
        url = self.media_url.get()
        def show(info):
            dialog = tk.Toplevel(self.root)
            dialog.title("Thông tin video / danh sách phát")
            editor = tk.Text(dialog, width=100, height=30, bg=PANEL, fg=TEXT)
            editor.pack(fill="both", expand=True)
            editor.insert("1.0", json.dumps(info, ensure_ascii=False, indent=2))
            editor.configure(state="disabled")
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

    def check_update(self):
        if os.name != "nt":
            messagebox.showinfo("Cập nhật HDM", "Bản preview macOS/Linux được cập nhật bằng cách chạy lại install.sh. Bộ cập nhật trong ứng dụng hiện dành cho Windows.", parent=self.root)
            return
        from .updater import check_update, download_installer
        def found(payload):
            if not payload:
                messagebox.showinfo("Cập nhật", "Bạn đang dùng phiên bản mới nhất.", parent=self.root)
                return
            if messagebox.askyesno("Cập nhật ký số", f"Có bản {payload['version']} với chữ ký hợp lệ. Tải bộ cài?", parent=self.root):
                self.background(lambda: download_installer(payload, self.data_dir/"updates"),
                                lambda path: messagebox.showinfo("Đã xác minh bộ cài", f"Bộ cài đã được kiểm chữ ký manifest và mã băm:\n{path}\nMở bộ cài từ thư mục khi bạn sẵn sàng.", parent=self.root))
        self.background(check_update, found)

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
                    self.tabs.select(self.media_tab)
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
        self.overview.update_values(sum(job["state"] == "downloading" for job in jobs),
            sum(job["state"] == "complete" for job in jobs), human(sum(job.get("speed", 0) for job in jobs))+"/s")
        if jobs:
            self.empty_state.place_forget()
        elif not self.empty_state.winfo_manager():
            self.empty_state.place(relx=0.5, rely=0.56, anchor="center")
        chosen = self.table.selection()
        current = next((job for job in jobs if chosen and job["id"] == chosen[0]), None)
        active = bool(current and current["state"] in {"queued", "downloading", "verifying"})
        self.transfer_button.configure(text="Tạm dừng" if active else "Tiếp tục")
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
            values = (job["filename"], STATES.get(job["state"], job["state"]), progress,
                      f"{human(job['downloaded'])} / {human(job['total']) if job['total'] else '?'}",
                      f"{human(job['speed'])}/s" if job["speed"] else "—")
            if self.last_jobs.get(job["id"]) != values:
                if self.table.exists(job["id"]):
                    self.table.item(job["id"], values=values)
                else:
                    self.table.insert("", 0, iid=job["id"], values=values)
                self.last_jobs[job["id"]] = values
        self.show_details()
        self.root.after(500, self.refresh)

    def toggle_transfer(self):
        def action():
            job_id = self.selected()
            if self.store.get(job_id)["state"] in {"queued", "downloading", "verifying"}:
                self.manager.pause(job_id)
            else:
                self.manager.start(job_id)
        self.guarded(action)

    def close(self):
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
