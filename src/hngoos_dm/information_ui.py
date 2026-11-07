"""Information menu, local preferences and Chromium extension installation."""

import time
import tkinter as tk
from tkinter import ttk

from .rounded import RoundedPanel

REPOSITORY = "https://github.com/hngoos/hngoos-download-manager"


def build_browser_settings(app, parent):
    from . import browser
    from .icons import load_browser_icons
    from .rounded import RoundedButton
    ttk.Label(parent, text="Trình duyệt", font=("Segoe UI", 16, "bold")).pack(anchor="w", pady=(0, 10))
    actions = ttk.Frame(parent)
    actions.pack(fill="x")
    app.browser_install_buttons = {}
    app.browser_icons = load_browser_icons(app.root)
    for index, browser_id in enumerate(browser.supported_browsers()):
        available = browser.find_browser(browser_id) is not None
        button = RoundedButton(actions, text="",
                               command=lambda browser_id=browser_id: browser_dialog(app, browser_id),
                               width=54, height=60, flat=True, image=app.browser_icons[browser_id, available])
        button.configure(state="normal" if available else "disabled", cursor="hand2" if available else "arrow",
                         takefocus=available)
        button.grid(row=0, column=index, padx=(0, 2), pady=2)
        app.browser_install_buttons[browser_id] = button


def build_browser_capture_settings(app, parent):
    from .browser_preferences import validate_preferences
    config = validate_preferences(app.store.setting("browser_preferences", {}))
    app.browser_capture = tk.BooleanVar(value=config["capture"])
    app.browser_auto_start = tk.BooleanVar(value=config["auto_start"])
    def save():
        # Removed filter controls must not silently keep restricting capture.
        config.update(capture=app.browser_capture.get(), auto_start=app.browser_auto_start.get(),
                      skip_domains_enabled=False, skip_extensions_enabled=False,
                      only_extensions_enabled=False, min_bytes_enabled=False)
        app.store.set_setting("browser_preferences", validate_preferences(config))
        app.store.set_setting("browser_preferences_revision", str(time.time_ns()))
    app.save_browser_preferences = lambda: app.guarded(save)
    app.browser_capture_button = ttk.Checkbutton(parent, text="Chuyển lượt tải từ trình duyệt sang HDM",
        variable=app.browser_capture, command=app.save_browser_preferences)
    app.browser_capture_button.pack(anchor="w", pady=4)
    app.browser_auto_start_button = ttk.Checkbutton(parent, text="Bắt đầu tải mà không cần xác nhận",
        variable=app.browser_auto_start, command=app.save_browser_preferences)
    app.browser_auto_start_button.pack(anchor="w", pady=4)
    if any(config[key+"_enabled"] for key in ("skip_domains", "skip_extensions", "only_extensions", "min_bytes")):
        save()


def information_menu(app):
    translate = app.locale.text
    from .rounded import RoundedMenu
    menu = RoundedMenu(app)
    menu.add_command(label=translate("Thiết lập"), command=app.open_preferences)
    menu.add_separator()
    menu.add_command(label=translate("Báo lỗi"), command=app.open_bug_report)
    menu.add_separator()
    menu.add_command(label=translate("Kiểm tra cập nhật"), command=app.check_update)
    menu.add_command(label=translate("Giới thiệu"), command=app.open_about)
    menu.add_command(label=translate("Thoát"), command=app.close)
    return menu


class CenteredCard(RoundedPanel):
    """A compact modal surface in the existing native window."""
    lift = tk.Misc.tkraise

    def __init__(self, app, title="", height=300, on_close=None):
        previous = getattr(app, "modal_card", None)
        if previous and previous.winfo_exists():
            previous.destroy()
        super().__init__(app.root, padding=22, radius=24)
        self.app = app
        self.on_close = on_close or self.destroy
        self.previous_focus = app.root.focus_get()
        app.modal_card = self
        if title:
            ttk.Label(self.content, text=title, style="Card.TLabel", anchor="center",
                      font=("Segoe UI", 15, "bold")).pack(fill="x", pady=(4, 12))
        self.footer = ttk.Frame(self.content, style="Card.TFrame")
        self.footer.pack(side="bottom", pady=(16, 0))
        self.body = ttk.Frame(self.content, style="Card.TFrame")
        self.body.pack(fill="both", expand=True)
        self.place(relx=.5, rely=.5, anchor="center", width=500, height=height)
        self.lift()
        self.escape_binding = app.root.bind("<Escape>", self.dismiss, add="+")
        self.outside_binding = app.root.bind("<Button-1>", self.dismiss_outside, add="+")
        self.activation = self.after_idle(self.activate)

    def dismiss(self, _event=None):
        self.on_close()
        return "break"

    def dismiss_outside(self, event):
        x, y = self.winfo_rootx(), self.winfo_rooty()
        if not (x <= event.x_root < x+self.winfo_width() and y <= event.y_root < y+self.winfo_height()):
            return self.dismiss()

    def draw(self):
        super().draw()
        from .ui_preferences import PALETTES
        background, panel, *_ = PALETTES[self.theme]
        self.configure(background=background)
        self.delete("backdrop")
        # Match both underlying panels and the gaps between them at the round corners.
        x, y = self.winfo_rootx(), self.winfo_rooty()
        width, height = self.winfo_width(), self.winfo_height()
        for surface in (getattr(self.app, "empty_panel", None), getattr(self.app, "url_panel", None),
                        getattr(self.app, "queue_panel", None)):
            if surface and surface.winfo_ismapped():
                left, top = surface.winfo_rootx()-x, surface.winfo_rooty()-y
                right, bottom = left+surface.winfo_width(), top+surface.winfo_height()
                if right > 0 and bottom > 0 and left < width and top < height:
                    self.create_rectangle(max(0, left), max(0, top), min(width, right), min(height, bottom),
                                          fill=panel, outline="", tags="backdrop")
        self.tag_lower("backdrop")

    def activate(self):
        self.activation = None
        self.grab_set()
        self.focus_set()

    def destroy(self):
        if self.activation:
            self.after_cancel(self.activation)
            self.activation = None
        self.app.root.unbind("<Escape>", self.escape_binding)
        self.app.root.unbind("<Button-1>", self.outside_binding)
        if self.grab_current() == self:
            self.grab_release()
        if getattr(self.app, "modal_card", None) == self:
            self.app.modal_card = None
        focus = self.previous_focus
        super().destroy()
        if not getattr(self.app, "_closing", False) and focus and focus.winfo_exists():
            focus.focus_set()


class ContentPage(ttk.Frame):
    """Navigate inside the existing app window while transfers continue."""
    def __init__(self, app, title, beside_logo=False):
        self.beside_logo = beside_logo
        super().__init__(app.shell if beside_logo else app.view_host, padding=(16, 0, 16, 0))
        self.app = app
        self.body = ttk.Frame(self)
        self.body.pack(fill="both", expand=True)
        self.show()

    def show(self):
        app = self.app
        if self in app.page_stack:
            return
        if not app.page_stack:
            app.resize_source_card()
        previous = app.page_stack[-1] if app.page_stack else app.tabs
        previous.pack_forget()
        previous.place_forget()
        if not app.page_stack:
            app.url_panel.grid_remove()
            app.empty_panel.grid_remove()
            app.header_left.configure(height=app.brand_label.winfo_reqheight())
        app.page_stack.append(self)
        if self.beside_logo:
            self.place(relx=.04, rely=.05, relwidth=.90, relheight=.88)
            app.header.pack_forget()
            if hasattr(self, "position_columns"):
                self.position_columns()
        else:
            if getattr(previous, "beside_logo", False):
                app.header.place_forget()
                app.header.pack(before=app.view_host, fill="x", padx=18, pady=(0, 14))
            self.pack(fill="both", expand=True)
        app.schedule_redraw()

    def hide(self):
        app = self.app
        if self not in app.page_stack:
            return
        index = app.page_stack.index(self)
        for child in list(app.page_stack[index+1:])[::-1]:
            child.destroy()
        app.page_stack.remove(self)
        self.place_forget()
        self.pack_forget()
        if not getattr(app, "_closing", False) and app.tabs.winfo_exists():
            previous = app.page_stack[-1] if app.page_stack else app.tabs
            if getattr(previous, "beside_logo", False):
                previous.place(relx=.04, rely=.05, relwidth=.90, relheight=.88)
                previous.position_columns()
            else:
                previous.pack(fill="both", expand=True)
            if not app.page_stack:
                if self.beside_logo:
                    app.header.place_forget()
                    app.header.pack(before=app.view_host, fill="x", padx=18, pady=(0, 14))
                editor = getattr(app, "download_editor", None)
                if editor and editor.show_options:
                    app.url_panel.grid()
                app.empty_panel.grid()
                app.schedule_source_resize()
            app.schedule_redraw()

    def destroy(self):
        self.hide()
        super().destroy()


def preferences_page(app):
    """Compact static columns: general controls under the logo, downloads beside it."""
    previous = getattr(app, "preferences_dialog", None)
    if previous and previous.winfo_exists():
        previous.show()
        return previous
    dialog = app.preferences_dialog = ContentPage(app, "Thiết lập", beside_logo=True)
    body = dialog.body
    body.columnconfigure(0, weight=0)
    body.columnconfigure(1, weight=1)
    left, right = ttk.Frame(body), ttk.Frame(body)
    left.grid(row=0, column=1, sticky="new", padx=(24, 0))
    right.grid(row=0, column=0, sticky="new", padx=(0, 24))
    dialog.sections = {}
    # General initializes variables shared by the download and system sections.
    appearance = dialog.sections["Chung"] = ttk.Frame(right)
    appearance.pack(fill="x", pady=(0, 20))
    app._download_settings(appearance)
    from .preferences import build_network_settings
    for title, parent, builder in (
            ("Tải xuống", left, app._transfer_settings), ("Hệ thống", left, app._system_settings),
            ("Trình duyệt", right, lambda frame: build_browser_settings(app, frame)),
            ("Mạng", right, lambda frame: build_network_settings(app, frame))):
        section = dialog.sections[title] = ttk.Frame(parent)
        section.pack(fill="x", pady=(0, 20))
        builder(section)
    contact = dialog.sections["Liên hệ"] = ttk.Frame(right)
    contact.pack(fill="x", pady=(0, 8))
    build_contact_settings(app, contact)
    def position_columns():
        if not app.page_stack or app.page_stack[-1] is not dialog:
            return
        wide = app.root.winfo_width() >= 1400
        dialog.place_configure(relx=.08 if wide else .04, relwidth=.85 if wide else .90)
        body.columnconfigure(0, minsize=round(app.root.winfo_width()*.34) if wide else 0)
        logo_height = app.header_logo.height()
        app.header.pack_forget()
        app.header.place(x=18, y=0, width=app.header_logo.width()+8, height=logo_height)
        app.header.lift()
        right.grid_configure(pady=(max(0, logo_height+14-round(app.shell.winfo_height()*.05)), 0))
    dialog.position_columns = position_columns
    position_columns()
    def fit(_event=None):
        position_columns()
        compact = app.root.winfo_height() < 1000
        for value, button in app.proxy_choices.buttons.items():
            width = button.label_font.measure(app.locale.text(button.label))+(20 if compact else 40)
            app.proxy_choices.widths[value] = width
            button.configure(width=width)
        from types import SimpleNamespace
        app.proxy_choices.arrange(SimpleNamespace(width=app.proxy_choices.winfo_width()))
        for button, natural in ((app.preference_report_button, 140), (app.preference_update_button, 180),
                                (app.preference_reset_button, 180)):
            button.configure(width=min(natural, max(90, (left.winfo_width()-20)//3)))
        contact.winfo_children()[0].pack_configure(pady=(0, 4 if compact else 8))
        contact.winfo_children()[2].pack_configure(pady=(4, 4) if compact else (6, 8))
        for title in dialog.sections:
            section = dialog.sections[title]
            section.pack_configure(pady=(0, 4 if compact else 20))
            for control in section.winfo_children():
                if isinstance(control, ttk.Checkbutton):
                    control.pack_configure(pady=0 if compact else 4)
    dialog.bind("<Configure>", fit)
    fit()
    app.apply_preferences()
    return dialog


def build_contact_settings(app, parent):
    import webbrowser

    from . import __version__
    ttk.Label(parent, text="Liên hệ", font=("Segoe UI", 16, "bold")).pack(anchor="w", pady=(0, 8))
    ttk.Label(parent, text=f"Hngoos Download Manager · {__version__}").pack(anchor="w")
    links = ttk.Frame(parent)
    links.pack(anchor="w", pady=(6, 8))
    for label, url in (("Facebook", "https://www.facebook.com/hngoos"),
                       ("Instagram", "https://www.instagram.com/hngoos"),
                       ("Gmail", "mailto:1hngoos@gmail.com"), ("GitHub", REPOSITORY)):
        link = ttk.Label(links, text=label, cursor="hand2", takefocus=True)
        link.pack(side="left", padx=(0, 16))
        link.bind("<Button-1>", lambda _event, url=url: webbrowser.open(url))
        link.bind("<Return>", lambda _event, url=url: webbrowser.open(url))


def content_dialog(app, attribute, title, builders):
    previous = getattr(app, attribute, None)
    if previous and previous.winfo_exists():
        for page in list(app.page_stack[app.page_stack.index(previous)+1:])[::-1]:
            page.destroy()
        return previous
    if app.page_stack:
        app.page_stack[-1].destroy()
    dialog = ContentPage(app, title)
    setattr(app, attribute, dialog)
    frame = dialog.body
    if len(builders) == 1:
        builders[0][1](app.scrollable(frame))
    else:
        sidebar = ttk.Frame(frame, width=180)
        sidebar.pack(side="left", fill="y", padx=(0, 24))
        content = ttk.Frame(frame)
        content.pack(side="left", fill="both", expand=True)
        shared = app.scrollable(content)
        canvas = shared.master
        dialog.sections, dialog.section_buttons, dialog.scroller = {}, {}, canvas
        from .rounded import RoundedButton
        def select_section(label):
            dialog.update_idletasks()
            canvas.yview_moveto(dialog.sections[label].winfo_y()/max(1, shared.winfo_height()))
        dialog.select_section = select_section
        for label, build in builders:
            section = ttk.Frame(shared)
            section.pack(fill="x", pady=(0, 32))
            dialog.sections[label] = section
            button = RoundedButton(sidebar, text=label, command=lambda label=label: select_section(label),
                                   width=160, height=40, flat=True)
            button.pack(fill="x", pady=3)
            dialog.section_buttons[label] = button
            build(section)
        def update_navigation(first, last):
            shared.scrollbar.set(first, last)
            top = canvas.canvasy(0)+2
            active = next((label for label, section in reversed(dialog.sections.items())
                           if section.winfo_y() <= top), builders[0][0])
            for label, button in dialog.section_buttons.items():
                selected = label == active
                if button.flat == selected:
                    button.flat = not selected
                    button.draw()
        canvas.configure(yscrollcommand=update_navigation)
        # Leave room below the final section so every sidebar target can align at the top.
        spacer = ttk.Frame(shared, height=1)
        spacer.pack(fill="x")
        def resize_spacer(_event):
            spacer.configure(height=max(1, canvas.winfo_height()-dialog.sections[builders[-1][0]].winfo_height()+2))
        canvas.bind("<Configure>", resize_spacer, add="+")
        dialog.sections[builders[-1][0]].bind("<Configure>", resize_spacer, add="+")
    app.apply_preferences()
    return dialog


def browser_dialog(app, browser_id="chrome"):
    import json
    from pathlib import Path
    from tkinter import filedialog

    from . import browser
    from .extension_package import bundled_extension_path
    from .rounded import RoundedButton
    previous = getattr(app, "browser_install_page", None)
    if previous and previous.winfo_exists():
        if previous.browser_id == browser_id:
            return previous
        previous.destroy()
    dialog = app.browser_install_page = ContentPage(app, "Tiện ích trình duyệt")
    dialog.browser_id = browser_id
    dialog.archive_path = bundled_extension_path()
    parent = dialog.body
    name = browser.BROWSERS[browser_id][0]
    header = ttk.Frame(parent)
    header.pack(fill="x", pady=(8, 18))
    dialog.browser_title = ttk.Label(header, text=name, font=("Segoe UI", 20, "bold"))
    dialog.browser_title.pack(side="left")
    status = dialog.status = tk.StringVar()

    def connect_folder():
        folder = filedialog.askdirectory(parent=app.root,
            title=app.locale.text("Chọn thư mục tiện ích đã giải nén"),
            initialdir=str(dialog.archive_path.parent) if dialog.archive_path else app.directory.get())
        if not folder:
            return
        try:
            source = Path(folder)
            manifest = json.loads((source/"manifest.json").read_text(encoding="utf-8"))
            if (manifest.get("manifest_version") != 3 or manifest.get("name") != "Hngoos Download Manager"
                    or not (source/"background.js").is_file()):
                raise ValueError("Chọn thư mục HDM chứa manifest.json sau khi giải nén.")
            browser.connect_extension(source, app.data_dir)
            status.set(app.locale.text("Đã kết nối tiện ích với HDM."))
        except (OSError, ValueError) as error:
            status.set(app.locale.text(str(error)))

    dialog.archive_label = ttk.Label(parent, text=str(dialog.archive_path), style="Muted.TLabel",
                                      font=("Segoe UI", 11), wraplength=900)
    dialog.archive_label.translate_text = False
    dialog.archive_label.pack(anchor="w", pady=(0, 12))
    instructions = ttk.Frame(parent)
    instructions.pack(fill="both", expand=True)
    extension_page = browser.BROWSERS[browser_id][1]+"://extensions"
    steps = (
        "B1: Mở trang tiện ích của trình duyệt:",
        "B2: Bật Chế độ nhà phát triển (Developer mode).",
        "B3: Giải nén HDM-Browser-Extension.zip có sẵn cùng HDM vào một thư mục cố định.",
        "B4: Chọn Tải tiện ích đã giải nén (Load unpacked), rồi chọn thư mục chứa manifest.json.",
        "B5: Bấm Kết nối HDM bên dưới và chọn lại thư mục vừa giải nén.",
        "B6: Mở cài đặt tiện ích HDM, bấm Bật chuyển lượt tải sang HDM và xác nhận quyền.",
    )
    def open_page(_event=None):
        try:
            browser.open_extensions(browser_id)
        except OSError as error:
            status.set(app.locale.text(str(error)))
        return "break"

    dialog.step_labels = []
    for index, step in enumerate(steps):
        label = ttk.Label(instructions, text=app.locale.text(step),
                          font=("Segoe UI", 12), wraplength=520, justify="left")
        label.pack(anchor="w", pady=(3, 8))
        dialog.step_labels.append(label)
        if index == 0:
            dialog.extension_link = ttk.Label(instructions, text=extension_page, cursor="hand2", takefocus=True,
                                             font=("Segoe UI", 12, "underline"))
            dialog.extension_link.translate_text = False
            dialog.extension_link.pack(anchor="w", pady=(0, 10))
            for sequence in ("<Button-1>", "<Return>", "<space>"):
                dialog.extension_link.bind(sequence, open_page)
        if index == 4:
            dialog.connect_button = RoundedButton(instructions, text="Kết nối HDM", command=connect_folder,
                                                  width=200, height=40)
            dialog.connect_button.pack(anchor="w", pady=(0, 10))
    def fit_steps(event):
        dialog.archive_label.configure(wraplength=max(200, event.width))
        for label in dialog.step_labels:
            label.configure(wraplength=max(200, event.width))
    instructions.bind("<Configure>", fit_steps)
    ttk.Label(parent, textvariable=status, style="Muted.TLabel", wraplength=1100).pack(anchor="w", pady=(8, 0))
    app.apply_preferences()
    return dialog
