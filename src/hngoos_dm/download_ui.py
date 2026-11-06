"""Source-specific details revealed inline after Enter, with a pinned download action."""

import tkinter as tk
from tkinter import filedialog, ttk

from .safety import filename_from_url


class DownloadEditor(ttk.Frame):
    def __init__(self, app, description):
        super().__init__(app.editor_panel.content, style="Card.TFrame")
        self.app, self.description = app, description
        self.original, self.kind, self.resolved = (description[key] for key in ("original", "kind", "url"))
        kind, resolved = self.kind, self.resolved
        actions = ttk.Frame(self, style="Card.TFrame")
        actions.pack(side="bottom", fill="x", pady=(8, 0))
        ttk.Button(actions, text="Hủy", command=app.dismiss_download).pack(side="right", padx=8)
        self.confirm_button = ttk.Button(actions, text="Tải xuống", style="Primary.TButton", command=self.confirm)
        self.confirm_button.pack(side="right")
        self.error = tk.StringVar()
        ttk.Label(actions, textvariable=self.error, style="Muted.TLabel", wraplength=600).pack(side="left")
        self.filename = tk.StringVar(value=description.get("filename", "" if kind == "media" else filename_from_url(resolved)))
        self.directory = tk.StringVar(value=app.directory.get())
        self.connections = tk.StringVar(value=app.connections.get())
        self.format = tk.StringVar(value="MP4")
        self.quality = tk.StringVar(value=app.media_quality.get())
        self.playlist, self.subtitles = tk.BooleanVar(), tk.BooleanVar()
        self.digest, self.mirrors, self.cookie, self.format_id = (tk.StringVar() for _ in range(4))
        self.algorithm = tk.StringVar(value="SHA-256")
        frame = app.scrollable(self)
        frame.columnconfigure(1, weight=1)
        ttk.Label(frame, text="Link tệp").grid(row=0, column=0, sticky="w", padx=(0, 12))
        self.source_url = tk.StringVar(value=self.original)
        ttk.Entry(frame, textvariable=self.source_url, state="readonly").grid(
            row=0, column=1, columnspan=2, sticky="ew", pady=(0, 6))
        ttk.Label(frame, text="Tên tệp").grid(row=1, column=0, sticky="w", padx=(0, 12))
        ttk.Entry(frame, textvariable=self.filename).grid(row=1, column=1, columnspan=2, sticky="ew", pady=6)
        ttk.Label(frame, text="Lưu tại").grid(row=3, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.directory).grid(row=3, column=1, sticky="ew", pady=8)
        ttk.Button(frame, text="Chọn thư mục", command=self.choose_directory).grid(row=3, column=2, padx=(8, 0))
        advanced = self.advanced = ttk.Frame(frame)
        advanced.columnconfigure(1, weight=1)
        ttk.Label(advanced, text="Luồng").grid(row=0, column=0, sticky="w")
        ttk.Combobox(advanced, textvariable=self.connections, values=(1, 2, 4, 8, 16, 32),
                     width=6, state="readonly").grid(row=0, column=1, sticky="w", pady=8)
        if kind == "media":
            self.media_controls = ttk.Frame(advanced)
            self.media_controls.grid(row=1, column=0, columnspan=3, sticky="ew", pady=12)
            ttk.Label(self.media_controls, text="Định dạng").grid(row=0, column=0, sticky="w", padx=(0, 16))
            formats = ttk.Combobox(self.media_controls, textvariable=self.format,
                                  values=("MP4", "MP3", "M4A"), width=10, state="readonly")
            formats.grid(row=0, column=1, sticky="w", pady=6)
            self.quality_label = ttk.Label(self.media_controls, text="Độ cao tối đa")
            self.quality_label.grid(row=1, column=0, sticky="w")
            self.quality_selector = ttk.Combobox(self.media_controls, textvariable=self.quality,
                values=(360, 480, 720, 1080, 1440, 2160), width=10, state="readonly")
            self.quality_selector.grid(row=1, column=1, sticky="w", pady=6)
            ttk.Checkbutton(self.media_controls, text="Cả danh sách phát", variable=self.playlist).grid(
                row=2, column=0, columnspan=2, sticky="w", pady=6)
            self.subtitle_control = ttk.Checkbutton(self.media_controls, text="Phụ đề vi/en", variable=self.subtitles)
            self.subtitle_control.grid(row=3, column=0, columnspan=2, sticky="w")
            formats.bind("<<ComboboxSelected>>", self.format_changed)
        def toggle():
            if advanced.winfo_manager():
                advanced.grid_remove()
            else:
                advanced.grid(row=7, column=0, columnspan=3, sticky="ew", pady=8)
        self.toggle_advanced = toggle
        ttk.Button(actions, text="Tùy chọn nâng cao  ▸", command=toggle).pack(side="left")
        if kind == "media":
            ttk.Button(advanced, text="Chọn cookie do bạn xuất…", command=self.choose_cookie).grid(
                row=2, column=0, columnspan=2, sticky="w")
            ttk.Label(advanced, text="Format ID").grid(row=3, column=0, sticky="w", padx=(0, 10))
            ttk.Entry(advanced, textvariable=self.format_id).grid(row=3, column=1, sticky="ew", pady=8)
        else:
            ttk.Label(advanced, text="Mã băm").grid(row=2, column=0, sticky="w", padx=(0, 10))
            ttk.Entry(advanced, textvariable=self.digest).grid(row=2, column=1, sticky="ew")
            ttk.Combobox(advanced, textvariable=self.algorithm, values=("SHA-256", "MD5", "SHA-1", "SHA-512"),
                         width=10, state="readonly").grid(row=2, column=2, padx=8)
            ttk.Label(advanced, text="Mirror").grid(row=3, column=0, sticky="w")
            ttk.Entry(advanced, textvariable=self.mirrors).grid(row=3, column=1, columnspan=2, sticky="ew", pady=8)
            ttk.Label(advanced, text="Link cách bởi dấu |", style="Muted.TLabel").grid(row=4, column=1, sticky="w")
        app.apply_preferences()

    def format_changed(self, _event=None):
        video = self.format.get() == "MP4"
        for widget in (self.quality_label, self.quality_selector, self.subtitle_control):
            widget.grid() if video else widget.grid_remove()
        if not video:
            self.subtitles.set(False)

    def choose_directory(self):
        folder = filedialog.askdirectory(parent=self.app.root, initialdir=self.directory.get())
        if folder:
            self.directory.set(folder)

    def choose_cookie(self):
        path = filedialog.askopenfilename(parent=self.app.root, title="Cookie", filetypes=[("Netscape cookies", "*.txt")])
        if path:
            self.cookie.set(path)

    def confirm(self):
        app = self.app
        if app.url.get().strip() != self.original:
            self.error.set(app.locale.text("Link đã thay đổi; nhấn Enter để nhận diện lại."))
            return
        if not self.directory.get().strip():
            self.error.set(app.locale.text("Chọn thư mục lưu trước khi tải."))
            return
        for target, source in ((app.filename, self.filename), (app.directory, self.directory),
                (app.connections, self.connections), (app.expected_hash, self.digest),
                (app.hash_algorithm, self.algorithm), (app.mirrors, self.mirrors)):
            target.set(source.get())
        app.download_format.set(self.format.get() if self.kind == "media" else "Original")
        app.store.set_setting("download_directory", self.directory.get())
        if self.kind == "media":
            for target, source in ((app.media_quality, self.quality), (app.media_playlist, self.playlist),
                    (app.media_subtitles, self.subtitles), (app.media_cookie, self.cookie),
                    (app.media_format, self.format_id)):
                target.set(source.get())
        source = self.kind, self.resolved
        app.dismiss_download()
        app.add(resolved_source=source)
