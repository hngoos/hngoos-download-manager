"""Per-file checks with honest local and multi-engine results, and explicit upload consent."""

import os
import threading
import tkinter as tk
import webbrowser
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, ttk

from .safety import inspect_download, sha256_file
from .virustotal import VirusTotalClient


class SafetyDialog(tk.Toplevel):
    def __init__(self, app, job):
        super().__init__(app.root)
        self.app, self.job = app, job
        self.busy, self.digest, self.analysis_id = False, "", ""
        self.generation = 0
        self.poll_id = None
        self.title("HDM · "+app.locale.text("Kiểm tra an toàn"))
        self.geometry("920x740")
        self.minsize(760, 620)
        self.transient(app.root)
        paths = list(dict.fromkeys(job.get("outputs") or [job["output"]]))
        self.path = tk.StringVar(value=paths[0])
        self.key = tk.StringVar(value=getattr(app, "virustotal_key", ""))
        self.local_status = tk.StringVar(value=app.locale.text("Đang kiểm tra trên máy…"))
        self.vt_status = tk.StringVar(value=app.locale.text("Chưa quét bằng VirusTotal."))
        self.hash_text = tk.StringVar()
        frame = ttk.Frame(self, padding=24)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Kiểm tra an toàn", font=("Segoe UI", 21, "bold")).pack(anchor="w")
        self.path_selector = ttk.Combobox(frame, textvariable=self.path, values=paths, state="readonly")
        self.path_selector.pack(fill="x", pady=(12, 16))
        self.path_selector.bind("<<ComboboxSelected>>", lambda _: self.scan_local())
        ttk.Label(frame, textvariable=self.local_status, wraplength=850, justify="left").pack(anchor="w")
        ttk.Label(frame, textvariable=self.hash_text, style="Muted.TLabel", wraplength=850).pack(anchor="w", pady=12)
        ttk.Separator(frame).pack(fill="x", pady=8)
        ttk.Label(frame, text="VirusTotal", font=("Segoe UI", 15, "bold")).pack(anchor="w", pady=8)
        ttk.Label(frame, text="Nhiều bộ quét · phát hiện mã độc, ransomware và virus",
                  style="Muted.TLabel").pack(anchor="w")
        credentials = ttk.Frame(frame)
        credentials.pack(fill="x", pady=12)
        ttk.Label(credentials, text="API key").pack(side="left", padx=(0, 12))
        ttk.Entry(credentials, textvariable=self.key, show="•").pack(side="left", fill="x", expand=True)
        self.lookup_button = ttk.Button(credentials, text="Kiểm tra VirusTotal", command=self.lookup)
        self.lookup_button.pack(side="left", padx=(12, 0))
        ttk.Label(frame, text="Khóa chỉ giữ trong phiên này. Tra mã băm không gửi nội dung tệp.",
                  style="Muted.TLabel").pack(anchor="w")
        ttk.Button(frame, text="Lấy API key", command=lambda: webbrowser.open(
            "https://www.virustotal.com/gui/my-apikey")).pack(anchor="w", pady=(8, 0))
        ttk.Label(frame, textvariable=self.vt_status, wraplength=850, justify="left").pack(anchor="w", pady=12)
        actions = ttk.Frame(frame)
        actions.pack(fill="x", pady=(0, 12))
        self.upload_button = ttk.Button(actions, text="Gửi tệp để quét mới…", command=self.upload, state="disabled")
        self.upload_button.pack(side="left")
        self.refresh_button = ttk.Button(actions, text="Lấy kết quả quét", command=self.refresh_analysis, state="disabled")
        self.refresh_button.pack(side="left", padx=8)
        ttk.Button(actions, text="Mở trang VirusTotal", command=lambda: webbrowser.open(
            "https://www.virustotal.com/gui/file/"+self.digest if self.digest else
            "https://www.virustotal.com/gui/home/upload")).pack(side="left")
        self.engines = ttk.Treeview(frame, columns=("engine", "category", "result"), show="headings", height=6)
        for column, label, width in (("engine", "Bộ quét", 190), ("category", "Kết quả", 160), ("result", "Phát hiện", 390)):
            self.engines.heading(column, text=app.locale.text(label))
            self.engines.column(column, width=width, minwidth=80)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.engines.yview)
        self.engines.configure(yscrollcommand=scrollbar.set)
        bottom = ttk.Frame(frame)
        bottom.pack(side="bottom", fill="x", pady=(12, 0))
        ttk.Label(bottom, text="Không có bộ quét nào bảo đảm phát hiện mọi mối đe dọa.",
                  style="Muted.TLabel", wraplength=620).pack(side="left")
        ttk.Button(bottom, text="Đóng", command=self.destroy).pack(side="right")
        scrollbar.pack(side="right", fill="y")
        self.engines.pack(fill="both", expand=True)
        app.apply_preferences()
        self.scan_local()

    def run(self, work, success, *, local=False):
        if self.busy:
            return
        self.busy = True
        self.path_selector.configure(state="disabled")
        self.lookup_button.configure(state="disabled")
        self.upload_button.configure(state="disabled")
        self.refresh_button.configure(state="disabled")
        generation = self.generation
        def finish(value=None, error=None):
            if not self.winfo_exists() or generation != self.generation:
                return
            self.busy = False
            self.path_selector.configure(state="readonly")
            self.lookup_button.configure(state="normal" if self.digest else "disabled")
            self.refresh_button.configure(state="normal" if self.analysis_id else "disabled")
            if error:
                (self.local_status if local else self.vt_status).set(str(error))
            else:
                success(value)
        def worker():
            try:
                result = work()
                self.app.events.put(lambda: finish(result))
            except Exception as error:  # noqa: BLE001 -- All scanners can fail; never label failure as safe.
                self.app.events.put(lambda error=str(error): finish(error=error))
        thread = threading.Thread(target=worker, daemon=True)
        self.app.background_threads.append(thread)
        thread.start()

    def destroy(self):
        self.generation += 1
        if self.poll_id is not None:
            self.after_cancel(self.poll_id)
        self.key.set("")
        super().destroy()

    def scan_local(self):
        if self.busy:
            return
        self.generation += 1
        self.digest, self.analysis_id = "", ""
        self.engines.delete(*self.engines.get_children())
        self.hash_text.set("")
        self.vt_status.set(self.app.locale.text("Chưa quét bằng VirusTotal."))
        self.local_status.set(self.app.locale.text("Đang kiểm tra trên máy…"))
        path = Path(self.path.get())
        def scan():
            if not path.is_file():
                raise FileNotFoundError(self.app.locale.text("Tệp đã được di chuyển hoặc xóa."))
            digest = sha256_file(path)
            result = inspect_download(path, path.name.removesuffix(".chuakiemtra"),
                high_security=self.app.store.setting("high_security", False), antivirus=os.name == "nt")
            if sha256_file(path) != digest:
                raise ValueError(self.app.locale.text("Tệp thay đổi trong lúc kiểm tra; hãy quét lại."))
            return digest, result
        def done(value):
            self.digest, result = value
            self.lookup_button.configure(state="normal")
            self.hash_text.set("SHA-256: "+self.digest)
            if result["reasons"]:
                self.local_status.set(self.app.locale.text("Cần kiểm tra: ")+"\n"+"\n".join(result["reasons"][:8]))
            else:
                self.local_status.set(self.app.locale.text(result["safety_note"])+" · "+
                    self.app.locale.text("Chưa phát hiện dấu hiệu trong phạm vi kiểm tra."))
            self.app.store.update(self.job["id"], safety_check={
                "sha256": self.digest, "local": result, "time": datetime.now().isoformat(timespec="seconds")})
        self.run(scan, done, local=True)

    def client(self):
        client = VirusTotalClient(self.key.get())
        self.app.virustotal_key = self.key.get().strip()
        return client

    def lookup(self):
        if self.busy or not self.digest:
            return
        try:
            client = self.client()
        except ValueError as error:
            self.vt_status.set(str(error))
            return
        self.vt_status.set(self.app.locale.text("Đang tra kết quả nhiều bộ quét…"))
        digest = self.digest
        def done(result):
            if result is None:
                self.vt_status.set(self.app.locale.text("VirusTotal chưa có báo cáo. Bạn có thể gửi tệp để quét mới."))
                self.upload_button.configure(state="normal")
            else:
                self.show_report(result)
        path = Path(self.path.get())
        def lookup():
            result = client.lookup(digest)
            if sha256_file(path) != digest:
                raise ValueError(self.app.locale.text("Tệp thay đổi trong lúc kiểm tra; hãy quét lại."))
            return result
        self.run(lookup, done)

    def upload(self):
        if self.busy or not self.digest:
            return
        try:
            client = self.client()
        except ValueError as error:
            self.vt_status.set(str(error))
            return
        if not messagebox.askyesno("VirusTotal", self.app.locale.text(
                "Gửi toàn bộ tệp này lên VirusTotal?\nTệp có thể được chia sẻ với các đối tác bảo mật. Không gửi tệp riêng tư."),
                parent=self):
            return
        path, digest = Path(self.path.get()), self.digest
        self.vt_status.set(self.app.locale.text("Đang gửi tệp để quét…"))
        def done(identifier):
            self.analysis_id = identifier
            self.refresh_button.configure(state="normal")
            self.vt_status.set(self.app.locale.text("Đã gửi. Đang chờ các bộ quét trả kết quả…"))
            self.poll_id = self.after(20000, self.refresh_analysis)
        self.run(lambda: client.upload(path, digest, consent=True), done)

    def refresh_analysis(self):
        self.poll_id = None
        if self.busy or not self.analysis_id or not self.winfo_exists():
            return
        try:
            client = self.client()
        except ValueError as error:
            self.vt_status.set(str(error))
            return
        identifier, digest, path = self.analysis_id, self.digest, Path(self.path.get())
        def analysis():
            result = client.analysis(identifier)
            if sha256_file(path) != digest:
                raise ValueError(self.app.locale.text("Tệp thay đổi trong lúc kiểm tra; hãy quét lại."))
            return result
        self.run(analysis, self.show_report)

    def show_report(self, result):
        stats = result["stats"]
        malicious, suspicious = stats.get("malicious", 0), stats.get("suspicious", 0)
        self.engines.delete(*self.engines.get_children())
        for engine in result["engines"]:
            self.engines.insert("", "end", values=(engine["name"], engine["category"], engine["result"]))
        if result["status"] != "completed":
            self.vt_status.set(self.app.locale.text("Đang chờ quét; chưa có kết luận."))
        else:
            count = sum(stats.get(key, 0) for key in ("malicious", "suspicious", "harmless", "undetected"))
            if not count:
                self.vt_status.set(self.app.locale.text("Báo cáo không có kết quả từ bộ quét."))
                self.upload_button.configure(state="normal")
                return
            message = self.app.locale.text("Phát hiện mã độc") if malicious or suspicious else self.app.locale.text(
                "Chưa bộ quét nào phát hiện trong báo cáo này")
            self.vt_status.set(f"{message}: {malicious} malicious · {suspicious} suspicious / {count} engines")
            if result.get("date"):
                self.vt_status.set(self.vt_status.get()+"\n"+self.app.locale.text("Thời điểm báo cáo: ")+
                                   datetime.fromtimestamp(result["date"]).isoformat(sep=" ", timespec="seconds"))
            self.app.store.update(self.job["id"], virustotal={"sha256": self.digest, "stats": stats,
                                                           "date": result.get("date")})
            if malicious or suspicious:
                self.app.store.update(self.job["id"], safety_note="VirusTotal · "+self.app.locale.text("Phát hiện mã độc"))
            self.upload_button.configure(state="normal")
