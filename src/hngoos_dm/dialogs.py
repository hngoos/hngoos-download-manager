"""Desktop tools with functional inputs and background execution."""

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk


def media_tools(app, initial=None):
    dialog = tk.Toplevel(app.root)
    dialog.title(app.locale.text("Cắt / ghép / nén video, nhạc"))
    dialog.geometry("760x650")
    frame = ttk.Frame(dialog, padding=20)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Xử lý video và âm thanh", font=("Segoe UI", 18, "bold")).pack(anchor="w", pady=10)
    mode = tk.StringVar(value="Cắt nhanh")
    from .rounded import ChoiceRow
    ChoiceRow(frame, mode, [(label, label) for label in
              ("Cắt nhanh", "Cắt chính xác", "Ghép", "Nén MP4", "Đổi MP4", "Tách MP3", "Tách M4A")],
              lambda: None, app).pack(fill="x", pady=8)
    listing = tk.Listbox(frame, bg="#181818", fg="#eeeeee", height=7, selectmode="browse")
    listing.pack(fill="both", expand=True, pady=8)
    if initial:
        listing.insert("end", str(initial))
    actions = ttk.Frame(frame)
    actions.pack(fill="x")
    def add():
        for path in filedialog.askopenfilenames(title=app.locale.text("Chọn video hoặc nhạc")):
            listing.insert("end", path)
    def move(offset):
        selected = listing.curselection()
        if selected and 0 <= selected[0]+offset < listing.size():
            index = selected[0]
            value = listing.get(index)
            listing.delete(index)
            listing.insert(index+offset, value)
            listing.selection_set(index+offset)
    def remove():
        for index in reversed(listing.curselection()):
            listing.delete(index)
    for label, command in (("Thêm tệp", add), ("Lên", lambda: move(-1)), ("Xuống", lambda: move(1)), ("Bỏ tệp", remove)):
        ttk.Button(actions, text=label, command=command).pack(side="left", padx=(0, 8))
    fields = ttk.Frame(frame)
    fields.pack(fill="x", pady=16)
    start, end, target = tk.StringVar(value="0"), tk.StringVar(value="10"), tk.StringVar(value="20")
    for index, (label, variable) in enumerate((("Bắt đầu (giây)", start), ("Kết thúc (giây)", end), ("Dung lượng đích (MB)", target))):
        ttk.Label(fields, text=label).grid(row=0, column=index, sticky="w", padx=6)
        ttk.Entry(fields, textvariable=variable, width=18).grid(row=1, column=index, padx=6)
    ttk.Label(frame, text="Cắt nhanh bám keyframe. Cắt chính xác mã hóa lại. Ghép giữ khung hình nguồn lớn nhất, chuẩn hóa 30fps/AAC.\nNén theo dung lượng đích; đầu ra lớn hơn bản gốc sẽ bị bỏ.", wraplength=690, style="Muted.TLabel").pack(anchor="w", pady=12)
    status = tk.StringVar(value="Tệp gốc được giữ nguyên.")
    ttk.Label(frame, textvariable=status, wraplength=690).pack(anchor="w", pady=8)
    import threading
    stop = threading.Event()
    if not hasattr(app, "processing_stops"):
        app.processing_stops = []
    app.processing_stops.append(stop)
    def execute():
        from . import processing
        sources = list(listing.get(0, "end"))
        if not sources:
            return
        operation = mode.get()
        suffix = ".mp3" if operation == "Tách MP3" else ".m4a" if operation == "Tách M4A" else ".mp4"
        destination = filedialog.asksaveasfilename(defaultextension=suffix, initialfile=Path(sources[0]).stem+"-edited"+suffix)
        if not destination:
            return
        try:
            cut_start, cut_end, target_mb = float(start.get()), float(end.get()), float(target.get())
        except ValueError:
            messagebox.showerror(app.locale.text("Giá trị"), app.locale.text("Thời gian và dung lượng phải là số."), parent=dialog)
            return
        stop.clear()
        run_button.configure(state="disabled")
        status.set("Đang xử lý…")
        def task():
            try:
                if operation in {"Cắt nhanh", "Cắt chính xác"}:
                    return processing.cut(sources[0], destination, cut_start, cut_end, operation == "Cắt chính xác", stop)
                if operation == "Ghép":
                    return processing.concatenate(sources, destination, stop)
                if operation == "Nén MP4":
                    return processing.compress(sources[0], destination, target_mb, stop)
                if operation.startswith("Tách"):
                    return processing.extract_audio(sources[0], destination, stop)
                return processing.convert(sources[0], destination, stop)
            finally:
                app.events.put(lambda: run_button.configure(state="normal") if run_button.winfo_exists() else None)
        app.background(task, lambda path: status.set(f"Đã lưu: {path}") if dialog.winfo_exists() else None)
    run_button = ttk.Button(frame, text="Bắt đầu xử lý", style="Primary.TButton", command=execute)
    run_button.pack(side="left", pady=12)
    ttk.Button(frame, text="Hủy tác vụ", command=stop.set).pack(side="right", pady=12)
    def close():
        stop.set()
        dialog.destroy()
    dialog.protocol("WM_DELETE_WINDOW", close)


def redact_pdf(app):
    source = filedialog.askopenfilename(title=app.locale.text("Chọn PDF cần xóa thông tin"), filetypes=[(app.locale.text("PDF"), "*.pdf")])
    if not source:
        return
    from .pdf_tools import preview, redact
    try:
        image, count = preview(source)
    except Exception as exc:  # noqa: BLE001 -- Optional PDF library errors belong in the UI.
        messagebox.showerror(app.locale.text("PDF"), app.locale.text(str(exc)), parent=app.root)
        return
    from PIL import ImageTk
    dialog = tk.Toplevel(app.root)
    dialog.title(app.locale.text("Che thông tin PDF — xóa thật, xuất bản raster"))
    dialog.geometry("950x850")
    frame = ttk.Frame(dialog, padding=14)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Kéo chuột khoanh vùng cần xóa. Xuất PDF raster mới; văn bản, tệp đính kèm và lớp ẩn của bản gốc không được sao chép.", wraplength=900).pack(fill="x", pady=8)
    page_index = [0]
    rectangles = {}
    canvas = tk.Canvas(frame, background="#283548", highlightthickness=0)
    canvas.pack(fill="both", expand=True)
    photo = [None]
    geometry = [0, 0, 1, 1]
    drag = [None]
    current_image = [image]
    page_label = tk.StringVar()
    def draw(_event=None):
        page_image = current_image[0].copy()
        page_image.thumbnail((max(1, canvas.winfo_width()-20), max(1, canvas.winfo_height()-20)))
        width, height = page_image.size
        x, y = (canvas.winfo_width()-width)//2, 5
        geometry[:] = [x, y, width, height]
        photo[0] = ImageTk.PhotoImage(page_image)
        canvas.delete("all")
        canvas.create_image(x, y, image=photo[0], anchor="nw")
        for x0, y0, x1, y1 in rectangles.get(page_index[0], []):
            canvas.create_rectangle(x+x0*width, y+y0*height, x+x1*width, y+y1*height, fill="black")
        page_label.set(app.locale.text("Trang {page}/{count} · {regions} vùng xóa").format(
            page=page_index[0]+1, count=count, regions=sum(map(len, rectangles.values()))))
    def normalized(event):
        x, y, width, height = geometry
        return max(0, min(1, (event.x-x)/width)), max(0, min(1, (event.y-y)/height))
    def begin(event):
        drag[0] = normalized(event)
    def finish(event):
        if drag[0] is None:
            return
        x0, y0 = drag[0]
        x1, y1 = normalized(event)
        if abs(x0-x1) > 0.002 and abs(y0-y1) > 0.002:
            rectangles.setdefault(page_index[0], []).append((min(x0,x1), min(y0,y1), max(x0,x1), max(y0,y1)))
        drag[0] = None
        draw()
    def navigate(delta):
        if 0 <= page_index[0]+delta < count:
            page_index[0] += delta
            current_image[0].close()
            current_image[0], _ = preview(source, page_index[0])
            draw()
    def undo():
        if rectangles.get(page_index[0]):
            rectangles[page_index[0]].pop()
        draw()
    def save():
        destination = filedialog.asksaveasfilename(defaultextension=".pdf", initialfile=Path(source).stem+"-redacted.pdf")
        if destination:
            selected = {page: list(boxes) for page, boxes in rectangles.items()}
            app.background(lambda: redact(source, destination, selected), lambda path: messagebox.showinfo(
                app.locale.text("PDF"), app.locale.text(f"Đã xuất bản xóa thông tin:\n{path}"), parent=app.root))
    canvas.bind("<Configure>", draw)
    canvas.bind("<Button-1>", begin)
    canvas.bind("<ButtonRelease-1>", finish)
    actions = ttk.Frame(frame)
    actions.pack(fill="x", pady=10)
    for label, command in (("Trang trước", lambda: navigate(-1)), ("Trang sau", lambda: navigate(1)), ("Bỏ vùng cuối", undo), ("Xuất PDF đã xóa…", save)):
        ttk.Button(actions, text=label, command=command).pack(side="left", padx=6)
    ttk.Label(frame, textvariable=page_label).pack(anchor="w")
    dialog.after(200, draw)


def torrent_dialog(app, source=None, folder=None):
    from tkinter.simpledialog import askstring

    from .torrent import TorrentJob
    if source is None:
        source = askstring(app.locale.text("Torrent / magnet"), app.locale.text("Dán magnet, hoặc để trống rồi bấm OK để chọn tệp .torrent"), parent=app.root)
    if source is None:
        return
    if not source.strip():
        source = filedialog.askopenfilename(filetypes=[(app.locale.text("Torrent"), "*.torrent")])
    if not source:
        return
    folder = folder or filedialog.askdirectory(title=app.locale.text("Thư mục tải torrent"))
    if not folder:
        return
    job = TorrentJob(source, folder, state_directory=app.data_dir/"torrents")
    entry = {"source": job.source, "directory": str(job.directory)}
    history = [entry]+[item for item in app.store.setting("torrent_history", []) if item != entry]
    app.store.set_setting("torrent_history", history[:100])
    if not hasattr(app, "torrent_jobs"):
        app.torrent_jobs = []
    app.torrent_jobs.append(job)
    dialog = tk.Toplevel(app.root)
    dialog.title(app.locale.text("Torrent — chọn tệp tải, dừng chia sẻ sau hoàn tất"))
    dialog.geometry("850x550")
    frame = ttk.Frame(dialog, padding=20)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Chọn tệp bằng Ctrl/Shift. Tệp có đuôi thực thi không được chọn mặc định; hãy kiểm tra trước khi tải.", wraplength=800).pack(anchor="w", pady=10)
    listing = tk.Listbox(frame, selectmode="extended", exportselection=False, bg="#181818", fg="#eeeeee")
    listing.pack(fill="both", expand=True)
    status = tk.StringVar(value="Đang chờ metadata…")
    ttk.Label(frame, textvariable=status, wraplength=800).pack(anchor="w", pady=12)
    loaded = [False]
    indexes = []
    def refresh():
        if not dialog.winfo_exists() or job.closed:
            return
        try:
            if not loaded[0]:
                items = job.files()
                if items is not None:
                    for row, item in enumerate(items):
                        listing.insert("end", f"{'⚠ ' if item['risky'] else ''}{item['name']} ({item['size']:,} byte)")
                        indexes.append(item["index"])
                        if (job.restored and job.handle.get_file_priorities()[item["index"]]) or (not job.restored and not item["risky"]):
                            listing.selection_set(row)
                    loaded[0] = True
            info = job.status()
            label = app.locale.text("Hoàn tất, đã dừng chia sẻ" if info['complete'] else "Tiến độ")
            peers = app.locale.text("máy ngang hàng")
            status.set(f"{label}: {info['progress']*100:.1f}% · "
                       f"{info['download_rate']/1024:.1f} KB/s · {info['peers']} {peers} · {info['error']}")
        except (ValueError, RuntimeError) as exc:
            status.set(str(exc))
        dialog.after(500, refresh)
    def start():
        app.guarded(lambda: job.select([indexes[index] for index in listing.curselection()]))
    controls = ttk.Frame(frame)
    controls.pack(fill="x", pady=10)
    for label, callback in (("Tải các tệp đã chọn", start), ("Tạm dừng", job.pause), ("Tiếp tục", job.resume)):
        ttk.Button(controls, text=label, command=callback).pack(side="left", padx=6)
    def close():
        job.close()
        dialog.destroy()
    dialog.protocol("WM_DELETE_WINDOW", close)
    refresh()


def torrent_history_dialog(app):
    history = app.store.setting("torrent_history", [])
    if not history:
        messagebox.showinfo(app.locale.text("Torrent"), app.locale.text("Chưa có torrent đã lưu."), parent=app.root)
        return
    dialog = tk.Toplevel(app.root)
    dialog.title(app.locale.text("Mở lại torrent đã lưu"))
    listing = tk.Listbox(dialog, width=100, height=15, exportselection=False)
    listing.pack(fill="both", expand=True, padx=16, pady=16)
    for item in history:
        listing.insert("end", f"{Path(item['directory']).name} — {item['directory']}")
    def open_selected():
        if listing.curselection():
            item = history[listing.curselection()[0]]
            app.guarded(lambda: torrent_dialog(app, item["source"], item["directory"]))
    ttk.Button(dialog, text="Mở và tiếp tục…", command=open_selected).pack(pady=12)
