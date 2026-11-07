"""Draw preferences as one vector scene, retaining Tk layout and native text editing."""

import tkinter as tk
from tkinter import ttk

from .rounded import ChoiceRow, RoundedButton, RoundedField, rounded_rectangle
from .ui_preferences import PALETTES


class PreferencesSurface(tk.Canvas):
    """One visible background for text, artwork, choices and checkboxes.

    The existing widget tree supplies layout, commands and accessibility state.
    Its individual HWND surfaces remain behind this scene and never supply pixels
    to it. Only editable fields have native windows on the visible surface.
    """

    tkraise = tk.Misc.tkraise

    def __init__(self, app, page):
        super().__init__(app.shell, background=PALETTES[app.theme][0],
                         highlightthickness=0, borderwidth=0, takefocus=True)
        self.app, self.page = app, page
        self.items_by_widget, self.editors, self.editor_windows = {}, {}, {}
        self.regions, self.focused = [], None
        self.timer = None
        self.action_timer, self.pending_action = None, None
        self.presented = None
        self.frame_images = ()
        self.traces = {}
        self.geometry_bindings = {}
        self._hdm_shared_surface = True
        app.root._hdm_preferences_surface = self
        self._hdm_presentation = (app.theme, app.locale.language)
        self.bind("<Button-1>", self.click)
        self.bind("<Motion>", self.motion)
        self.bind("<Return>", self.activate)
        self.bind("<space>", self.activate)
        self.bind("<Tab>", lambda event: self.move_focus(1))
        self.bind("<Shift-Tab>", lambda event: self.move_focus(-1))
        self.bind("<Configure>", self.schedule)
        self.bind("<Destroy>", self.cleanup, add="+")
        self.configure_binding = app.shell.bind("<Configure>", self.schedule, add="+")
        self.show()

    def cleanup(self, event):
        if event.widget != self:
            return
        if self.timer:
            self.after_cancel(self.timer)
            self.timer = None
        if self.action_timer:
            self.after_cancel(self.action_timer)
            self.action_timer = None
        self.app.shell.unbind("<Configure>", self.configure_binding)
        for variable, callback in self.traces.items():
            self.tk.call("trace", "remove", "variable", variable, "write", callback)
            self.deletecommand(callback)
        self.traces.clear()
        for widget, bindings in self.geometry_bindings.items():
            if widget.winfo_exists():
                for sequence, callback in bindings:
                    tk.Misc.unbind(widget, sequence, callback)
        self.geometry_bindings.clear()
        self.frame_images = ()
        if getattr(self.app.root, "_hdm_preferences_surface", None) is self:
            del self.app.root._hdm_preferences_surface

    def show(self):
        self.place(x=0, y=0, relwidth=1, relheight=1)
        self.tkraise()
        self.schedule()

    def hide(self):
        self.place_forget()

    def schedule(self, _event=None):
        if not self.timer and not getattr(self.app, "_closing", False):
            self.timer = self.after_idle(self.settle)

    def settle(self):
        # Choice widths and fonts can change during localization. Let geometry
        # and Configure callbacks finish before reading their final positions.
        self.timer = self.after_idle(self.render)

    def refresh_language(self):
        self.schedule()

    def watch(self, variable):
        variable = str(variable)
        if variable and variable not in self.traces:
            callback = self.register(lambda *_: self.schedule())
            self.tk.call("trace", "add", "variable", variable, "write", callback)
            self.traces[variable] = callback

    def watch_geometry(self, widget):
        if widget not in self.geometry_bindings:
            self.geometry_bindings[widget] = [(sequence, tk.Misc.bind(widget, sequence, self.schedule, add="+"))
                for sequence in ("<Configure>", "<Map>", "<Unmap>")]

    def text(self, widget):
        variable = str(widget.cget("textvariable"))
        return str(widget.getvar(variable)) if variable else str(widget.cget("text"))

    def bounds(self, widget):
        x = widget.winfo_rootx()-self.winfo_rootx()
        y = widget.winfo_rooty()-self.winfo_rooty()
        return x, y, widget.winfo_width(), widget.winfo_height()

    def label(self, widget, x, y, width, height):
        style = ttk.Style(self)
        name = widget.cget("style") or "TLabel"
        font = widget.cget("font") or style.lookup(name, "font")
        color = widget.cget("foreground") or style.lookup(name, "foreground")
        image = widget.cget("image")
        if image:
            image = image[0] if isinstance(image, tuple) else image
            self.create_image(x+width/2, y+height/2, image=image, tags="frame")
        else:
            self.create_text(x, y+height/2, text=self.text(widget), anchor="w", fill=color,
                             font=font, tags="frame")
        if str(widget.cget("cursor")) == "hand2":
            self.regions.append((widget, (x, y, width, height), lambda: widget.event_generate("<Button-1>")))

    def checkbox(self, widget, x, y, width, height):
        self.watch(widget.cget("variable"))
        background, _panel, text, muted, accent = PALETTES[self.app.theme]
        disabled = "disabled" in widget.state()
        selected = "selected" in widget.state()
        top = y+(height-20)/2
        rounded_rectangle(self, x+1, top, x+20, top+19, 5,
                          fill=accent if selected else background,
                          outline=accent if selected else muted, tags="frame")
        if selected:
            self.create_line(x+5, top+10, x+9, top+14, x+16, top+6, width=2,
                             fill="white" if self.app.theme == "light" else "#10252f", tags="frame")
        font = ttk.Style(self).lookup(widget.cget("style") or "TCheckbutton", "font")
        self.create_text(x+26, y+height/2, text=self.text(widget), anchor="w",
                         font=font, fill=muted if disabled else text, tags="frame")
        if not disabled:
            self.regions.append((widget, (x, y, width, height), widget.invoke))

    def vector_items(self, widget, x, y):
        for item in widget.find_all():
            kind = widget.type(item)
            if kind == "window":
                continue
            options = {name: values[-1] for name, values in widget.itemconfigure(item).items()}
            options["tags"] = "frame"
            # Flat artwork and text need no painted rectangle behind them.
            if kind == "polygon" and str(options.get("fill")) == str(self.cget("background")) \
                    and str(options.get("outline")) == str(self.cget("background")):
                continue
            points = [value+(x if index % 2 == 0 else y)
                      for index, value in enumerate(widget.coords(item))]
            self._create(kind, points, options)

    def editor(self, widget, x, y, width, height):
        if widget not in self.editors:
            field = ttk.Entry(self, textvariable=widget.cget("textvariable"),
                              style=widget.cget("style"), font=widget.cget("font"))
            field._hdm_presentation = (self.app.theme, self.app.locale.language)
            for sequence in ("<Return>", "<FocusOut>"):
                field.bind(sequence, lambda event, source=widget, sequence=sequence:
                           source.event_generate(sequence))
            field.bind("<FocusIn>", lambda _event: setattr(self, "focused", None))
            for sequence, direction in (("<Tab>", 1), ("<Shift-Tab>", -1)):
                field.bind(sequence, lambda _event, direction=direction, field=field:
                           self.move_focus(direction, field))
            self.editors[widget] = field
            self.editor_windows[widget] = self.create_window(x, y, anchor="nw", window=field)
        field = self.editors[widget]
        field.configure(state=widget.cget("state"))
        self.coords(self.editor_windows[widget], x, y)
        self.itemconfigure(self.editor_windows[widget], width=width, height=height, state="normal")

    def render(self):
        self.timer = None
        if getattr(self.app.root, "_hdm_paint_depth", 0):
            # Native mapping completes when the outer presentation transaction
            # releases painting. A timer, unlike another idle, runs after that.
            self.timer = self.after(0, self.render)
            return
        if not self.app.page_stack or self.app.page_stack[-1] is not self.page:
            self.hide()
            return
        if not self.winfo_ismapped():
            return
        images = (self.app.header_logo, *self.app.icons.values(), *self.app.browser_icons.values())
        background = PALETTES[self.app.theme][0]
        self.configure(background=background)
        # No update()/update_idletasks() here: Tk publishes this complete vector
        # frame from its backing pixmap after all items have been replaced.
        self.delete("frame")
        self.items_by_widget, self.regions = {}, []

        def visit(widget):
            self.watch_geometry(widget)
            if widget == self or not widget.winfo_ismapped():
                return
            x, y, width, height = self.bounds(widget)
            before = set(self.find_all())
            if isinstance(widget, ttk.Label):
                self.label(widget, x, y, width, height)
            elif isinstance(widget, ttk.Checkbutton):
                self.checkbox(widget, x, y, width, height)
            elif isinstance(widget, (RoundedButton, RoundedField)):
                self.vector_items(widget, x, y)
                if isinstance(widget, RoundedButton) and str(widget.cget("state")) != "disabled":
                    self.regions.append((widget, (x, y, width, height), widget.invoke))
            elif isinstance(widget, ttk.Entry):
                self.editor(widget, x, y, width, height)
            elif isinstance(widget, ChoiceRow):
                self.watch(widget.variable)
            items = tuple(item for item in self.find_all() if item not in before)
            if items:
                self.items_by_widget[widget] = items
            for child in widget.winfo_children():
                visit(child)

        visit(self.app.header)
        visit(self.page)
        for source, item in self.editor_windows.items():
            if source.winfo_ismapped():
                self.tag_raise(item)
            else:
                self.itemconfigure(item, state="hidden")
        self.presented = (self.app.theme, self.app.locale.language)
        # Canvas items retain Tk image names, not Python PhotoImage objects.
        # Keep the old artwork alive until the entire new scene replaces it.
        self.frame_images = images
        self.draw_focus()
        self.tkraise()

    def hit(self, x, y):
        return next((region for region in reversed(self.regions)
                     if region[1][0] <= x < region[1][0]+region[1][2]
                     and region[1][1] <= y < region[1][1]+region[1][3]), None)

    def click(self, event):
        modal = getattr(self.app, "modal_card", None)
        if modal and modal.winfo_exists():
            modal.dismiss()
            return "break"
        region = self.hit(event.x, event.y)
        if region:
            self.focus_set()
            self.focused = region[0]
            if isinstance(region[0].master, ChoiceRow):
                if self.pending_action is None:
                    self.pending_action = {}
                # Appearance, language and proxy choices are independent. Only
                # superseded selections within the same choice row are dropped.
                self.pending_action[region[0].master] = region[2]
                if not self.action_timer:
                    self.action_timer = self.after_idle(self.commit_action)
            else:
                self.run_action(region[2])
        return "break"

    def commit_action(self):
        self.action_timer = None
        actions, self.pending_action = self.pending_action, None
        for action in (actions or {}).values():
            self.run_action(action)

    def run_action(self, action):
        if self.winfo_exists() and self.winfo_ismapped():
            action()
            if self.winfo_exists():
                self.schedule()

    def motion(self, event):
        self.configure(cursor="hand2" if self.hit(event.x, event.y) else "arrow")

    def activate(self, _event=None):
        region = next((region for region in self.regions if region[0] == self.focused), None)
        if region:
            self.run_action(region[2])
        return "break"

    def move_focus(self, direction, current=None):
        widgets = [region[0] for region in self.regions]+[
            field for source, field in self.editors.items() if source.winfo_ismapped()]
        current = current or self.focused
        if widgets:
            index = widgets.index(current) if current in widgets else (-1 if direction > 0 else 0)
            self.focused = widgets[(index+direction) % len(widgets)]
            if self.focused in self.editors.values():
                self.focused.focus_set()
            else:
                self.focus_set()
            self.draw_focus()
        return "break"

    def draw_focus(self):
        self.delete("focus")
        region = next((region for region in self.regions if region[0] == self.focused), None)
        if region and self.focus_get() == self:
            x, y, width, height = region[1]
            rounded_rectangle(self, x, y, x+width, y+height, 6, fill="",
                              outline=PALETTES[self.app.theme][3], dash=(2, 3), tags="focus")
