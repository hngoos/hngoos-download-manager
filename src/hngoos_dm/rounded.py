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
    def __init__(self, parent, height=80, padding=16, radius=26, dashed=False):
        super().__init__(parent, height=height, width=1, highlightthickness=0, borderwidth=0)
        self.padding, self.radius, self.dashed = padding, radius, dashed
        self.theme = "dark"
        self.content = ttk.Frame(self, style="Card.TFrame")
        self.window = self.create_window(padding, padding, anchor="nw", window=self.content)
        self.bind("<Configure>", lambda _event: self.draw())
        self.reveal_timer = None
        self.bind("<Destroy>", self.cancel_reveal, add="+")

    def cancel_reveal(self, event=None):
        if (event is None or event.widget == self) and self.reveal_timer is not None:
            self.after_cancel(self.reveal_timer)
            self.reveal_timer = None

    def set_presentation(self, theme, *_args):
        self.theme = theme
        self.draw()

    def reveal(self):
        """A short content reveal; honor the OS reduced-motion preference."""
        from .widgets import motion_enabled
        self.cancel_reveal()
        self._reveal_generation = getattr(self, "_reveal_generation", 0)+1
        generation = self._reveal_generation
        frames = 10 if motion_enabled() else 0
        def tick(frame=0):
            self.reveal_timer = None
            if not self.winfo_exists() or generation != self._reveal_generation:
                return
            offset = 12*(1-frame/max(1, frames))**3 if frames else 0
            self.coords(self.window, self.padding, self.padding+offset)
            if frame < frames:
                self.reveal_timer = self.after(16, tick, frame+1)
        tick()

    def draw(self):
        background, panel, *_ = PALETTES[self.theme]
        self.configure(background=background)
        width, height = self.winfo_width(), self.winfo_height()
        self.delete("surface")
        rounded_rectangle(self, 1, 1, max(2, width-1), max(2, height-1), self.radius,
                          fill=panel, outline="#d0d0d0" if self.theme == "light" else "#3a3a3a",
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
        fill = ("#6d28d9" if light else "#7c3aed") if self.primary else ("#ececec" if light else "#272727")
        if self.hover and not self.primary:
            fill = "#e4e4e4" if light else "#333333"
        color = "white" if self.primary else text
        if self.cget("state") == "disabled":
            color = muted
        width, height = self.winfo_width(), self.winfo_height()
        rounded_rectangle(self, 1, 1, max(2, width-1), max(2, height-1), 18, fill=fill,
                          outline=accent if self.focus_get() == self else fill)
        label = self.translate(self.label)
        if self.image:
            self.create_image(20 if label else width/2, height/2, image=self.image)
        self.create_text(width/2+(12 if self.image and label else 0), height/2, text=label, fill=color,
                         font=("Segoe UI", 10, "bold" if self.primary else "normal"))


class RoundedField(tk.Canvas):
    """Keep native text editing, selection and keyboard behavior inside a rounded border."""
    control_class = ttk.Entry

    def __init__(self, parent, **options):
        width = options.pop("width", 20)
        super().__init__(parent, width=max(90, width*8), height=38, highlightthickness=0,
                         borderwidth=0, takefocus=False)
        self.theme = "dark"
        options.setdefault("style", "Rounded.TCombobox" if self.control_class is ttk.Combobox else "Rounded.TEntry")
        self.control = self.control_class(self, **options)
        self.window = self.create_window(9, 4, anchor="nw", window=self.control)
        super().bind("<Configure>", lambda _: self.draw())
        self.control.bind("<FocusIn>", lambda _: self.draw(), add="+")
        self.control.bind("<FocusOut>", lambda _: self.draw(), add="+")

    def set_presentation(self, theme, *_args):
        self.theme = theme
        self.draw()

    def configure(self, cnf=None, **options):
        control_options = {}
        for key in ("state", "values", "textvariable", "show", "validate", "validatecommand"):
            if key in options:
                control_options[key] = options.pop(key)
        if control_options:
            self.control.configure(**control_options)
        return super().configure(cnf, **options)

    config = configure

    def draw(self):
        background, panel, _text, muted, accent = PALETTES[self.theme]
        if isinstance(self.master, ttk.Frame) and self.master.cget("style") == "Card.TFrame":
            background = panel
        super().configure(background=background)
        tk.Canvas.delete(self, "surface")
        width, height = self.winfo_width(), self.winfo_height()
        rounded_rectangle(self, 1, 1, max(2, width-1), max(2, height-1), 16, fill=panel,
            outline=accent if self.focus_get() == self.control else muted, tags="surface")
        self.tag_lower("surface")
        self.itemconfigure(self.window, width=max(1, width-18), height=max(1, height-8))

    def bind(self, *args, **kwargs):
        return self.control.bind(*args, **kwargs)

    def focus_set(self):
        self.control.focus_set()

    def focus_force(self):
        self.control.focus_force()

    def event_generate(self, *args, **kwargs):
        self.control.event_generate(*args, **kwargs)

    def get(self):
        return self.control.get()

    def insert(self, *args):
        return self.control.insert(*args)

    def delete(self, *args):
        return self.control.delete(*args)


class RoundedEntry(RoundedField):
    pass


class RoundedCombobox(RoundedField):
    control_class = ttk.Combobox

    def current(self, *args):
        return self.control.current(*args)
