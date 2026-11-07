"""Live download and upload rates."""

import tkinter as tk
from tkinter import ttk


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


class SpeedMeter(ttk.Frame):
    def __init__(self, app, parent):
        super().__init__(parent)
        self.app = app
        self.down, self.up = tk.StringVar(value="0 B/s"), tk.StringVar(value="0 B/s")
        ttk.Label(self, textvariable=self.down).pack(side="left", padx=(0, 12))
        ttk.Label(self, textvariable=self.up).pack(side="left")

    def update_rates(self, down, up):
        from .app import human
        self.down.set("0 B/s" if not down else human(down)+"/s")
        self.up.set("0 B/s" if not up else human(up)+"/s")
