"""Keep Tcl font creation and deletion on the owning UI thread."""

from tkinter import Misc
from tkinter.font import Font


def owned_font(widget, **options):
    font = Font(widget, **options)

    def release(event):
        if event.widget is widget and font.delete_font:
            # A destroyed widget can remain in a Python callback cycle until a
            # worker triggers GC. Dispose its Tcl resource now, on the UI thread.
            font.delete_font = False
            widget.tk.call("font", "delete", font.name)

    # Use Misc.bind: entry wrappers intentionally forward their public bind API.
    Misc.bind(widget, "<Destroy>", release, add="+")
    return font


def metrics_font(widget, specification):
    root = widget._root()
    key = tuple(root.tk.splitlist(root.tk.call("font", "actual", specification)))
    if not hasattr(root, "_hdm_metric_fonts"):
        root._hdm_metric_fonts = {}
    if key not in root._hdm_metric_fonts:
        root._hdm_metric_fonts[key] = owned_font(root, font=specification)
    return root._hdm_metric_fonts[key]
