"""Live download and upload rates."""

import tkinter as tk
from tkinter import ttk


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
