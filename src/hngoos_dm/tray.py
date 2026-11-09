"""Optional Windows notification-area icon; UI work is routed through the app queue."""


class Tray:
    def __init__(self, app):
        import sys
        from importlib.resources import files

        import pystray
        from PIL import Image
        self.app = app
        with (files("hngoos_dm") / "assets/branding/hdm.png").open("rb") as source, Image.open(source) as image:
            image = image.convert("RGBA")
        icon_class = pystray.Icon
        if sys.platform == "win32":
            from .windows_tray import WindowsIcon
            icon_class = WindowsIcon
        self.icon = icon_class("HDM", image, "Hngoos Download Manager (HDM)", menu=pystray.Menu(
            pystray.MenuItem(app.locale.text("Mở HDM"), self.show, default=True),
            pystray.MenuItem(app.locale.text("Thoát"), self.exit)))
        self.icon.run_detached()

    def show(self, *_args):
        self.app.events.put(lambda: (self.app.root.deiconify(), self.app.root.lift()))

    def hide(self):
        self.app.root.withdraw()

    def exit(self, *_args):
        self.app.events.put(self.app.close)

    def close(self):
        self.icon.stop()
