"""Run the native application with isolated data and live UI refresh (F5).

Usage: .venv/Scripts/pythonw.exe scripts/dev-native.py
The download manager survives UI refreshes; no browser or installer is used.
"""

import argparse
import importlib
import logging
import subprocess
import sys
import tempfile
import time
import tkinter as tk
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
UI_MODULES = ("ui_preferences", "rounded", "toolbar", "icons", "browser", "browser_preferences", "network", "preferences", "extension_package", "toolchain", "media", "download_ui", "information_ui",
              "safety_ui", "update_ui", "app")
LOG = logging.getLogger(__name__)


class NativeSession:
    def __init__(self, root, data_dir, watch=True):
        from hngoos_dm.app import App
        self.root = root
        self.app = App(root, data_dir)
        self.app.close_to_tray.set(False)
        self.title()
        self.last, self.pending = self.stamp(), None
        self.root.bind("<F5>", self.reload_ui)
        self.timer = root.after(700, self.watch) if watch else None
        root.bind("<Destroy>", self.cancel_watch, add="+")

    def title(self):
        self.root.title("Hngoos Download Manager")

    def stamp(self):
        paths = [BASE / f"src/hngoos_dm/{name}.py" for name in UI_MODULES]
        paths += sorted((BASE / "src/hngoos_dm/assets").rglob("*.png"))
        return tuple(path.stat().st_mtime_ns for path in paths)

    def cancel_watch(self, event):
        if event.widget == self.root and self.timer:
            self.root.after_cancel(self.timer)
            self.timer = None

    def reload_ui(self, _event=None):
        app, root = self.app, self.root
        if (BASE / "tools/native-live-hold").exists():
            return False
        if getattr(app, "source_busy", False) or getattr(app, "paste_timer", None):
            return False
        if getattr(app, "page_stack", []) or getattr(app, "modal_card", None):
            return False
        if any(isinstance(child, tk.Toplevel) for child in root.winfo_children()):
            return False
        snapshots = {}
        try:
            # Construct the new UI in an isolated process before removing this view.
            # Import/compile checks alone cannot catch failures inside _layout().
            checked = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--preflight"],
                                     check=False, capture_output=True, text=True, timeout=15,
                                     creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
            if checked.returncode:
                raise RuntimeError(checked.stderr[-6000:])
            for name in UI_MODULES:
                path = BASE / f"src/hngoos_dm/{name}.py"
                compile(path.read_text(encoding="utf-8"), str(path), "exec")
            editor = getattr(app, "download_editor", None)
            description = editor.description if editor and editor.winfo_exists() else None
            inputs = {key: getattr(editor, key).get() for key in (
                "filename", "format", "quality", "connections", "digest", "algorithm", "mirrors", "cookie",
                "format_id", "playlist", "subtitles", "bitrate")} if description else {}
            for name in UI_MODULES:
                module = importlib.import_module("hngoos_dm."+name)
                snapshots[module] = module.__dict__.copy()
                importlib.reload(module)
        except Exception:
            for module, snapshot in snapshots.items():
                module.__dict__.clear()
                module.__dict__.update(snapshot)
            LOG.exception("UI reload rejected; previous view retained")
            return False
        root.after_cancel(app.refresh_id)
        for name in ("navigation_timer", "presentation_timer", "source_resize_timer", "redraw_timer"):
            if timer := getattr(app, name, None):
                root.after_cancel(timer)
                setattr(app, name, None)
        app._presentation_pending = False
        shutdown = app.shutdown_after.get()
        close_to_tray = app.close_to_tray.get()
        for child in root.winfo_children():
            child.destroy()
        for modes, token in app.url.trace_info():
            app.url.trace_remove(modes, token)
        from hngoos_dm.app import App
        from hngoos_dm.icons import load_brand_icons, load_icons
        from hngoos_dm.ui_preferences import TRANSLATIONS, Localizer
        app.__class__ = App
        app.locale.__class__ = Localizer
        app.locale.reverse = {value: key for key, value in TRANSLATIONS.items()}
        app.brand_icons = load_brand_icons(root)
        app.icons = load_icons(root, light=app.theme == "light")
        app._icon_theme = app.theme
        app.download_editor = None
        app._layout()
        # bind_all keeps bound method objects across a hot reload. Replace the
        # original callback as well, or old redraw behavior survives the patch.
        root.bind_all("<Map>", app._presentation_mapped)
        app.connections.set("32")
        app.set_transfer_mode("maximum")
        app.shutdown_after.set(shutdown)
        app.close_to_tray.set(close_to_tray)
        app.apply_preferences()
        if description:
            from hngoos_dm.download_ui import DownloadEditor
            app.download_editor = DownloadEditor(app, description)
            app.download_editor.pack(fill="both", expand=True)
            for key, value in inputs.items():
                getattr(app.download_editor, key).set(value)
            if description["kind"] == "media":
                app.download_editor.format_changed()
            app.resize_source_card()
        root.protocol("WM_DELETE_WINDOW", app.request_close)
        app.refresh()
        self.title()
        self.last = self.stamp()
        LOG.info("UI refreshed; download manager and history retained")
        return True

    def watch(self):
        self.timer = None
        if getattr(self.app, "_closing", False):
            return
        try:
            current = self.stamp()
            if current != self.last:
                if self.pending and self.pending[0] == current and time.monotonic()-self.pending[1] >= 1:
                    self.reload_ui()
                    self.pending = None
                elif not self.pending or self.pending[0] != current:
                    self.pending = current, time.monotonic()
        except Exception:
            LOG.exception("Live refresh failed")
        finally:
            self.timer = self.root.after(700, self.watch)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=BASE / "tools/native-live-data")
    parser.add_argument("--preflight", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--preferences", choices=("general", "download", "system", "browser", "network"),
                        help="Open a preferences section for native UI review")
    parser.add_argument("--card", choices=("about", "update"), help="Open a centered card for native UI review")
    args = parser.parse_args()
    if args.preflight:
        from hngoos_dm.app import App
        with tempfile.TemporaryDirectory(prefix="hdm-ui-preflight-") as folder:
            root = tk.Tk()
            root.withdraw()
            app = App(root, Path(folder))
            try:
                root.update_idletasks()
            finally:
                app.close()
                app.manager.pool.shutdown(wait=True)
        return
    args.data_dir.mkdir(parents=True, exist_ok=True)
    from hngoos_dm.instance import InstanceLock
    instance = InstanceLock(args.data_dir / "instance.lock")
    logging.basicConfig(filename=args.data_dir / "development.log", level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s", encoding="utf-8")
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("hngoos.HDM.Development")
    root = tk.Tk()
    root.report_callback_exception = lambda *args: LOG.error("Tk callback", exc_info=args)
    session = None
    try:
        session = NativeSession(root, args.data_dir)
        if args.preferences:
            session.app.open_preferences()
        if args.card:
            root.after(300, session.app.open_about if args.card == "about" else session.app.check_update)
        root.update()
        LOG.info("Native development window opened, HWND=%s", root.winfo_id())
        root.mainloop()
    finally:
        if session:
            session.app.manager.close()
            session.app.manager.pool.shutdown(wait=True)
        instance.close()
    return session


if __name__ == "__main__":
    main()
