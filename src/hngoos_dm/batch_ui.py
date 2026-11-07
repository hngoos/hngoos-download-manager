"""Editable batch preview and durable, URL-free per-row reporting."""

import csv
import io
import tkinter as tk
import uuid
from tkinter import filedialog, messagebox, simpledialog, ttk

from .batch import normalize, parse_text, read_batch
from .information_ui import ContentPage


def open_batch(app):
    dialog = ContentPage(app, "Nhập danh sách…")
    frame = ttk.Frame(dialog.body, padding=16)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Dán hai cột link / tên, rồi bấm Xem trước. Nhấp đúp một dòng để sửa.").pack(anchor="w")
    editor = tk.Text(frame, height=7, wrap="none", undo=True)
    editor.pack(fill="x", pady=10)
    table = ttk.Treeview(frame, columns=("number", "url", "name"), show="headings", selectmode="extended")
    for column, label, width in (("number", "#", 40), ("url", "Link", 520), ("name", "Tên tệp", 300)):
        table.heading(column, text=label)
        table.column(column, width=width, stretch=column != "number")
    table.pack(fill="both", expand=True)
    rows = []

    def redraw():
        table.delete(*table.get_children())
        for index, (url, name) in enumerate(rows):
            table.insert("", "end", iid=str(index), values=(index+1, url, name))

    def preview():
        nonlocal rows
        rows = parse_text(editor.get("1.0", "end"))
        if len(rows) > 500:
            raise ValueError("Mỗi lần nhập tối đa 500 dòng.")
        redraw()

    def load():
        path = filedialog.askopenfilename(parent=dialog, filetypes=[(app.locale.text("Danh sách"), "*.xlsx *.csv *.txt")])
        if path:
            values = read_batch(path)
            buffer = io.StringIO()
            writer = csv.writer(buffer, delimiter="\t")
            writer.writerows(values)
            editor.delete("1.0", "end")
            editor.insert("1.0", buffer.getvalue())
            preview()

    def edit(_event=None):
        for item in table.selection():
            index = int(item)
            url, name = rows[index]
            url = simpledialog.askstring(app.locale.text("Sửa link"), app.locale.text("Đường dẫn HTTP/HTTPS"), initialvalue=url, parent=dialog)
            if url is None:
                continue
            name = simpledialog.askstring(app.locale.text("Sửa tên"), app.locale.text("Tên tệp"), initialvalue=name, parent=dialog)
            if name is not None:
                rows[index] = normalize([(url, name)])[0]
        redraw()

    def remove():
        for index in sorted(map(int, table.selection()), reverse=True):
            rows.pop(index)
        redraw()

    def rename():
        prefix = simpledialog.askstring(app.locale.text("Đổi tên hàng loạt"), app.locale.text("Tiền tố tên tệp (sẽ thêm 001, 002… và giữ đuôi)"), parent=dialog)
        if prefix is None:
            return
        from pathlib import Path
        selected = table.selection() or table.get_children()
        for number, item in enumerate(selected, 1):
            index = int(item)
            url, name = rows[index]
            rows[index] = normalize([(url, f"{prefix}{number:03d}{Path(name).suffix}")])[0]
        redraw()

    def submit():
        if not rows:
            preview()
        if not rows:
            raise ValueError("Danh sách chưa có link hợp lệ.")
        batch_id = uuid.uuid4().hex
        created = []
        # Add every row paused first, so a validation error never starts half a batch.
        try:
            for number, (url, name) in enumerate(rows, 1):
                job_id = app.manager.add(url, app.directory.get(), name, int(app.connections.get()), start=False)
                app.store.update(job_id, batch_id=batch_id, batch_row=number)
                created.append(job_id)
        except Exception:
            for job_id in created:
                app.store.update(job_id, state="error", error="Danh sách chưa được thêm đầy đủ; chưa bắt đầu tải.")
            raise
        for job_id in created:
            app.manager.start(job_id)
        app.status.set(f"Đã thêm {len(created)} lượt tải; có thể xuất báo cáo từng dòng trong Công cụ.")
        dialog.destroy()

    def guarded(action):
        def call(*_args):
            try:
                action()
            except (ValueError, OSError) as exc:
                messagebox.showerror(app.locale.text("Danh sách"), app.locale.text(str(exc)), parent=dialog)
        return call

    table.bind("<Double-1>", guarded(edit))
    actions = ttk.Frame(frame)
    actions.pack(fill="x", pady=10)
    for text, action in (("Mở tệp…", load), ("Xem trước", preview), ("Sửa dòng", edit),
                         ("Đổi tên hàng loạt", rename), ("Xóa dòng", remove)):
        ttk.Button(actions, text=text, command=guarded(action)).pack(side="left", padx=3)
    ttk.Button(actions, text="Bắt đầu tải", command=guarded(submit), style="Primary.TButton").pack(side="right")
    app.apply_preferences()
    return dialog


def export_batch_report(store, destination):
    from pathlib import Path
    with Path(destination).open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(("Batch", "Dòng", "Tên tệp", "Trạng thái", "Đã tải", "Tổng", "SHA-256"))
        for job in reversed(store.all()):
            if job.get("batch_id"):
                # Do not export URLs, tokens or raw network errors in shared reports.
                writer.writerow((job["batch_id"], job["batch_row"], "'"+job["filename"], job["state"],
                                 job["downloaded"], job["total"], job.get("sha256", "")))
