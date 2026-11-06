"""Rounded category navigation and a live transfer-rate / bandwidth control."""

import tkinter as tk
from tkinter import ttk

from .filters import FILTERS
from .rounded import RoundedButton, RoundedPanel


class Tooltip:
    def __init__(self, widget, text):
        self.widget, self.text, self.window, self.timer = widget, text, None, None
        widget.bind("<Enter>", self.schedule, add="+")
        widget.bind("<FocusIn>", self.schedule, add="+")
        for event in ("<Leave>", "<FocusOut>", "<Button-1>"):
            widget.bind(event, self.hide, add="+")
        widget.bind("<Destroy>", lambda event: self.hide() if event.widget == widget else None, add="+")

    def schedule(self, _event=None):
        self.hide()
        self.timer = self.widget.after(450, self.show)

    def show(self):
        self.timer = None
        self.window = tk.Toplevel(self.widget)
        self.window.wm_overrideredirect(True)
        self.window.geometry(f"+{self.widget.winfo_rootx()}+{self.widget.winfo_rooty()+self.widget.winfo_height()+6}")
        ttk.Label(self.window, text=self.text(), padding=8).pack()

    def hide(self, _event=None):
        if self.timer is not None:
            self.widget.after_cancel(self.timer)
            self.timer = None
        if self.window is not None:
            self.window.destroy()
            self.window = None


class CategoryBar(ttk.Frame):
    def __init__(self, app, parent):
        super().__init__(parent)
        self.app, self.buttons = app, {}
        for key, text, icon in FILTERS:
            button = RoundedButton(self, text=text, command=lambda key=key: app.set_filter(key),
                                   image=app.icons[icon], width=94 if text == "Archive" else 80, height=40)
            button.pack(side="left", padx=(0, 4))
            self.buttons[key] = button

    def set_presentation(self, theme, translate):
        for key, _text, icon in FILTERS:
            button = self.buttons[key]
            button.primary = self.app.category_filter == key
            button.image = self.app.primary_icons[icon] if button.primary else self.app.icons[icon]
            button.set_presentation(theme, translate)


class SpeedMeter(RoundedPanel):
    def __init__(self, app, parent):
        super().__init__(parent, height=44, padding=6, radius=20)
        self.app = app
        self.configure(width=310)
        self.down, self.up = tk.StringVar(value="0 B/s"), tk.StringVar(value="0 B/s")
        self.down_icon = ttk.Label(self.content, style="Card.TLabel")
        self.down_icon.pack(side="left", padx=(4, 3))
        ttk.Label(self.content, textvariable=self.down, style="Card.TLabel").pack(side="left", padx=(0, 8))
        self.up_icon = ttk.Label(self.content, style="Card.TLabel")
        self.up_icon.pack(side="left", padx=(0, 3))
        ttk.Label(self.content, textvariable=self.up, style="Card.TLabel").pack(side="left", padx=(0, 8))
        self.mode = RoundedButton(self.content, text="HIGH", image=app.icons["activity"],
                                  command=self.open_menu, width=92, height=32)
        self.mode.pack(side="right")
        self.menu = None

    def open_menu(self):
        from .ui_preferences import PALETTES
        if self.menu:
            self.menu.destroy()
        _, panel, text, _, accent = PALETTES[self.app.theme]
        self.menu = tk.Menu(self, tearoff=False, background=panel, foreground=text,
                            activebackground=accent, activeforeground="white")
        self.choice = tk.StringVar(value=self.app.store.setting("bandwidth_mode", "maximum"))
        for key, label in (("maximum", "Tối đa"), ("medium", "Vừa (4 MB/s)"), ("light", "Nhẹ (512 KB/s)")):
            self.menu.add_radiobutton(label=self.app.locale.text(label), variable=self.choice, value=key,
                command=lambda key=key: self.app.set_bandwidth(key))
        try:
            self.menu.tk_popup(self.winfo_rootx(), self.winfo_rooty()-110)
        finally:
            self.menu.grab_release()

    def update_rates(self, down, up):
        from .app import human
        self.down.set("0 B/s" if not down else human(down)+"/s")
        self.up.set("0 B/s" if not up else human(up)+"/s")

    def set_presentation(self, theme, translate=str):
        super().set_presentation(theme, translate)
        self.down_icon.configure(image=self.app.icons["arrow-down"])
        self.up_icon.configure(image=self.app.icons["arrow-up"])
        self.mode.image = self.app.icons["activity"]
        mode = self.app.store.setting("bandwidth_mode", "maximum")
        self.mode.label = {"maximum": "HIGH", "medium": "MEDIUM", "light": "LOW"}[mode]
        self.mode.set_presentation(theme, translate)
