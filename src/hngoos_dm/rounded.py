"""Small native rounded surfaces and keyboard-accessible buttons for the download window."""

import tkinter as tk
from tkinter import ttk

from .ui_preferences import PALETTES


def rounded_rectangle(canvas, x, y, right, bottom, radius=14, **options):
    radius = min(radius, (right-x)/2, (bottom-y)/2)
    return canvas.create_polygon(x+radius, y, right-radius, y, right, y, right, y+radius,
        right, bottom-radius, right, bottom, right-radius, bottom, x+radius, bottom,
        x, bottom, x, bottom-radius, x, y+radius, x, y, smooth=True, splinesteps=24, **options)


class RoundedPanel(tk.Canvas):
    def __init__(self, parent, height=80, padding=16, radius=18, dashed=False):
        super().__init__(parent, height=height, width=1, highlightthickness=0, borderwidth=0)
        self.padding, self.radius, self.dashed = padding, radius, dashed
        self.theme = "dark"
        self.content = ttk.Frame(self, style="Card.TFrame")
        self.window = self.create_window(padding, padding, anchor="nw", window=self.content)
        self.bind("<Configure>", lambda _event: self.draw())

    def set_presentation(self, theme, *_args):
        self.theme = theme
        self.draw()

    def draw(self):
        background, panel, *_ = PALETTES[self.theme]
        self.configure(background=background)
        width, height = self.winfo_width(), self.winfo_height()
        self.delete("surface")
        rounded_rectangle(self, 1, 1, max(2, width-1), max(2, height-1), self.radius,
                          fill=panel, outline="#c5cede" if self.theme == "light" else "#30364b",
                          dash=(8, 5) if self.dashed else (), tags="surface")
        self.tag_lower("surface")
        self.itemconfigure(self.window, width=max(1, width-2*self.padding), height=max(1, height-2*self.padding))


class RoundedButton(tk.Canvas):
    def __init__(self, parent, text, command, width=120, height=38, primary=False, image=None):
        super().__init__(parent, width=width, height=height, highlightthickness=0, borderwidth=0,
                         takefocus=True, cursor="hand2")
        self.label, self.command, self.image = text, command, image
        self.primary, self.theme, self.translate = primary, "dark", str
        self.hover = False
        self.bind("<Configure>", lambda _event: self.draw())
        self.bind("<Enter>", lambda _event: self.enter(True))
        self.bind("<Leave>", lambda _event: self.enter(False))
        self.bind("<FocusIn>", lambda _event: self.draw())
        self.bind("<FocusOut>", lambda _event: self.draw())
        self.bind("<Button-1>", self.invoke)
        self.bind("<space>", self.invoke)
        self.bind("<Return>", self.invoke)

    def enter(self, hover):
        self.hover = hover
        self.draw()

    def invoke(self, _event=None):
        if self.cget("state") != "disabled":
            self.command()
        return "break"

    def configure(self, cnf=None, **options):
        options.pop("compound", None)
        for key, attribute in (("text", "label"), ("command", "command"), ("image", "image")):
            if key in options:
                setattr(self, attribute, options.pop(key))
        result = super().configure(cnf, **options)
        if hasattr(self, "theme"):
            self.draw()
        return result

    config = configure

    def set_presentation(self, theme, translate=str):
        self.theme, self.translate = theme, translate
        self.draw()

    def draw(self):
        background, panel, text, muted, accent = PALETTES[self.theme]
        if isinstance(self.master, ttk.Frame) and self.master.cget("style") == "Card.TFrame":
            background = panel
        super().configure(background=background)
        self.delete("all")
        light = self.theme == "light"
        fill = ("#6d28d9" if light else "#7c3aed") if self.primary else ("#e8ecf3" if light else "#242b3e")
        if self.hover and not self.primary:
            fill = "#dce3ee" if light else "#30394f"
        color = "white" if self.primary else text
        if self.cget("state") == "disabled":
            color = muted
        width, height = self.winfo_width(), self.winfo_height()
        rounded_rectangle(self, 1, 1, max(2, width-1), max(2, height-1), 11, fill=fill,
                          outline=accent if self.focus_get() == self else fill)
        label = self.translate(self.label)
        if self.image:
            self.create_image(22, height/2, image=self.image)
        self.create_text(width/2+(10 if self.image else 0), height/2, text=label, fill=color,
                         font=("Segoe UI", 10, "bold" if self.primary else "normal"))
