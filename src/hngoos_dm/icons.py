"""Morphicons/Lucide assets rendered ahead of time; Tk needs no JavaScript runtime."""
import sys
from importlib.resources import files
from tkinter import PhotoImage, ttk


def load_brand_icons(master):
    """Set the default icon for this window and its dialogs; retain Tk images."""
    folder = files("hngoos_dm") / "assets" / "branding"
    source = PhotoImage(master=master, file=str(folder / "hdm.png"))
    icons = tuple(source.subsample(factor) for factor in (4, 8, 16, 32, 6))
    master.iconphoto(True, *icons)
    if sys.platform == "win32":
        master.iconbitmap(str(folder / "hdm.ico"))
        master.iconbitmap(default=str(folder / "hdm.ico"))
        master.after_idle(lambda: set_windows_icon(master, folder / "hdm.ico"))
    return icons


def load_header_logo(master, width, height, theme="dark"):
    """Fit the approved strokes, with transparent tiles and a themed foreground.

    Header assets use the original artwork's luminance multiplied by its alpha
    as a mask. This preserves the handwritten H and square outlines exactly.
    The filled app/window icon remains a separate asset.
    """
    path = files("hngoos_dm") / "assets" / "branding" / f"header-{theme}.png"
    try:
        from PIL import Image, ImageTk
        with Image.open(path) as source:
            artwork = source.convert("RGBA")
            artwork.thumbnail((width, height), Image.Resampling.LANCZOS)
            from .ui_preferences import PALETTES
            foreground = Image.new("RGBA", artwork.size, PALETTES[theme][2])
            foreground.putalpha(artwork.getchannel("A"))
            return ImageTk.PhotoImage(foreground, master=master)
    except ImportError:
        import math
        source = PhotoImage(master=master, file=str(path))
        factor = max(1, math.ceil(max(source.width()/width, source.height()/height)))
        return source.subsample(factor)


def set_windows_icon(master, path):
    """Tk's default icon alone does not replace an existing Windows wrapper icon."""
    import ctypes
    from ctypes import wintypes
    user = ctypes.windll.user32
    user.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
    user.GetAncestor.restype = wintypes.HWND
    user.LoadImageW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT,
                               ctypes.c_int, ctypes.c_int, wintypes.UINT]
    user.LoadImageW.restype = wintypes.HANDLE
    user.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user.SendMessageW.restype = wintypes.LPARAM
    user.DestroyIcon.argtypes = [wintypes.HANDLE]
    hwnd = user.GetAncestor(master.winfo_id(), 2)
    previous = getattr(master, "_hdm_icon_handles", [])
    handles = []
    for which, size in ((0, 16), (1, 32)):
        handle = user.LoadImageW(None, str(path), 1, size, size, 0x10)
        if handle:
            user.SendMessageW(hwnd, 0x80, which, handle)
            handles.append(handle)
    master._hdm_icon_handles = handles
    for handle in previous:
        user.DestroyIcon(handle)
    if not getattr(master, "_hdm_icon_cleanup", False):
        def release(event):
            if event.widget == master:
                for handle in getattr(master, "_hdm_icon_handles", []):
                    user.DestroyIcon(handle)
        master.bind("<Destroy>", release, add="+")
        master._hdm_icon_cleanup = True


def load_image(master, path, light=False, size=None):
    if light or size:
        try:
            from PIL import Image, ImageTk
            with Image.open(path) as source:
                image = source.convert("RGBA")
                if light:
                    image = Image.new("RGBA", source.size, "#555555")
                    image.putalpha(source.convert("RGBA").getchannel("A"))
                if size:
                    image = image.resize((size, size), Image.Resampling.LANCZOS)
            return ImageTk.PhotoImage(image, master=master)
        except ImportError:
            pass
    return PhotoImage(master=master, file=str(path))


def load_icons(master, light=False, size=None):
    root = files("hngoos_dm")/"assets"/"icons"
    names = ("download", "play", "pause", "check", "shield", "settings", "folder", "list", "video",
             "file", "search", "plus", "globe", "info", "scissors", "close", "app", "music", "image", "archive",
             "arrow-down", "arrow-up", "activity", "sun", "moon", "more", "trash", "refresh", "transfer", "progress",
             "grid", "remove", "alert")
    return {name: load_image(master, root/(name+".png"), light, size) for name in names}


def load_browser_icons(master, size=None):
    """Browser trademarks keep their own colors, separate from themed UI icons."""
    root = files("hngoos_dm")/"assets"/"icons"
    return {(name, enabled): load_image(master,
                root/f"browser-{'opera' if name == 'opera-gx' else name}{'' if enabled else '-dim'}.png", size=size)
            for name in ("chrome", "edge", "brave", "coccoc", "opera", "opera-gx", "vivaldi") for enabled in (True, False)}


def load_contact_icons(master, size=None):
    root = files("hngoos_dm") / "assets" / "icons"
    return {label: load_image(master, root / f"contact-{label.lower()}.png", size=size)
            for label in ("Facebook", "Instagram", "Gmail", "GitHub")}


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
        self.timer = None
        button.bind("<Destroy>", lambda event: self.cancel() if event.widget == button else None, add="+")
        button.configure(image=self.frames[0], compound="left")

    def cancel(self):
        if self.timer is not None:
            self.button.after_cancel(self.timer)
            self.timer = None

    def set_theme(self, light):
        self.cancel()
        self.generation += 1
        root = files("hngoos_dm")/"assets"/"icons"
        self.frames = [load_image(self.button, root/f"play-pause-{i}.png", light) for i in range(13)]
        self.button.configure(image=self.frames[-1 if self.running else 0])

    def set_running(self, running):
        if running == self.running:
            return
        self.running = running
        self.cancel()
        self.generation += 1
        generation = self.generation
        indexes = list(range(13)) if running else list(range(12, -1, -1))
        from .widgets import motion_enabled
        if not motion_enabled():
            self.button.configure(image=self.frames[indexes[-1]])
            return
        def tick(frame=0):
            self.timer = None
            if generation != self.generation or not self.button.winfo_exists():
                return
            self.button.configure(image=self.frames[indexes[frame]])
            if frame < 12:
                self.timer = self.button.after(16, tick, frame+1)
        tick()
