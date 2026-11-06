"""Small native dashboard surfaces, without a browser runtime."""

import ctypes
import os
import tkinter as tk


def motion_enabled():
    if os.name != "nt":
        return True
    enabled = ctypes.c_int(1)
    if ctypes.windll.user32.SystemParametersInfoW(0x1042, 0, ctypes.byref(enabled), 0):
        return bool(enabled.value)
    return True


class QueueOverview(tk.Canvas):
    def __init__(self, parent):
        super().__init__(parent, height=96, background="#0f121c", highlightthickness=0)
        self.values = ("0", "0", "0 B/s")
        self.theme = "dark"
        self.translate = str
        self.bind("<Configure>", lambda _event: self.draw())

    def update_values(self, active, completed, speed):
        values = (str(active), str(completed), speed)
        if values != self.values:
            self.values = values
            self.draw()

    def set_presentation(self, theme, translate):
        self.theme, self.translate = theme, translate
        self.draw()

    def draw(self):
        from .ui_preferences import PALETTES
        bg, panel, text, muted, accent = PALETTES[self.theme]
        self.configure(background=bg)
        self.delete("all")
        width = max(1, self.winfo_width())
        card_width = (width-24)/3
        labels = ("ĐANG TẢI", "HOÀN TẤT", "TỐC ĐỘ HIỆN TẠI")
        colors = (accent, "#187a57", "#245caa") if self.theme == "light" else (accent, "#6ee7b7", "#93c5fd")
        for index, (label, value, color) in enumerate(zip(labels, self.values, colors, strict=True)):
            x, right = index*(card_width+12), index*(card_width+12)+card_width
            self.create_polygon(x+12, 0, right-12, 0, right, 0, right, 12, right, 76,
                right, 88, right-12, 88, x+12, 88, x, 88, x, 76, x, 12, x, 0,
                smooth=True, fill=panel, outline="#d4dbe8" if self.theme == "light" else "#282d40")
            self.create_line(x+19, 21, x+19, 66, fill=color, width=3)
            self.create_text(x+33, 24, text=self.translate(label), anchor="w", fill=muted, font=("Segoe UI", 9))
            self.create_text(x+33, 56, text=value, anchor="w", fill=text, font=("Segoe UI", 22, "bold"))
