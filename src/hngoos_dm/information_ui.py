"""Information menu, local preferences and Chromium extension installation."""

import tkinter as tk
import webbrowser
from tkinter import filedialog, ttk

REPOSITORY = "https://github.com/hngoos/hngoos-download-manager"


def information_menu(app):
    translate = app.locale.text
    from .ui_preferences import PALETTES
    _, panel, text, _, accent = PALETTES[app.theme]
    options = {"tearoff": False, "background": panel, "foreground": text, "activebackground": accent,
               "activeforeground": "#151020" if app.theme == "dark" else "white"}
    menu = tk.Menu(app.root, **options)
    transfer = tk.Menu(menu, **options)
    for label, command in (("Nhập danh sách…", app.batch_dialog), ("Xuất lịch sử tải CSV…", app.export_history),
                           ("Xuất báo cáo danh sách từng dòng…", app.export_batch_report)):
        transfer.add_command(label=translate(label), command=command)
    menu.add_cascade(label=translate("Nhập / Xuất"), menu=transfer)
    menu.add_command(label=translate("Tiện ích trình duyệt"), command=lambda: browser_dialog(app))
    menu.add_command(label=translate("Thiết lập"), command=app.open_preferences)
    languages = tk.Menu(menu, **options)
    app.menu_language = tk.StringVar(value=app.locale.language)
    for label, value in (("Tiếng Việt", "vi"), ("English", "en")):
        languages.add_radiobutton(label=label, variable=app.menu_language, value=value,
                                 command=lambda value=value: app.set_preference("language", value))
    menu.add_cascade(label=translate("Ngôn ngữ"), menu=languages)
    menu.add_separator()
    for label, url in (("Liên hệ hỗ trợ", "mailto:1hngoos@gmail.com"),
                       ("Báo lỗi", REPOSITORY+"/issues/new?labels=bug"),
                       ("Tham gia Discord", "https://discord.gg/xn2AnqcQhS")):
        menu.add_command(label=translate(label), command=lambda url=url: webbrowser.open(url))
    menu.add_separator()
    menu.add_command(label="Check for update", command=app.check_update)
    menu.add_command(label=translate("Giới thiệu"), command=app.open_about)
    menu.add_separator()
    menu.add_command(label=translate("Thoát"), command=app.close)
    return menu


def content_dialog(app, attribute, title, builders):
    previous = getattr(app, attribute, None)
    if previous and previous.winfo_exists():
        previous.lift()
        return previous
    dialog = tk.Toplevel(app.root)
    setattr(app, attribute, dialog)
    dialog.title("HDM · "+app.locale.text(title))
    dialog.geometry("960x680")
    dialog.minsize(780, 560)
    dialog.transient(app.root)
    frame = ttk.Frame(dialog, padding=20)
    frame.pack(fill="both", expand=True)
    if len(builders) == 1:
        builders[0][1](app.scrollable(frame))
    else:
        tabs = ttk.Notebook(frame)
        tabs.pack(fill="both", expand=True)
        for label, build in builders:
            tab = ttk.Frame(tabs, padding=12)
            tabs.add(tab, text=app.locale.text(label))
            build(app.scrollable(tab))
    app.apply_preferences()
    return dialog


def browser_dialog(app):
    def build(parent):
        ttk.Label(parent, text="Tiện ích trình duyệt", font=("Segoe UI", 20, "bold")).pack(anchor="w", pady=12)
        ttk.Label(parent, text="1. Tải ZIP và giải nén vào thư mục cố định.\n"
                  "2. Mở chrome://extensions hoặc edge://extensions, bật Developer mode.\n"
                  "3. Chọn Load unpacked và thư mục có manifest.json.\n"
                  "4. Sao chép Extension ID, dán bên dưới và đăng ký kết nối.\n"
                  "5. Mở tiện ích và chọn Test connection.", wraplength=850,
                  justify="left").pack(anchor="w", pady=12)
        status = tk.StringVar()
        def download():
            target = filedialog.asksaveasfilename(parent=parent.winfo_toplevel(),
                initialfile="HDM-Browser-Extension.zip", defaultextension=".zip", filetypes=[("ZIP", "*.zip")])
            if not target:
                return
            button.configure(state="disabled")
            status.set(app.locale.text("Đang tải tiện ích…"))
            def success(path):
                if button.winfo_exists():
                    button.configure(state="normal")
                    status.set(str(path))
            def failed(error):
                if button.winfo_exists():
                    button.configure(state="normal")
                    status.set(str(error))
            # Queue all Tk updates on the main thread, including error state.
            import threading
            def worker():
                try:
                    from .extension_package import download_extension
                    result = download_extension(target)
                    app.events.put(lambda: success(result))
                except Exception as error:  # noqa: BLE001 -- Present network errors in the dialog.
                    app.events.put(lambda error=str(error): failed(error))
            thread = threading.Thread(target=worker, daemon=True)
            app.background_threads.append(thread)
            thread.start()
        button = ttk.Button(parent, text="Tải tiện ích (.zip)", command=download)
        button.pack(anchor="w", pady=8)
        ttk.Label(parent, textvariable=status, style="Muted.TLabel", wraplength=850).pack(anchor="w")
        app._browser(parent)
    return content_dialog(app, "browser_dialog", "Tiện ích trình duyệt", [("", build)])
