"""Draw the desktop interface on one scene, retaining Tk layout and text editing."""

import tkinter as tk
from tkinter import ttk

from .rounded import ChoiceRow, RoundedButton, RoundedField, RoundedPanel, RoundedScrollbar
from .ui_preferences import PALETTES


def fit_text(font, text, width, suffix=""):
    """Clip long URLs and names without wrapping or quadratic font measurements."""
    if font.measure(text) <= width:
        return text
    low, high = 0, len(text)
    while low < high:
        middle = (low+high+1)//2
        if font.measure(text[:middle]+suffix) <= width:
            low = middle
        else:
            high = middle-1
    return text[:low]+suffix


class PreferencesSurface(tk.Canvas):
    """One visible background for text, artwork, choices and checkboxes.

    The existing widget tree supplies layout, commands and keyboard state.
    Its individual HWND surfaces remain behind this scene and never supply pixels
    to it. A native editor is visible only while the user is editing its text.
    """

    tkraise = tk.Misc.tkraise

    def _create(self, itemType, args, kw):
        item = super()._create(itemType, args, kw)
        items = getattr(self, "_widget_frame_items", None)
        if items is not None:
            items.append(item)
        return item

    def __init__(self, app):
        super().__init__(app.root, background=PALETTES[app.theme][0],
                         highlightthickness=0, borderwidth=0, takefocus=True)
        self.app = app
        self.items_by_widget, self.editors, self.editor_windows = {}, {}, {}
        self.regions, self.focused = [], None
        self.pending_editor = None
        self.timer = None
        self.action_timer, self.pending_action = None, None
        self.presented = None
        self.frame_images = ()
        self.traces = {}
        self.geometry_bindings = {}
        self.drag_scrollbar = None
        self._hdm_shared_surface = True
        app.root._hdm_preferences_surface = self
        app.root._hdm_paint_depth = 0
        self._hdm_presentation = (app.theme, app.locale.language)
        self.bind("<Button-1>", self.click)
        self.bind("<Motion>", self.motion)
        self.bind("<B1-Motion>", self.drag)
        self.bind("<ButtonRelease-1>", self.release)
        for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.bind(sequence, self.wheel)
        self.bind("<Return>", self.activate)
        self.bind("<space>", self.activate)
        self.bind("<Tab>", lambda event: self.move_focus(1))
        self.bind("<Shift-Tab>", lambda event: self.move_focus(-1))
        self.bind("<Configure>", self.schedule)
        self.bind("<Destroy>", self.cleanup, add="+")
        self.configure_binding = app.root.bind("<Configure>", self.schedule, add="+")
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
        self.app.root.unbind("<Configure>", self.configure_binding)
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
        modal = getattr(self.app, "modal_card", None)
        if modal and modal.winfo_exists():
            modal.lift()
        else:
            self.tkraise()
        self.schedule()

    def hide(self):
        # Navigation changes the source tree, never the visible backing surface.
        self.schedule()

    def schedule(self, _event=None):
        if not self.timer and not getattr(self.app, "_closing", False):
            self.timer = self.after(16, self.settle)

    def settle(self):
        # Choice widths and fonts can change during localization. Let geometry
        # and Configure callbacks finish before reading their final positions.
        self.timer = self.after_idle(self.render)

    def refresh_language(self):
        self.schedule()

    def watch(self, variable):
        variable = str(variable)
        self.active_variables.add(variable)
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
        parent = widget.master
        if widget.winfo_manager() == "canvas" and isinstance(parent, tk.Canvas):
            # Tk unmaps embedded source windows when another surface covers
            # them. Their Canvas geometry remains the authoritative layout.
            for item in parent.find_all():
                if parent.type(item) == "window" and str(parent.itemcget(item, "window")) == str(widget):
                    box = parent.bbox(item)
                    if box:
                        px, py, *_ = self.bounds(parent)
                        left, top, right, bottom = box
                        return px+left, py+top, right-left, bottom-top
        x = widget.winfo_rootx()-self.winfo_rootx()
        y = widget.winfo_rooty()-self.winfo_rooty()
        return x, y, widget.winfo_width(), widget.winfo_height()

    def label(self, widget, x, y, width, height):
        variable = widget.cget("textvariable")
        if variable:
            self.watch(variable)
        style = ttk.Style(self)
        name = widget.cget("style") or "TLabel"
        font = widget.cget("font") or style.lookup(name, "font")
        color = widget.cget("foreground") or style.lookup(name, "foreground")
        image = widget.cget("image")
        if image:
            image = image[0] if isinstance(image, tuple) else image
            self.create_image(x+width/2, y+height/2, image=image, tags="frame")
        else:
            anchor = str(widget.cget("anchor"))
            centered = anchor in {"center", "n", "s"}
            self.create_text(x+width/2 if centered else x, y+height/2, text=self.text(widget),
                             anchor="center" if centered else "w", fill=color, font=font,
                             width=width, tags="frame")
        if str(widget.cget("cursor")) == "hand2":
            action = getattr(widget, "surface_command", None) or (lambda: widget.event_generate("<Button-1>"))
            self.regions.append((widget, (x, y, width, height), action))

    def checkbox(self, widget, x, y, width, height):
        self.watch(widget.cget("variable"))
        _background, _panel, text, muted, _accent = PALETTES[self.app.theme]
        disabled = "disabled" in widget.state()
        selected = "selected" in widget.state()
        state = ("on" if selected else "off")+("-disabled" if disabled else "")
        image = self.app.root._hdm_checkbox_images[self.app.theme, state]
        from .ui_scale import WindowScale
        size = WindowScale(self.app.root).size(27, 18)
        if size != image.width():
            try:
                from PIL import Image, ImageTk
            except ImportError:
                pass  # Minimal source installs retain the original transparent artwork.
            else:
                from importlib.resources import files
                cache = getattr(self.app.root, "_hdm_scaled_checkbox_images", {})
                key = self.app.theme, state, size
                if key not in cache:
                    path = files("hngoos_dm")/"assets/icons"/f"checkbox-{self.app.theme}-{state}.png"
                    with Image.open(path) as source:
                        cache[key] = ImageTk.PhotoImage(source.resize((size, round(size*22/27)),
                                                                     Image.Resampling.LANCZOS), master=self.app.root)
                    self.app.root._hdm_scaled_checkbox_images = cache
                image = cache[key]
        # Use the same transparent, antialiased artwork as native checkboxes.
        # Canvas polygon/line rendering does not antialias diagonal ticks.
        self.create_image(x, y+height/2, image=image, anchor="w", tags="frame")
        font = ttk.Style(self).lookup(widget.cget("style") or "TCheckbutton", "font")
        inset = image.width()-1
        self.create_text(x+inset, y+height/2, text=self.text(widget), anchor="w",
                         font=font, fill=muted if disabled else text,
                         width=max(1, widget.master.winfo_width()-widget.winfo_x()-inset-4), tags="frame")
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
        self.watch(widget.cget("textvariable"))
        if widget not in self.editors:
            field = ttk.Entry(self, textvariable=widget.cget("textvariable"),
                              style=widget.cget("style"), font=widget.cget("font"))
            field._hdm_presentation = (self.app.theme, self.app.locale.language)
            # Dispatch actual editor events through the source widget's bindings.
            # Synthetic key events sent to an obscured source Entry are dropped
            # by Tk. A binding tag preserves Return, paste and save callbacks.
            field.bindtags((str(field), str(widget), *field.bindtags()[1:]))
            field.bind("<FocusOut>", lambda _event: self.schedule())
            field.bind("<FocusIn>", lambda _event, source=widget: self.editor_focused(source))
            field.bind("<Map>", lambda _event, source=widget, field=field:
                       field.focus_set() if self.pending_editor is source else None)
            for sequence, direction in (("<Tab>", 1), ("<Shift-Tab>", -1)):
                field.bind(sequence, lambda _event, direction=direction, field=field:
                           self.move_focus(direction, field))
            self.editors[widget] = field
            self.editor_windows[widget] = self.create_window(x, y, anchor="nw", window=field)
        field = self.editors[widget]
        field.configure(state=widget.cget("state"), font=widget.cget("font"))
        self.coords(self.editor_windows[widget], x, y)
        editing = self.pending_editor is widget or self.focus_get() is field
        self.itemconfigure(self.editor_windows[widget], width=width, height=height,
                           state="normal" if editing else "hidden")
        if not editing:
            from .ui_fonts import metrics_font
            font = metrics_font(self, widget.cget("font"))
            placeholder = getattr(widget, "placeholder", "") if not widget.get() else ""
            text = fit_text(font, self.app.locale.text(placeholder) if placeholder else widget.get(), width)
            color = PALETTES[self.app.theme][3 if placeholder or str(widget.cget("state")) == "disabled" else 2]
            self.create_text(x, y+height/2, text=text, anchor="w", fill=color, font=font, tags="frame")
        if str(widget.cget("state")) != "disabled":
            self.regions.append((widget, (x, y, width, height), lambda: self.start_edit(widget)))

    def start_edit(self, source):
        # Mapping and native focus are asynchronous on Aqua. Retain the window
        # across intervening frames until FocusIn acknowledges the request.
        self.pending_editor = source
        self.itemconfigure(self.editor_windows[source], state="normal")
        self.tag_raise(self.editor_windows[source])
        self.editors[source].focus_set()

    def editor_focused(self, source):
        if self.pending_editor is source:
            self.pending_editor = None
        self.schedule()

    def render(self):
        self.timer = None
        if getattr(self.app.root, "_hdm_paint_depth", 0):
            # Native mapping completes when the outer presentation transaction
            # releases painting. A timer, unlike another idle, runs after that.
            self.timer = self.after(0, self.render)
            return
        if not self.winfo_ismapped():
            return
        images = (self.app.header_logo, *self.app.icons.values(),
                  *getattr(self.app, "browser_icons", {}).values())
        background = PALETTES[self.app.theme][0]
        self.configure(background=background)
        # No update()/update_idletasks() here: Tk publishes this complete vector
        # frame from its backing pixmap after all items have been replaced.
        self.delete("frame")
        self.items_by_widget, self.regions = {}, []
        visited = set()
        self.active_variables = set()

        def visit(widget):
            self.watch_geometry(widget)
            embedded = widget.winfo_manager() == "canvas" and widget.master in visited
            if widget == self or not (widget.winfo_ismapped() or embedded):
                return
            visited.add(widget)
            x, y, width, height = self.bounds(widget)
            self._widget_frame_items = []
            if isinstance(widget, ttk.Label):
                self.label(widget, x, y, width, height)
            elif isinstance(widget, ttk.Checkbutton):
                self.checkbox(widget, x, y, width, height)
            elif isinstance(widget, (RoundedButton, RoundedField, RoundedPanel, RoundedScrollbar)):
                self.vector_items(widget, x, y)
                if isinstance(widget, RoundedButton) and str(widget.cget("state")) != "disabled":
                    self.regions.append((widget, (x, y, width, height), widget.invoke))
                elif isinstance(widget, RoundedScrollbar):
                    self.regions.append((widget, (x, y, width, height), None))
            elif isinstance(widget, ttk.Entry):
                self.editor(widget, x, y, width, height)
            elif getattr(widget, "_hdm_surface_canvas", False):
                self.vector_items(widget, x, y)
            elif isinstance(widget, ttk.Treeview):
                self.journal(widget, x, y)
            elif isinstance(widget, tk.Frame) and height == 1:
                self.create_line(x, y, x+width, y, fill=widget.cget("background"), tags="frame")
            elif isinstance(widget, ChoiceRow):
                self.watch(widget.variable)
            items = tuple(self._widget_frame_items)
            self._widget_frame_items = None
            if items:
                self.items_by_widget[widget] = items
            for child in widget.winfo_children():
                visit(child)

        visit(self.app.header)
        visit(self.app.page_stack[-1] if self.app.page_stack else self.app.view_host)
        self.active_editors = set(self.editors) & visited
        if self.pending_editor not in self.active_editors:
            self.pending_editor = None
        for source in list(self.editors):
            if not source.winfo_exists():
                self.editors.pop(source).destroy()
                self.delete(self.editor_windows.pop(source))
        for source, item in self.editor_windows.items():
            if source in self.active_editors:
                self.tag_raise(item)
            else:
                self.itemconfigure(item, state="hidden")
        for variable in set(self.traces)-self.active_variables:
            callback = self.traces.pop(variable)
            self.tk.call("trace", "remove", "variable", variable, "write", callback)
            self.deletecommand(callback)
        for widget in list(self.geometry_bindings):
            if not widget.winfo_exists():
                del self.geometry_bindings[widget]
        self.presented = (self.app.theme, self.app.locale.language)
        # Canvas items retain Tk image names, not Python PhotoImage objects.
        # Keep the old artwork alive until the entire new scene replaces it.
        self.frame_images = images
        self.draw_focus()
        self.tkraise()
        modal = getattr(self.app, "modal_card", None)
        if modal and modal.winfo_exists():
            modal.lift()

    def journal(self, widget, x, y):
        """Draw visible rows; the native Treeview still owns layout and scrolling."""
        from .ui_fonts import metrics_font
        style = ttk.Style(self)
        font = metrics_font(self, style.lookup("Treeview", "font"))
        color = PALETTES[self.app.theme][2]
        if not widget.get_children():
            heading_height = font.metrics("linespace")+16
            self.create_text(x+widget.winfo_width()/2, y+(widget.winfo_height()+heading_height)/2,
                             text=self.app.locale.text("Danh sách trống"), fill=PALETTES[self.app.theme][3],
                             font=font, tags="frame")
        # Status, speed, check and actions are existing semantic cell overlays.
        # File names are the only text supplied directly by the native table.
        for row in widget.get_children():
            box = widget.bbox(row, "name")
            if not box:
                continue
            left, top, width, height = box
            text = fit_text(font, str(widget.set(row, "name")), max(0, width-12), "…")
            self.create_text(x+left+6, y+top+height/2, text=text, anchor="w", fill=color,
                             font=font, tags="frame")
            def open_folder(left=left, top=top, height=height):
                widget.event_generate("<Button-1>", x=left+8, y=top+height//2)
            self.regions.append((widget, (x+left, y+top, min(width, font.measure(text)+10), height), open_folder))

    def wheel(self, event):
        panel = self.app.queue_panel
        x, y, width, height = self.bounds(panel)
        if not self.app.page_stack and x <= event.x < x+width and y <= event.y < y+height:
            step = (-1 if getattr(event, "num", None) == 4 else 1) if not event.delta else -int(event.delta/120)
            self.app.table.yview_scroll(step, "units")
            self.app.update_safety_buttons()
            self.schedule()
        return "break"

    def drag(self, event):
        if self.drag_scrollbar:
            from types import SimpleNamespace
            scrollbar = self.drag_scrollbar
            scrollbar.motion(SimpleNamespace(y=event.y-self.bounds(scrollbar)[1]))
            self.app.update_safety_buttons()
            self.schedule()
        return "break"

    def release(self, _event):
        if self.drag_scrollbar:
            self.drag_scrollbar.drag = None
            self.drag_scrollbar = None
        return "break"

    def hit(self, x, y):
        return next((region for region in reversed(self.regions)
                     if region[1][0] <= x < region[1][0]+region[1][2]
                     and region[1][1] <= y < region[1][1]+region[1][3]), None)

    def click(self, event):
        self.pending_editor = None
        modal = getattr(self.app, "modal_card", None)
        if modal and modal.winfo_exists():
            modal.dismiss()
            return "break"
        region = self.hit(event.x, event.y)
        if region:
            if isinstance(region[0], RoundedScrollbar):
                from types import SimpleNamespace
                self.drag_scrollbar = region[0]
                region[0].press(SimpleNamespace(y=event.y-region[1][1]))
                self.schedule()
                return "break"
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
        for row, action in (actions or {}).items():
            if row.winfo_exists():
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
        if region and region[2] is not None:
            self.run_action(region[2])
        return "break"

    def move_focus(self, direction, current=None):
        widgets = [region[0] for region in self.regions
                   if region[2] is not None and not isinstance(region[0], ttk.Entry)]+[
            field for source, field in self.editors.items()
            if source in self.active_editors and str(source.cget("state")) != "disabled"]
        current = current or self.focused
        if widgets:
            index = widgets.index(current) if current in widgets else (-1 if direction > 0 else 0)
            self.focused = widgets[(index+direction) % len(widgets)]
            if self.focused in self.editors.values():
                source = next(source for source, field in self.editors.items() if field is self.focused)
                self.start_edit(source)
            else:
                self.pending_editor = None
                self.focus_set()
            self.draw_focus()
        return "break"

    def draw_focus(self):
        # Keep keyboard focus and activation without painting a click outline.
        self.delete("focus")
