"""Optional Windows notification-area icon; UI work is routed through the app queue."""


class Tray:
    def __init__(self, app):
        import pystray
        from PIL import Image, ImageDraw
        self.app = app
        image = Image.new("RGB", (64, 64), "#101827")
        draw = ImageDraw.Draw(image)
        draw.rectangle((26, 9, 38, 37), fill="#459fff")
        draw.polygon(((13, 30), (51, 30), (32, 49)), fill="#459fff")
        draw.rectangle((13, 52, 51, 57), fill="#e6edf8")
        self.icon = pystray.Icon("HDM", image, "hngoos-download-manager (HDM)", menu=pystray.Menu(
            pystray.MenuItem("Mở HDM", self.show, default=True),
            pystray.MenuItem("Thoát", self.exit)))
        self.icon.run_detached()

    def show(self, *_args):
        self.app.events.put(lambda: (self.app.root.deiconify(), self.app.root.lift()))

    def hide(self):
        self.app.root.withdraw()

    def exit(self, *_args):
        self.app.events.put(self.app.close)

    def close(self):
        self.icon.stop()
