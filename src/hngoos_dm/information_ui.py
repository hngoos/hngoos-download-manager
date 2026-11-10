"""Information menu, local preferences and Chromium extension installation."""

import time
import tkinter as tk
from tkinter import ttk

from .rounded import RoundedPanel
from .ui_preferences import buffered_presentation

REPOSITORY = "https://github.com/hngoos/hngoos-download-manager"


class ExtensionExample(tk.Canvas):
    """Small vector examples, drawn into the app's shared presentation surface."""
    _hdm_surface_canvas = True

    def __init__(self, parent, app, kind):
        super().__init__(parent, width=1, height=64, highlightthickness=0, borderwidth=0)
        self.app, self.kind = app, kind
        self.bind("<Configure>", lambda _: self.draw())

    def set_presentation(self, *_args):
        self.draw()

    def draw(self):
        from .rounded import rounded_rectangle
        from .ui_preferences import PALETTES
        from .ui_scale import WindowScale
        scale = WindowScale(self.app.root)
        background, panel, text, muted, _ = PALETTES[self.app.theme]
        self.configure(background=background)
        self.delete("all")
        width, height = self.winfo_width(), self.winfo_height()
        rounded_rectangle(self, 1, 1, max(2, width-1), max(2, height-1), 12,
                          fill=panel, outline=muted, tags="surface")
        font = ("Segoe UI", scale.font_size(11, 9))
        if self.kind == "developer":
            self.create_text(18, height/2, anchor="w", text="Developer mode", fill=text, font=font)
            x = width-60
            self.create_line(x, height/2, x+24, height/2, width=20, capstyle="round", fill=muted)
            self.create_oval(x+16, height/2-7, x+30, height/2+7, fill=panel, outline=panel)
        else:
            self.create_text(18, height/2, anchor="w", text="Extensions", fill=muted, font=font)
            left = max(120, width-190)
            rounded_rectangle(self, left, height/2-18, width-12, height/2+18, 8, fill=panel, outline=text)
            self.create_text((left+width-12)/2, height/2, text="Load unpacked", fill=text, font=font)


def build_browser_settings(app, parent):
    from . import browser
    from .icons import load_browser_icons
    from .rounded import RoundedButton
    ttk.Label(parent, text="Trình duyệt", font=("Segoe UI", 16, "bold")).pack(anchor="w", pady=(0, 10))
    actions = ttk.Frame(parent)
    actions.pack(fill="x")
    app.browser_install_buttons = {}
    app.browser_icons = load_browser_icons(app.root)
    app.browser_icon_sizes = {48: app.browser_icons}
    for index, browser_id in enumerate(browser.supported_browsers()):
        available = browser.find_browser(browser_id) is not None
        button = RoundedButton(actions, text="",
                               command=lambda browser_id=browser_id: browser_dialog(app, browser_id),
                               width=54, height=60, flat=True, image=app.browser_icons[browser_id, available])
        button.configure(state="normal" if available else "disabled", cursor="hand2" if available else "arrow",
                         takefocus=available)
        button.grid(row=0, column=index, padx=(0, 2), pady=2)
        app.browser_install_buttons[browser_id] = button


def refresh_browser_availability(app):
    from . import browser
    for browser_id, button in getattr(app, "browser_install_buttons", {}).items():
        available = browser.find_browser(browser_id) is not None
        button.configure(state="normal" if available else "disabled", cursor="hand2" if available else "arrow",
                         takefocus=available)
        size = getattr(button.image, "width", lambda: 48)()
        artwork = app.browser_icon_sizes.get(size, app.browser_icons)
        button.configure(image=artwork[browser_id, available])


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

    @buffered_presentation
    def show(self):
        app = self.app
        if self in app.page_stack:
            return
        if not app.page_stack:
            app.resize_source_card()
        previous = app.page_stack[-1] if app.page_stack else app.tabs
        if hasattr(previous, "surface"):
            previous.surface.hide()
        previous.pack_forget()
        previous.place_forget()
        if not app.page_stack:
            app.url_panel.grid_remove()
            app.empty_panel.grid_remove()
            app.header_left.configure(height=app.brand_label.winfo_reqheight())
        app.page_stack.append(self)
        app.sync_update_notice()
        if self.beside_logo:
            self.place(relx=.04, rely=.05, relwidth=.90, relheight=.88)
            app.header.pack_forget()
            if hasattr(self, "position_columns"):
                self.position_columns()
            if hasattr(self, "surface"):
                self.surface.show()
        else:
            if getattr(previous, "beside_logo", False):
                app.header.place_forget()
                app.header.pack(before=app.view_host, fill="x", padx=18, pady=(0, 14))
            self.pack(fill="both", expand=True)
        app.schedule_redraw()

    @buffered_presentation
    def hide(self):
        app = self.app
        if self not in app.page_stack:
            return
        index = app.page_stack.index(self)
        for child in list(app.page_stack[index+1:])[::-1]:
            child.destroy()
        app.page_stack.remove(self)
        app.sync_update_notice()
        if hasattr(self, "surface"):
            self.surface.hide()
        self.place_forget()
        self.pack_forget()
        if not getattr(app, "_closing", False) and app.tabs.winfo_exists():
            previous = app.page_stack[-1] if app.page_stack else app.tabs
            if getattr(previous, "beside_logo", False):
                previous.place(relx=.04, rely=.05, relwidth=.90, relheight=.88)
                previous.position_columns()
                if hasattr(previous, "surface"):
                    previous.surface.show()
            else:
                previous.pack(fill="both", expand=True)
            if not app.page_stack:
                if self.beside_logo:
                    app.header.place_forget()
                    app.header.pack(before=app.view_host, fill="x", padx=18, pady=(0, 14))
                app.show_source_controls(app.source_controls_visible)
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
        refresh_browser_availability(app)
        previous.show()
        return previous
    dialog = app.preferences_dialog = ContentPage(app, "Thiết lập", beside_logo=True)
    body = dialog.body
    body.columnconfigure(0, weight=0)
    body.columnconfigure(1, weight=1)
    body.rowconfigure(0, weight=1)
    left, right = ttk.Frame(body), ttk.Frame(body)
    left.grid(row=0, column=1, sticky="new", padx=(24, 0))
    right.grid(row=0, column=0, sticky="nsew", padx=(0, 24))
    # Wrapping choices must not change their own column's width. Otherwise a
    # narrow column can alternate forever between one-line and wrapped layouts.
    right.pack_propagate(False)
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
        small = app.root.winfo_width() < 1050 or app.root.winfo_height() < 650
        dialog.place_configure(relx=.01 if small else .08 if wide else .04,
                               rely=.015 if small else .05,
                               relwidth=.98 if small else .85 if wide else .90,
                               relheight=.97 if small else .88)
        column_width = 280 if small else round(app.root.winfo_width()*(.34 if wide else .36))
        body.columnconfigure(0, minsize=column_width)
        left.grid_configure(padx=(10 if small else 24, 0))
        right.grid_configure(padx=(0, 10 if small else 24))
        logo_height = app.header_logo.height()
        app.header.pack_forget()
        app.header.place(x=18, y=0, width=app.header_logo.width()+8, height=logo_height)
        app.header.lift()
        # The compact page has a different top inset. Use that same inset to
        # reserve space beneath the logo instead of overlapping Appearance.
        page_top = round(app.shell.winfo_height()*(.015 if small else .05))
        right.grid_configure(pady=(max(0, logo_height+18-page_top), 0))
    dialog.position_columns = position_columns
    position_columns()
    def fit(_event=None):
        if not app.page_stack or app.page_stack[-1] is not dialog:
            return
        from .ui_scale import WindowScale
        scale = WindowScale(app.root)
        compact = app.root.winfo_height() < 1000
        small = app.root.winfo_width() < 1050 or app.root.winfo_height() < 650
        from types import SimpleNamespace

        from .rounded import ChoiceRow
        signature = (app.root.winfo_width(), app.root.winfo_height(), left.winfo_width(), right.winfo_width(),
                     app.theme, app.locale.language, scale.font_factor, app.proxy_mode.get())
        if getattr(dialog, "_fit_signature", None) == signature:
            return
        dialog._fit_signature = signature
        position_columns()
        style = ttk.Style(app.root)
        style.configure("Compact.TCheckbutton", font=("Segoe UI", scale.font_size(10, 9)), padding=0,
                        wraplength=max(150, left.winfo_width()-26))
        app.preference_directory.control.configure(font=("Segoe UI", scale.font_size(12, 9)))
        app.preference_directory.configure(height=scale.size(38, 34))
        for caption in app.preference_directory.master.winfo_children():
            if isinstance(caption, ttk.Label):
                caption.configure(font=("Segoe UI", scale.font_size(12, 9)))
        for caption, content in app.preference_rows.values():
            caption.configure(width=10 if small else 12, font=("Segoe UI", scale.font_size(12, 9)))
            caption.master.pack_configure(pady=scale.size(2, 1) if small else scale.size(5))
            caption.pack_configure(padx=(0, scale.size(12, 4)))
            for choices in content.winfo_children():
                if isinstance(choices, ChoiceRow):
                    for value, button in choices.buttons.items():
                        button.label_font.configure(size=scale.font_size(10, 9))
                        width = max(48, button.label_font.measure(app.locale.text(button.label))+scale.size(24, 12))
                        choices.widths[value] = width
                        button.configure(width=width, height=scale.size(36, 24))
                    choices.arrange(SimpleNamespace(width=choices.winfo_width()))
        from .icons import load_browser_icons, load_contact_icons
        count = max(1, len(app.browser_install_buttons))
        browser_width = scale.size(54, 30)
        if right.winfo_width() > 1:
            browser_width = min(browser_width, max(24, (right.winfo_width()-2*count)//count))
        browser_size = min(scale.size(48, 24), max(20, browser_width-4))
        if browser_size not in app.browser_icon_sizes:
            app.browser_icon_sizes[browser_size] = load_browser_icons(app.root, browser_size)
        for browser_id, button in app.browser_install_buttons.items():
            button.configure(width=browser_width, height=scale.size(60, 30))
            available = str(button.cget("state")) != "disabled"
            button.image = app.browser_icon_sizes[browser_size][browser_id, available]
            button.draw()
        contact_size = scale.size(36, 24)
        if contact_size not in app.contact_icon_sizes:
            app.contact_icon_sizes[contact_size] = load_contact_icons(app.root, contact_size)
        for label, button in app.contact_buttons.items():
            button.configure(width=scale.size(44, 30), height=scale.size(44, 30),
                             image=app.contact_icon_sizes[contact_size][label])
        for value, button in app.proxy_choices.buttons.items():
            button.label_font.configure(size=scale.font_size(10, 9))
            width = button.label_font.measure(app.locale.text(button.label))+scale.size(20, 12)
            app.proxy_choices.widths[value] = width
            button.configure(width=width, height=scale.size(36, 24))
        app.proxy_choices.pack_configure(pady=2 if small else scale.size(8, 2))
        if app.proxy_address_row.winfo_manager():
            app.proxy_address_row.pack_configure(pady=2 if small else 8)
        app.proxy_choices.arrange(SimpleNamespace(width=app.proxy_choices.winfo_width()))
        for button, natural in ((app.preference_report_button, 140), (app.preference_update_button, 180),
                                (app.preference_reset_button, 180)):
            button.label_font.configure(size=scale.font_size(10, 9))
            button.configure(width=min(scale.size(natural, 90), max(90, (left.winfo_width()-20)//3)), height=scale.size(40, 32))
        contact.winfo_children()[0].pack_configure(pady=(0, 2 if small else 4 if compact else 8))
        contact.winfo_children()[2].pack_configure(pady=(2, 0) if small else (4, 4) if compact else (6, 8))
        for title in dialog.sections:
            section = dialog.sections[title]
            section.pack_configure(pady=(0, 2 if small else 4 if compact else 20))
            for control in section.winfo_children():
                if isinstance(control, ttk.Checkbutton):
                    control.pack_configure(pady=0 if compact else 4, fill="x")
                    control.configure(style="Compact.TCheckbutton")
                elif isinstance(control, ttk.Label) and control.pack_info().get("anchor") == "w":
                    if not hasattr(control, "_full_size_font"):
                        control._full_size_font = control.cget("font")
                    heading = control is section.winfo_children()[0]
                    control.configure(font=("Segoe UI", scale.font_size(16, 11), "bold") if heading else
                                      ("Segoe UI", scale.font_size(10, 9)))
                    if "pady" in control.pack_info():
                        control.pack_configure(pady=(0, 3 if small else 8))
    def schedule_fit(event):
        # Source layout and image scaling share the app's frame scheduler.
        # Native child geometry can emit several Configure events per frame.
        if event.widget in {dialog, left, right}:
            app.schedule_source_resize()
    dialog.bind("<Configure>", schedule_fit)
    left.bind("<Configure>", schedule_fit)
    right.bind("<Configure>", schedule_fit)
    dialog.fit = fit
    fit()
    app.apply_preferences()
    dialog.surface = app.presentation_surface
    dialog.surface.show()
    return dialog


def build_contact_settings(app, parent):
    from . import __version__

    ttk.Label(parent, text="Liên hệ", font=("Segoe UI", 16, "bold")).pack(anchor="w", pady=(0, 8))
    ttk.Label(parent, text=f"Hngoos Download Manager · {__version__}").pack(anchor="w")
    build_contact_links(app, parent).pack(anchor="w", pady=(6, 8))


def build_contact_links(app, parent):
    import webbrowser

    from .icons import load_contact_icons
    from .rounded import RoundedButton
    links = ttk.Frame(parent)
    app.contact_icons = load_contact_icons(app.root)
    app.contact_icon_sizes = {36: app.contact_icons}
    app.contact_buttons = {}
    for label, url in (("Facebook", "https://www.facebook.com/hngoos"),
                       ("Instagram", "https://www.instagram.com/hngoos"),
                       ("Gmail", "mailto:1hngoos@gmail.com"), ("GitHub", "https://github.com/hngoos")):
        link = RoundedButton(links, text="", image=app.contact_icons[label], width=44, height=44,
                             flat=True, command=lambda url=url: webbrowser.open(url))
        link.accessible_name = label
        link.pack(side="left", padx=5)
        app.contact_buttons[label] = link
    return links


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
    dialog.folder_path = bundled_extension_path()
    parent = dialog.body
    name = browser.BROWSERS[browser_id][0]
    header = ttk.Frame(parent)
    header.pack(fill="x", pady=(8, 18))
    dialog.browser_title = ttk.Label(header, text=name, font=("Segoe UI", 20, "bold"))
    dialog.browser_title.pack(side="left")
    ttk.Label(header, text="Tiện ích trình duyệt", style="Muted.TLabel").pack(side="right")
    status = dialog.status = tk.StringVar()
    selector = ttk.Frame(parent)
    selector.pack(fill="x", pady=(0, 16))
    from .icons import load_browser_icons
    dialog.browser_icons = load_browser_icons(app.root, 24)
    dialog.browser_buttons = {}
    for index, selected in enumerate(browser.supported_browsers()):
        available = browser.find_browser(selected) is not None
        button = RoundedButton(selector, text=browser.BROWSERS[selected][0],
            image=dialog.browser_icons[selected, available], flat=True, width=120, height=36,
            command=lambda selected=selected: browser_dialog(app, selected))
        button.configure(state="normal" if available else "disabled")
        button.grid(row=index//4, column=index%4, sticky="w", padx=(0, 8), pady=2)
        dialog.browser_buttons[selected] = button

    def connect_folder():
        try:
            source = dialog.folder_path
            manifest = json.loads((source/"manifest.json").read_text(encoding="utf-8"))
            if (manifest.get("manifest_version") != 3 or manifest.get("name") != "Hngoos Download Manager"
                    or not (source/"background.js").is_file()):
                raise ValueError("Không tìm thấy tiện ích HDM trong thư mục extension. Hãy cài lại HDM.")
            browser.connect_extension(source, app.data_dir)
            status.set("")
        except (OSError, ValueError) as error:
            status.set(app.locale.text(str(error)))

    folder_row = ttk.Frame(parent)
    folder_row.columnconfigure(0, weight=0)
    dialog.folder_label = ttk.Label(folder_row, text=str(dialog.folder_path), style="Muted.TLabel",
                                      font=("Segoe UI", 11), wraplength=900)
    dialog.folder_label.translate_text = False
    instructions = ttk.Frame(parent)
    instructions.pack(fill="both", expand=True)
    extension_page = browser.BROWSERS[browser_id][1]+"://extensions"
    steps = (
        "Bước 1: Mở trang tiện ích trình duyệt tại:",
        "Bước 2: Bật Chế độ nhà phát triển (Developer mode).",
        "Bước 3: Chọn Tải tiện ích đã giải nén (Load unpacked), rồi chọn thư mục extension có sẵn cùng HDM:",
    )
    def open_page(_event=None):
        try:
            browser.open_extensions(browser_id)
        except OSError as error:
            status.set(app.locale.text(str(error)))
        return "break"

    def copy(value):
        app.root.clipboard_clear()
        app.root.clipboard_append(value)
        status.set(app.locale.text("Đã sao chép."))

    dialog.copy_folder = RoundedButton(folder_row, text="", image=app.icons["copy"], flat=True,
        width=32, height=32, command=lambda: copy(str(dialog.folder_path)))
    dialog.copy_folder.accessible_name = "Sao chép đường dẫn thư mục"
    dialog.folder_label.grid(row=0, column=0, sticky="w")
    dialog.copy_folder.grid(row=0, column=1, padx=(8, 0), sticky="w")
    from .platforms import open_path
    dialog.open_folder = RoundedButton(folder_row, text="Mở thư mục tiện ích", image=app.icons["folder"],
        width=190, height=36, flat=True, command=lambda: app.guarded(lambda: open_path(dialog.folder_path)))
    dialog.open_folder.grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))

    dialog.step_labels = []
    dialog.examples = []
    for index, step in enumerate(steps):
        row = ttk.Frame(instructions)
        row.pack(fill="x", pady=(3, 8))
        label = ttk.Label(row, text=app.locale.text(step),
                          font=("Segoe UI", 12), wraplength=520, justify="left")
        label.pack(side="left" if index == 0 else "top", anchor="w")
        dialog.step_labels.append(label)
        if index == 0:
            label.configure(wraplength=0)
            dialog.extension_link = ttk.Label(row, text=extension_page, cursor="hand2", takefocus=True,
                                             font=("Segoe UI", 12, "underline"))
            dialog.extension_link.translate_text = False
            dialog.extension_link.surface_command = open_page
            dialog.extension_link.pack(side="left", padx=(6, 0))
            dialog.copy_address = RoundedButton(row, text="", image=app.icons["copy"], flat=True,
                width=28, height=28, command=lambda: copy(extension_page))
            dialog.copy_address.pack(side="left", padx=(6, 0))
            dialog.copy_address.accessible_name = "Sao chép địa chỉ trang tiện ích"
            for sequence in ("<Button-1>", "<Return>", "<space>"):
                dialog.extension_link.bind(sequence, open_page)
        if index == 2:
            folder_row.pack(in_=row, fill="x", pady=(4, 0))
        if index in (1, 2):
            example = ExtensionExample(row, app, "developer" if index == 1 else "unpacked")
            example.configure(width=480)
            example.pack(anchor="w", padx=(12, 0), pady=(6, 2))
            dialog.examples.append(example)
    def fit_steps(event):
        dialog.folder_label.configure(wraplength=max(120, event.width-48))
        for label in dialog.step_labels[1:]:
            label.configure(wraplength=max(200, event.width))
        from .ui_scale import WindowScale
        scale = WindowScale(app.root)
        for example in dialog.examples:
            if app.root.winfo_height() < 650:
                example.pack_forget()
            else:
                example.configure(height=scale.size(64, 48), width=min(480, max(200, event.width-24)))
                example.pack(anchor="w", padx=(12, 0), pady=(6, 2))
        for button in dialog.browser_buttons.values():
            button.label_font.configure(size=scale.font_size(10, 9))
            button.configure(width=max(100, min(150, (event.width-32)//4)), height=scale.size(36, 28))
    instructions.bind("<Configure>", fit_steps)
    ttk.Label(parent, textvariable=status, style="Muted.TLabel", wraplength=1100).pack(anchor="w", pady=(8, 0))
    connect_folder()
    app.apply_preferences()
    return dialog
