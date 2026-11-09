"""Small native rounded surfaces and keyboard-accessible buttons for the download window."""

import tkinter as tk
from tkinter import ttk

from .ui_fonts import owned_font
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
    def __init__(self, parent, text, command, width=120, height=38, primary=False, image=None, flat=False,
                 align="center", translate_text=True):
        super().__init__(parent, width=width, height=height, highlightthickness=0, borderwidth=0,
                         takefocus=True, cursor="hand2")
        self.label, self.command, self.image = text, command, image
        self.primary, self.theme, self.translate = primary, "dark", str
        self.flat = flat
        self.align, self.translate_text = align, translate_text
        self.label_font = owned_font(self, family="Segoe UI", size=10, weight="bold" if primary else "normal")
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
        if isinstance(self.master, ttk.Frame) and str(self.master.cget("style")).endswith("Card.TFrame"):
            background = panel
        background = getattr(self, "surface_background", background)
        super().configure(background=background)
        self.delete("all")
        light = self.theme == "light"
        fill = accent if self.primary else ("#ececec" if light else "#272727")
        if self.hover and not self.primary:
            fill = "#e4e4e4" if light else "#333333"
        if self.flat:
            fill = background
        color = ("white" if light else "#10252f") if self.primary else text
        if self.cget("state") == "disabled":
            color = muted
        width, height = self.winfo_width(), self.winfo_height()
        rounded_rectangle(self, 1, 1, max(2, width-1), max(2, height-1), 18, fill=fill,
                          outline=fill)
        label = self.translate(self.label) if self.translate_text else self.label
        label_width = self.label_font.measure(label)
        if self.align == "right":
            self.create_text(width-2, height/2, text=label, fill=color, anchor="e", font=self.label_font)
            if self.image:
                self.create_image(width-label_width-18, height/2, image=self.image)
            return
        if self.image:
            self.create_image(20 if label else width/2, height/2, image=self.image)
        self.create_text(width/2+(12 if self.image and label else 0), height/2, text=label, fill=color,
                         font=self.label_font)


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
        background, panel, _text, muted, _accent = PALETTES[self.theme]
        if isinstance(self.master, ttk.Frame) and str(self.master.cget("style")).endswith("Card.TFrame"):
            background = panel
        super().configure(background=background)
        tk.Canvas.delete(self, "surface")
        width, height = self.winfo_width(), self.winfo_height()
        rounded_rectangle(self, 1, 1, max(2, width-1), max(2, height-1), 16, fill=panel,
            outline=muted, tags="surface")
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
    """Fixed-width native entry, optionally reserving a non-editable file extension."""
    def __init__(self, parent, **options):
        self.suffix = options.pop("suffix", None)
        action_image = options.pop("action_image", None)
        action_command = options.pop("action_command", None)
        super().__init__(parent, **options)
        self.action_button = None
        if action_image is not None:
            self.action_button = RoundedButton(self, text="", image=action_image, command=action_command,
                                               width=32, height=30, flat=True)
            self.action_window = self.create_window(0, 0, window=self.action_button, anchor="center")
        self.text_font = owned_font(self.control, font=self.control.cget("font"))
        self.suffix_trace = self.suffix.trace_add("write", lambda *_: self.draw()) if self.suffix else None
        tk.Canvas.bind(self, "<Destroy>", self.cleanup, add="+")

    def cleanup(self, event):
        if event.widget == self and self.suffix_trace:
            self.suffix.trace_remove("write", self.suffix_trace)

    def draw(self):
        super().draw()
        action = getattr(self, "action_button", None)
        reserved = 36 if action is not None else 0
        if action is not None:
            action.surface_background = PALETTES[self.theme][1]
            action.set_presentation(self.theme)
            self.coords(self.action_window, self.winfo_width()-20, self.winfo_height()/2)
            self.itemconfigure(self.window, width=max(1, self.winfo_width()-18-reserved))
        if self.suffix is not None and hasattr(self, "text_font"):
            suffix = self.suffix.get()
            extra = min(self.winfo_width()/3, self.text_font.measure(suffix)+12) if suffix else 0
            self.itemconfigure(self.window, width=max(1, self.winfo_width()-18-extra-reserved))
            if suffix:
                color = PALETTES[self.theme][3 if str(self.control.cget("state")) == "disabled" else 2]
                self.create_text(self.winfo_width()-extra-reserved, self.winfo_height()/2, anchor="w", text=suffix,
                                 fill=color, font=self.text_font, tags="surface")


class UnderlinedEntry(RoundedField):
    """Native editable text with one underline and no surrounding input border."""
    def __init__(self, parent, **options):
        self.suffix = options.pop("suffix", None)
        self.minimum_width = options.pop("minimum_width", 70)
        self.fill_width = options.pop("fill_width", False)
        font = options.pop("font", ("Segoe UI", 10))
        self.value = options.get("textvariable")
        super().__init__(parent, **options)
        self.control.configure(font=font)
        self.text_font = owned_font(self.control, font=self.control.cget("font"))
        self.traces = []
        for variable in (self.value, self.suffix):
            if variable is not None:
                self.traces.append((variable, variable.trace_add("write", lambda *_: self.draw())))
        self.bind_id = self.master.bind("<Configure>", self.available_width_changed, add="+")
        tk.Canvas.bind(self, "<Destroy>", self.cleanup, add="+")
        tk.Canvas.configure(self, height=max(26, self.control.winfo_reqheight()+4))

    def available_width_changed(self, _event=None):
        if self.winfo_exists():
            self.draw()

    def configure_font(self, font):
        if getattr(self, "_configured_font", None) != font:
            self.text_font.configure(family=font[0], size=font[1])
            self._configured_font = font
            self.control.configure(font=self.text_font)
            self.draw()

    def cleanup(self, event):
        if event.widget == self:
            for variable, trace in self.traces:
                variable.trace_remove("write", trace)
            self.master.unbind("<Configure>", self.bind_id)

    def draw(self):
        if not hasattr(self, "text_font"):
            return
        background, panel, _text, muted, _accent = PALETTES[self.theme]
        if isinstance(self.master, ttk.Frame) and str(self.master.cget("style")).endswith("Card.TFrame"):
            background = panel
        tk.Canvas.configure(self, background=background)
        tk.Canvas.delete(self, "surface")
        suffix = self.suffix.get() if self.suffix is not None else ""
        extra = self.text_font.measure(suffix)+4 if suffix else 0
        requested = max(self.minimum_width if not self.control.get() else 12, self.text_font.measure(self.control.get())+10)+extra
        available = max(20, self.master.winfo_width()-self.winfo_x()-4)
        width = max(20, self.winfo_width()) if self.fill_width else min(requested, available)
        if not self.fill_width:
            tk.Canvas.configure(self, width=width)
        height = self.winfo_height()
        editable_width = max(6, width-extra)
        text_height = self.control.winfo_reqheight()
        text_top = (height-text_height)//2
        # Canvas strokes must stay outside the native Entry window to remain visible.
        line_y = text_top+text_height
        self.create_line(2, line_y, max(3, editable_width-2), line_y,
                         fill=muted, tags="surface")
        if suffix:
            self.create_text(editable_width, height/2, anchor="w", text=suffix,
                             fill=_text, font=self.text_font, tags="surface")
        self.coords(self.window, 3, text_top)
        self.itemconfigure(self.window, width=max(1, editable_width-6), height=text_height)


class ChoiceRow(ttk.Frame):
    """Visible wrapping choices with an accessible selected state and arrow keys."""
    def __init__(self, parent, variable, choices, command, app):
        style = "Card.TFrame" if isinstance(parent, ttk.Frame) and parent.cget("style") == "Card.TFrame" else "TFrame"
        super().__init__(parent, style=style)
        self.variable, self.command, self.app = variable, command, app
        self.buttons, self.widths = {}, {}
        for label, value in choices:
            width = max(84, len(label)*8+38)
            button = RoundedButton(self, text=label, command=lambda value=value: self.select(value),
                                   width=width, height=36)
            button.bind("<Right>", lambda _, value=value: self.move(value, 1))
            button.bind("<Left>", lambda _, value=value: self.move(value, -1))
            self.buttons[value], self.widths[value] = button, width
        self.bind("<Configure>", self.arrange)
        self.trace = self.variable.trace_add("write", lambda *_: self.present())
        self.bind("<Destroy>", self.cleanup, add="+")
        self.present()

    def cleanup(self, event):
        if event.widget == self:
            self.variable.trace_remove("write", self.trace)

    def select(self, value):
        if str(self.buttons[value].cget("state")) == "disabled":
            return
        self.variable.set(value)
        self.command()

    def move(self, value, direction):
        values = [key for key, button in self.buttons.items() if str(button.cget("state")) != "disabled"]
        if value not in values:
            return "break"
        value = values[(values.index(value)+direction) % len(values)]
        self.buttons[value].focus_set()
        self.select(value)
        return "break"

    def present(self):
        for value, button in self.buttons.items():
            button.primary = value == self.variable.get() and str(button.cget("state")) != "disabled"
            button.set_presentation(self.app.theme, self.app.locale.text)

    def arrange(self, event):
        row, column, used = 0, 0, 0
        for value, button in self.buttons.items():
            width = self.widths[value]+8
            if used+width > event.width and column:
                row, column, used = row+1, 0, 0
            button.grid(row=row, column=column, sticky="w", padx=(0, 8), pady=3)
            column, used = column+1, used+width


class RoundedCombobox(RoundedField):
    control_class = ttk.Combobox

    def current(self, *args):
        return self.control.current(*args)


class RoundedScrollbar(tk.Canvas):
    """A narrow rounded thumb; supports dragging, paging and native yview callbacks."""
    def __init__(self, parent, command):
        super().__init__(parent, width=12, height=1, highlightthickness=0,
                         borderwidth=0, takefocus=False)
        self.command, self.first, self.last = command, 0.0, 1.0
        self.theme, self.hover, self.drag = "dark", False, None
        self.bind("<Configure>", lambda _: self.draw())
        self.bind("<Enter>", lambda _: self.enter(True))
        self.bind("<Leave>", lambda _: self.enter(False))
        self.bind("<Button-1>", self.press)
        self.bind("<B1-Motion>", self.motion)
        self.bind("<ButtonRelease-1>", lambda _: setattr(self, "drag", None))
        self.bind("<MouseWheel>", lambda e: self.command("scroll", -int(e.delta/120), "units"))

    def set(self, first, last):
        self.first, self.last = float(first), float(last)
        self.draw()

    def set_presentation(self, theme, *_args):
        self.theme = theme
        self.draw()

    def enter(self, value):
        self.hover = value
        self.draw()

    def bounds(self):
        track = max(1, self.winfo_height()-8)
        size = min(track, max(28, track*(self.last-self.first)))
        travel = track-size
        start = 4+travel*self.first/max(1e-6, 1-(self.last-self.first))
        return start, size, travel

    def draw(self):
        self.configure(background=PALETTES[self.theme][1])
        self.delete("all")
        if self.last-self.first >= 0.999:
            return
        start, size, _ = self.bounds()
        color = ("#777777" if self.hover else "#a6a6a6") if self.theme == "light" else (
            "#888888" if self.hover else "#555555")
        self.create_line(6, start+3, 6, start+size-3, width=6, capstyle="round", fill=color, tags="thumb")

    def press(self, event):
        start, size, _ = self.bounds()
        if start <= event.y <= start+size:
            self.drag = event.y, self.first
        else:
            self.command("scroll", -1 if event.y < start else 1, "pages")

    def motion(self, event):
        if self.drag is None:
            return
        _, _, travel = self.bounds()
        fraction = 1-(self.last-self.first)
        target = self.drag[1]+(event.y-self.drag[0])*fraction/max(1, travel)
        self.command("moveto", max(0, min(fraction, target)))


class RoundedMenu(tk.Toplevel):
    """A keyboard accessible rounded popup shared by Info and row actions."""
    def __init__(self, app):
        super().__init__(app.root)
        self.withdraw()
        self.overrideredirect(True)
        self.transient(app.root)
        self.app, self.items, self.buttons = app, [], []
        self.focus_timer, self.outside_binding, self.anchor = None, None, None
        self.hover_timer = None
        self.surface = tk.Canvas(self, highlightthickness=0, borderwidth=0)
        self.surface.pack(fill="both", expand=True)
        self.content = ttk.Frame(self.surface, style="Card.TFrame")
        self.surface.create_window(10, 10, anchor="nw", window=self.content, width=280)
        self.bind("<Escape>", lambda _: self.destroy())
        self.bind("<FocusOut>", self.schedule_focus_check)
        self.bind("<Up>", lambda _: self.move(-1))
        self.bind("<Down>", lambda _: self.move(1))
        self.surface.bind("<Configure>", lambda _: self.draw())

    def add_command(self, label, command, icon=None):
        self.items.append((label, command, icon))

    def add_separator(self):
        self.items.append(None)

    def add_cascade(self, label, menu, icon=None):
        def submenu():
            parent_items = self.items
            self.items = [(self.app.locale.text("Quay lại"), lambda: self.show_items(parent_items), None)]+menu.items
            self.render()
        self.items.append((label+"  ›", submenu, icon))
        menu.destroy()

    def show_items(self, items):
        self.items = items
        self.render()

    def render(self):
        for child in self.content.winfo_children():
            child.destroy()
        self.buttons = []
        for item in self.items:
            if item is None:
                ttk.Frame(self.content, style="Card.TFrame", height=8).pack(fill="x")
                continue
            label, command, icon = item
            def invoke(command=command, label=label):
                if label.endswith("  ›") or label == self.app.locale.text("Quay lại"):
                    command()
                else:
                    self.destroy()
                    command()
            button = RoundedButton(self.content, text=label, command=invoke, width=280, height=36,
                                   image=self.app.icons.get(icon) if icon else None)
            button.set_presentation(self.app.theme)
            button.pack(fill="x", pady=1)
            self.buttons.append(button)
        self.update_idletasks()
        self.popup_height = self.content.winfo_reqheight()+20
        self.geometry(f"300x{self.popup_height}")
        self.draw()

    def draw(self):
        background, panel, *_ = PALETTES[self.app.theme]
        import sys
        # Use one canvas outline instead of clipping its curve with a second native region.
        if sys.platform == "win32":
            background = "#010203"
            self.wm_attributes("-transparentcolor", background)
        self.surface.configure(background=background)
        self.surface.delete("outline")
        rounded_rectangle(self.surface, 4, 4, self.winfo_width()-4, self.winfo_height()-4, 20,
                          fill=panel, outline="#999999" if self.app.theme == "light" else "#5a5a5a", tags="outline")
        self.surface.tag_lower("outline")

    def popup(self, anchor=None, x=None, y=None):
        self.anchor = anchor
        self.render()
        if anchor is not None:
            x = anchor.winfo_rootx()+anchor.winfo_width()-300
            y = anchor.winfo_rooty()+anchor.winfo_height()+6
        x = max(0, min(x, self.winfo_screenwidth()-300))
        y = max(0, min(y, self.winfo_screenheight()-self.popup_height-40))
        self.geometry(f"+{int(x)}+{int(y)}")
        self.deiconify()
        self.lift()
        self.focus_force()
        self.outside_binding = self.app.root.bind("<ButtonPress-1>", self.outside_click, add="+")

    def outside_click(self, event):
        if self.anchor is not None and event.widget == self.anchor:
            return
        if not (self.winfo_rootx() <= event.x_root < self.winfo_rootx()+self.winfo_width()
                and self.winfo_rooty() <= event.y_root < self.winfo_rooty()+self.winfo_height()):
            self.destroy()

    def schedule_focus_check(self, _event):
        if self.focus_timer:
            self.after_cancel(self.focus_timer)
        self.focus_timer = self.after_idle(self.check_focus)

    def check_focus(self):
        self.focus_timer = None
        if self.winfo_exists():
            focus = self.focus_get()
            if focus is None or focus.winfo_toplevel() != self:
                self.destroy()

    def destroy(self):
        if self.hover_timer:
            self.after_cancel(self.hover_timer)
            self.hover_timer = None
        if self.focus_timer:
            self.after_cancel(self.focus_timer)
            self.focus_timer = None
        if self.outside_binding:
            self.app.root.unbind("<ButtonPress-1>", self.outside_binding)
            self.outside_binding = None
        super().destroy()

    def track_hover(self, anchor):
        if self.hover_timer:
            self.after_cancel(self.hover_timer)
        def check():
            self.hover_timer = None
            x, y = self.winfo_pointerxy()
            def inside(widget, margin=0):
                return (widget.winfo_rootx()-margin <= x <= widget.winfo_rootx()+widget.winfo_width()+margin
                        and widget.winfo_rooty()-margin <= y <= widget.winfo_rooty()+widget.winfo_height()+margin)
            if not inside(anchor, 6) and not inside(self, 6):
                self.destroy()
                return
            self.hover_timer = self.after(100, check)
        self.hover_timer = self.after(180, check)

    def move(self, step):
        if self.buttons:
            index = self.buttons.index(self.focus_get()) if self.focus_get() in self.buttons else (-1 if step > 0 else 0)
            self.buttons[(index+step) % len(self.buttons)].focus_set()
        return "break"
