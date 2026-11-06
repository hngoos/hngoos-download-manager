"""Source-specific confirmation; the main window remains a simple download queue."""

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .safety import filename_from_url


class DownloadDialog(tk.Toplevel):
    def __init__(self, app, original, kind, resolved):
        super().__init__(app.root)
        self.app, self.original, self.kind, self.resolved = app, original, kind, resolved
        self.title(app.locale.text("Tải xuống"))
        self.transient(app.root)
        self.resizable(True, False)
        self.geometry("720x560" if kind == "media" else "720x430")
        self.minsize(640, 400)
        self.filename = tk.StringVar(value="" if kind == "media" else filename_from_url(resolved))
        self.directory = tk.StringVar(value=app.directory.get())
        self.connections = tk.StringVar(value=app.connections.get())
        self.format = tk.StringVar(value="MP4")
        self.quality = tk.StringVar(value=app.media_quality.get())
        self.playlist, self.subtitles = tk.BooleanVar(), tk.BooleanVar()
        self.digest, self.mirrors, self.cookie, self.format_id = (tk.StringVar() for _ in range(4))
        self.algorithm = tk.StringVar(value="SHA-256")
        frame = ttk.Frame(self, padding=24)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(1, weight=1)
        ttk.Label(frame, text="Video / nhạc" if kind == "media" else "Tệp gốc",
                  font=("Segoe UI", 18, "bold")).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 16))
        # Do not expose signed URL tokens in labels or diagnostics.
        ttk.Label(frame, text="Tên tệp").grid(row=1, column=0, sticky="w", padx=(0, 12))
        ttk.Entry(frame, textvariable=self.filename).grid(row=1, column=1, columnspan=2, sticky="ew", pady=6)
        if kind == "media":
            ttk.Label(frame, text="Để trống để dùng tiêu đề gốc.", style="Muted.TLabel").grid(
                row=2, column=1, columnspan=2, sticky="w")
        ttk.Label(frame, text="Lưu tại").grid(row=3, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.directory).grid(row=3, column=1, sticky="ew", pady=8)
        ttk.Button(frame, text="Chọn thư mục", command=self.choose_directory).grid(row=3, column=2, padx=(8, 0))
        ttk.Label(frame, text="Luồng").grid(row=4, column=0, sticky="w")
        ttk.Combobox(frame, textvariable=self.connections, values=(1, 2, 4, 8, 16, 32),
                     width=6, state="readonly").grid(row=4, column=1, sticky="w", pady=8)
        if kind == "media":
            self.media_controls = ttk.Frame(frame)
            self.media_controls.grid(row=5, column=0, columnspan=3, sticky="ew", pady=12)
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
        advanced = ttk.Frame(frame)
        advanced.columnconfigure(1, weight=1)
        def toggle():
            if advanced.winfo_manager():
                advanced.grid_remove()
            else:
                advanced.grid(row=7, column=0, columnspan=3, sticky="ew", pady=8)
            self.update_idletasks()
            self.geometry(f"{self.winfo_width()}x{frame.winfo_reqheight()}")
        ttk.Button(frame, text="Tùy chọn nâng cao  ▸", command=toggle).grid(
            row=6, column=0, columnspan=3, sticky="w", pady=8)
        if kind == "media":
            ttk.Button(advanced, text="Chọn cookie do bạn xuất…", command=self.choose_cookie).grid(
                row=0, column=0, columnspan=2, sticky="w")
            ttk.Label(advanced, text="Format ID").grid(row=1, column=0, sticky="w", padx=(0, 10))
            ttk.Entry(advanced, textvariable=self.format_id).grid(row=1, column=1, sticky="ew", pady=8)
        else:
            ttk.Label(advanced, text="Mã băm").grid(row=0, column=0, sticky="w", padx=(0, 10))
            ttk.Entry(advanced, textvariable=self.digest).grid(row=0, column=1, sticky="ew")
            ttk.Combobox(advanced, textvariable=self.algorithm, values=("SHA-256", "MD5", "SHA-1", "SHA-512"),
                         width=10, state="readonly").grid(row=0, column=2, padx=8)
            ttk.Label(advanced, text="Mirror").grid(row=1, column=0, sticky="w")
            ttk.Entry(advanced, textvariable=self.mirrors).grid(row=1, column=1, columnspan=2, sticky="ew", pady=8)
            ttk.Label(advanced, text="Link cách bởi dấu |", style="Muted.TLabel").grid(row=2, column=1, sticky="w")
        ttk.Label(frame, text="Số kết nối tùy nguồn. Tệp tải về được kiểm tra trước khi hoàn tất.",
                  style="Muted.TLabel", wraplength=640).grid(row=8, column=0, columnspan=3, sticky="w", pady=12)
        actions = ttk.Frame(frame)
        actions.grid(row=9, column=0, columnspan=3, sticky="e", pady=(8, 0))
        ttk.Button(actions, text="Hủy", command=self.destroy).pack(side="left", padx=8)
        ttk.Button(actions, text="Tải xuống", style="Primary.TButton", command=self.confirm).pack(side="left")
        self.bind("<Escape>", lambda _: self.destroy())
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        app.apply_preferences()
        self.update_idletasks()
        self.geometry(f"720x{max(400, frame.winfo_reqheight())}")
        self.grab_set()

    def format_changed(self, _event=None):
        video = self.format.get() == "MP4"
        for widget in (self.quality_label, self.quality_selector, self.subtitle_control):
            widget.grid() if video else widget.grid_remove()
        if not video:
            self.subtitles.set(False)

    def choose_directory(self):
        folder = filedialog.askdirectory(parent=self, initialdir=self.directory.get())
        if folder:
            self.directory.set(folder)

    def choose_cookie(self):
        path = filedialog.askopenfilename(parent=self, title="Cookie", filetypes=[("Netscape cookies", "*.txt")])
        if path:
            self.cookie.set(path)

    def confirm(self):
        app = self.app
        if app.url.get().strip() != self.original:
            messagebox.showinfo("HDM", app.locale.text("Link đã thay đổi; bấm tải lại để dùng link mới."), parent=self)
            self.destroy()
            return
        if not self.directory.get().strip():
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
        self.destroy()
        app.add(resolved_source=(self.kind, self.resolved))
