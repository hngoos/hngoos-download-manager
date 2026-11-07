"""File metadata and selectable output formats in the right-hand card."""

import tkinter as tk
from pathlib import Path
from tkinter import ttk

from .rounded import ChoiceRow, RoundedEntry
from .safety import filename_from_url


class DownloadEditor(ttk.Frame):
    def __init__(self, app, description):
        super().__init__(app.source_content, style="Card.TFrame")
        self.app, self.description = app, description
        self.resize_timer = None
        self.bind("<Destroy>", self.cancel_resize, add="+")
        self.original, self.kind, self.resolved = (description[key] for key in ("original", "kind", "url"))
        self.ready = self.kind in {"file", "media"} and not description.get("metadata_error")
        import mimetypes
        content_type = description.get("content_type") or mimetypes.guess_type(description.get("filename", ""))[0] or ""
        self.show_options = self.kind == "media" or content_type.startswith(("video/", "audio/", "image/"))
        if self.show_options and not app.page_stack:
            app.url_panel.grid()
        else:
            app.url_panel.grid_remove()
        if self.kind != "empty" and getattr(app, "download_placeholder", None):
            app.download_placeholder.pack_forget()
        self.filename = tk.StringVar(value=(description.get("filename") or filename_from_url(self.resolved)) if self.kind != "empty" else "")
        self.name = tk.StringVar(value=Path(self.filename.get()).stem)
        self.extension = tk.StringVar(value=Path(self.filename.get()).suffix)
        self.syncing_name = False
        self.name_traces = [(self.filename, self.filename.trace_add("write", self.sync_filename)),
                            (self.name, self.name.trace_add("write", self.rename))]
        self.base_name = self.filename.get()
        self.directory = app.directory
        self.connections = tk.StringVar(value=app.connections.get())
        self.format = tk.StringVar(value="MP4")
        self.quality = tk.StringVar(value=app.media_quality.get())
        self.bitrate = tk.StringVar(value=app.media_bitrate.get() if hasattr(app, "media_bitrate") else "320")
        self.playlist = tk.BooleanVar(value=app.media_playlist.get())
        self.subtitles = tk.BooleanVar(value=app.media_subtitles.get())
        self.cookie = tk.StringVar(value=app.media_cookie.get())
        self.format_id = tk.StringVar(value=app.media_format.get())
        self.digest, self.mirrors = tk.StringVar(), tk.StringVar()
        self.algorithm = tk.StringVar(value="SHA-256")
        self.error = tk.StringVar()
        self.columnconfigure(1, weight=1)
        name_row = ttk.Frame(self, style="Card.TFrame")
        name_row.grid(row=0, column=0, columnspan=2, sticky="ew", pady=4)
        name_row.columnconfigure(1, weight=1)
        ttk.Label(name_row, text="Tệp:", style="Source.Card.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.name_entry = RoundedEntry(name_row, textvariable=self.name, suffix=self.extension, font=("Segoe UI", 13))
        self.name_entry.grid(row=0, column=1, sticky="ew")
        self.name_entry.bind("<Return>", lambda _: app.submit_download())
        if description.get("metadata_error"):
            self.filename.set("")
            ttk.Label(self, text=app.locale.text("Không lấy được tên tệp từ nguồn. Hãy thử lại hoặc kiểm tra quyền truy cập."),
                      style="Card.TLabel", wraplength=900).grid(row=1, column=0, columnspan=2, sticky="w", pady=8)
        self.name_entry.configure(state="normal" if self.ready else "disabled")
        self.heights = sorted({int(height) for height in description.get("heights", []) if height}, reverse=True)
        if self.heights:
            self.quality.set(str(min(self.heights, key=lambda height: abs(height-int(self.quality.get())))))
        self.source_formats = [item for item in description.get("formats", [])
            if item.get("ext") and not item.get("has_drm")
            and (item.get("vcodec") != "none" or item.get("acodec") != "none")]
        if self.kind == "media" and not self.source_formats and self.heights:
            self.source_formats = [{"ext": Path(self.filename.get()).suffix.lstrip(".") or "mp4",
                                    "height": height, "vcodec": "unknown"} for height in self.heights]
        available = list(dict.fromkeys(item["ext"].upper() for item in self.source_formats)) if self.kind == "media" else ["Original"]
        available.sort(key=lambda ext: not any(item["ext"].upper() == ext and item.get("height") for item in self.source_formats))
        if self.kind == "media" and any(item.get("acodec") not in {None, "none"} for item in self.source_formats):
            available.append("MP3")
        self.format.set(available[0] if available else "Original")
        ttk.Label(self, text="Định dạng", style="Source.Card.TLabel").grid(row=2, column=0, sticky="nw", pady=18, padx=(0, 12))
        self.format_choices = ChoiceRow(self, self.format,
            [("Gốc" if value == "Original" else value, value) for value in available], self.format_changed, app)
        self.size_choices(self.format_choices)
        self.format_choices.grid(row=2, column=1, sticky="ew", pady=8)
        if self.kind == "media":
            self.media_controls = self.format_choices
        for button in self.format_choices.buttons.values():
            button.configure(state="normal" if self.ready else "disabled")
        self.format_choices.present()
        self.quality_label = ttk.Label(self, text="Chất lượng", style="Source.Card.TLabel")
        self.quality_label.grid(row=3, column=0, sticky="nw", pady=18, padx=(0, 12))
        self.quality_choices = None
        self.format_changed()
        self.error_label = ttk.Label(self, textvariable=self.error, style="Card.TLabel", wraplength=600)
        self.error_label.grid(row=5, column=0, columnspan=2, sticky="w")
        self.confirm_button = app.download_button
        app.apply_preferences()

    def size_choices(self, choices):
        for value, button in choices.buttons.items():
            button.label_font.configure(size=12)
            width = max(84, button.label_font.measure(self.app.locale.text(button.label))+32)
            choices.widths[value] = width
            button.configure(width=width, height=44)

    def sync_filename(self, *_args):
        if not self.syncing_name:
            self.syncing_name = True
            value = self.filename.get()
            self.name.set(Path(value).stem if value else "")
            self.extension.set(Path(value).suffix if value else "")
            self.syncing_name = False

    def rename(self, *_args):
        if not self.syncing_name:
            self.syncing_name = True
            self.filename.set(self.name.get()+self.extension.get() if self.name.get() else "")
            self.syncing_name = False

    def format_changed(self, _event=None):
        self.current_formats = [item for item in self.source_formats if item["ext"].upper() == self.format.get()]
        video = any(item.get("height") and item.get("vcodec") != "none" for item in self.current_formats)
        self.video_output = video
        if self.quality_choices is not None:
            self.quality_choices.destroy()
        if video:
            heights = sorted({int(item.get("quality") or item["height"]) for item in self.current_formats if item.get("height")}, reverse=True)
            values = [(f"{height}p", str(height)) for height in heights]
            if self.quality.get() not in {value for _, value in values}:
                self.quality.set(str(max(heights)))
        else:
            rates = ([320, 256, 192, 128] if self.format.get() == "MP3" else
                     sorted({round(item["abr"]) for item in self.current_formats if item.get("abr")}, reverse=True))
            values = [(f"{rate} kbps", str(rate)) for rate in rates]
            if rates and self.bitrate.get() not in {value for _, value in values}:
                self.bitrate.set(str(max(rates)))
        self.quality_label.grid() if values else self.quality_label.grid_remove()
        self.quality_choices = ChoiceRow(self, self.quality if video else self.bitrate, values,
                                         self.select_source_format, self.app)
        self.size_choices(self.quality_choices)
        self.quality_choices.grid(row=3, column=1, sticky="ew", pady=8)
        for button in self.quality_choices.buttons.values():
            button.configure(state="normal" if self.ready and self.kind == "media" else "disabled")
        self.quality_choices.present()
        if self.ready and self.kind == "media":
            self.filename.set(str(Path(self.filename.get() or self.base_name).with_suffix("."+self.format.get().lower())))
        if not video:
            self.subtitles.set(False)
        self.select_source_format()
        if self.resize_timer:
            self.after_cancel(self.resize_timer)
        self.resize_timer = self.after_idle(self.resize_card)

    def select_source_format(self):
        matches = [item for item in self.current_formats if
            (self.video_output and (item.get("quality") or item.get("height")) == int(self.quality.get())) or
            (not self.video_output and (not item.get("abr") or round(item["abr"]) == int(self.bitrate.get())))]
        chosen = max(matches, key=lambda item: item.get("tbr") or item.get("abr") or 0, default={})
        selected = str(chosen.get("format_id") or "")
        if selected and self.video_output and chosen.get("acodec") == "none":
            audio_ext = "m4a" if self.format.get() == "MP4" else self.format.get().lower()
            audio = [item for item in self.source_formats if item.get("vcodec") == "none" and item["ext"] == audio_ext]
            track = max(audio, key=lambda item: item.get("abr") or 0, default={})
            if track.get("format_id"):
                selected += "+"+str(track["format_id"])
        self.format_id.set(selected)

    def resize_card(self):
        self.resize_timer = None
        self.app.resize_source_card()

    def cancel_resize(self, event):
        if event.widget == self:
            if self.resize_timer:
                self.after_cancel(self.resize_timer)
                self.resize_timer = None
            for variable, trace in self.name_traces:
                variable.trace_remove("write", trace)

    def confirm(self):
        app = self.app
        if not self.ready:
            return
        if app.url.get().strip() != self.original:
            self.error.set(app.locale.text("Link đã thay đổi; nhấn Enter để nhận diện lại."))
            return
        if not self.filename.get() or self.description.get("metadata_error"):
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
            if not hasattr(app, "media_bitrate"):
                app.media_bitrate = tk.StringVar(master=app.root, value="320")
            for target, source in ((app.media_quality, self.quality), (app.media_playlist, self.playlist),
                    (app.media_subtitles, self.subtitles), (app.media_cookie, self.cookie),
                    (app.media_format, self.format_id), (app.media_bitrate, self.bitrate)):
                target.set(source.get())
        source = self.kind, self.resolved
        app.dismiss_download()
        app.add(resolved_source=source)
