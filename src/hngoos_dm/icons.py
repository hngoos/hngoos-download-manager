"""Morphicons/Lucide assets rendered ahead of time; Tk needs no JavaScript runtime."""
import sys
from importlib.resources import files
from tkinter import PhotoImage, ttk


def load_brand_icons(master):
    """Set the default icon for this window and its dialogs; retain Tk images."""
    folder = files("hngoos_dm") / "assets" / "branding"
    source = PhotoImage(master=master, file=str(folder / "hdm.png"))
    icons = tuple(source.subsample(factor) for factor in (4, 8, 16, 32))
    master.iconphoto(True, *icons)
    if sys.platform == "win32":
        master.iconbitmap(default=str(folder / "hdm.ico"))
    return icons


def load_icons(master):
    root = files("hngoos_dm")/"assets"/"icons"
    names = ("download", "play", "pause", "check", "shield", "settings", "folder", "list", "video",
             "file", "search", "plus", "globe", "info", "scissors", "close")
    return {name: PhotoImage(master=master, file=str(root/(name+".png"))) for name in names}


def decorate_buttons(parent, icons):
    groups = (("plus", ("Thêm",)), ("pause", ("Tạm dừng",)), ("play", ("Tiếp tục",)),
              ("folder", ("thư mục", "Mở thư mục")), ("shield", ("quét", "bảo vệ", "cách ly")),
              ("scissors", ("Cắt", "ghép", "nén")), ("list", ("danh sách", "lịch sử")),
              ("file", ("PDF",)), ("download", ("Tải", "tải", "cập nhật")))
    for widget in parent.winfo_children():
        if isinstance(widget, ttk.Button):
            label = str(widget.cget("text"))
            for name, words in groups:
                if any(word in label for word in words):
                    widget.configure(image=icons[name], compound="left")
                    break
        decorate_buttons(widget, icons)


class MorphPlayback:
    """Sampled Morphicons Play↔Pause transition, driven by Tk's own event loop."""
    def __init__(self, button):
        self.button = button
        root = files("hngoos_dm")/"assets"/"icons"
        self.frames = [PhotoImage(master=button, file=str(root/f"play-pause-{i}.png")) for i in range(13)]
        self.running = False
        self.generation = 0
        button.configure(image=self.frames[0], compound="left")

    def set_running(self, running):
        if running == self.running:
            return
        self.running = running
        self.generation += 1
        generation = self.generation
        indexes = list(range(13)) if running else list(range(12, -1, -1))
        from .widgets import motion_enabled
        if not motion_enabled():
            self.button.configure(image=self.frames[indexes[-1]])
            return
        def tick(frame=0):
            if generation != self.generation or not self.button.winfo_exists():
                return
            self.button.configure(image=self.frames[indexes[frame]])
            if frame < 12:
                self.button.after(16, tick, frame+1)
        tick()
