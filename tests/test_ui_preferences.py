"""UI behavior checks; headless runners exercise these in the packaged smoke test."""

import tempfile
import time
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch

from hngoos_dm.app import App


class PresentationTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f"A desktop display is required: {error}")
        self.folder = tempfile.TemporaryDirectory()
        self.app = App(self.root, Path(self.folder.name))
        self.errors = []
        self.root.report_callback_exception = lambda *args: self.errors.append(args)
        self.root.update()

    def tearDown(self):
        self.app.close()
        self.folder.cleanup()

    def pump(self, seconds=0.2):
        end = time.monotonic()+seconds
        while time.monotonic() < end:
            self.root.update()
            time.sleep(0.01)
        self.assertEqual(self.errors, [])

    def test_clipboard_detection_never_downloads_or_overwrites_typed_link(self):
        with patch.object(self.root, "clipboard_get", return_value="https://youtu.be/example"), \
                patch.object(self.app.manager, "add") as add:
            self.app.url.set("")
            self.app.clipboard_checked = 0
            self.app.check_clipboard()
            self.assertEqual(self.app.url.get(), "https://youtu.be/example")
            self.assertIn("video/nhạc", self.app.source_hint.get())
            add.assert_not_called()
        self.app.url.set("https://example.com/typing.zip")
        with patch.object(self.root, "clipboard_get", return_value="https://example.com/new.zip"):
            self.app.clipboard_checked = 0
            self.app.check_clipboard()
            self.assertEqual(self.app.url.get(), "https://example.com/typing.zip")
            self.assertTrue(self.app.clipboard_button.winfo_manager())
            self.app.use_clipboard_link()
            self.assertEqual(self.app.url.get(), "https://example.com/new.zip")
        self.assertEqual(len(self.app.tabs.tabs()), 1)
        self.assertEqual(self.app.connections.get(), "32")

    def test_media_link_download_uses_shared_history_and_mp3_choice(self):
        target = Path(self.folder.name)/"clip.mp3"
        target.write_bytes(b"audio fixture")
        self.app.url.set("https://youtu.be/example")
        self.app.download_format.set("MP3")
        with patch("hngoos_dm.media.download_video", return_value=[target]) as download:
            self.app.add()
            self.pump(0.6)
        row = self.app.store.all()[0]
        self.assertEqual(row["kind"], "media")
        self.assertEqual(row["state"], "complete")
        self.assertEqual(row["output"], str(target))
        self.assertEqual(download.call_args.kwargs["options"].audio, "mp3")
        self.assertFalse(self.app.media_busy)

    def test_information_menu_contains_language_and_browser_and_preferences_open_once(self):
        from hngoos_dm.information_ui import information_menu
        menu = information_menu(self.app)
        labels = [menu.entrycget(i, "label") for i in range(menu.index("end")+1)
                  if menu.type(i) != "separator"]
        self.assertIn("Ngôn ngữ", labels)
        self.assertIn("Giao diện", labels)
        self.assertIn("Tiện ích trình duyệt", labels)
        self.assertEqual(len(self.app.header_controls.winfo_children()), 2)
        self.assertFalse(hasattr(self.app, "language_switch"))
        self.assertFalse(hasattr(self.app, "theme_switch"))
        self.assertEqual(self.app.info_button.label, "")
        self.assertIs(self.app.info_button.image, self.app.icons["info"])
        dialog = self.app.open_preferences()
        self.assertIs(self.app.open_preferences(), dialog)
        self.pump()
        self.assertEqual(len(self.app.tabs.tabs()), 1)
        menu.destroy()
        dialog.destroy()

    def test_switches_preserve_task_inputs_and_persist_settings(self):
        self.app.url.set("https://example.com/download?token=keep-me")
        self.app.filename.set("Tài liệu của tôi.pdf")
        inputs = (self.app.url.get(), self.app.filename.get(), self.app.connections.get())
        self.app.set_preference("theme", "light")
        self.app.set_preference("language", "en")
        self.pump()
        self.assertEqual(self.app.store.setting("theme"), "light")
        self.assertEqual(self.app.store.setting("language"), "en")
        self.assertEqual(self.app.tabs.tab(0, "text"), "Download")
        self.assertEqual(self.app.table.heading("name", "text"), "FILENAME")
        self.assertEqual(inputs, (self.app.url.get(), self.app.filename.get(), self.app.connections.get()))
        self.app.set_bandwidth("medium")
        self.pump()
        self.assertEqual(self.app.store.setting("bandwidth_mode"), "medium")
        self.assertEqual(self.app.bandwidth_mode.get(), "Vừa (4 MB/s)")
        self.app.set_preference("language", "vi")
        self.pump()
        self.assertEqual(self.app.tabs.tab(0, "text"), "Tải xuống")
        self.assertEqual(self.app.speed_meter.mode.label, "MEDIUM")

    def test_confirmation_has_source_specific_options_and_cancel_never_downloads(self):
        from hngoos_dm.download_ui import DownloadEditor
        self.app.url.set("https://example.com/document.pdf")
        with patch.object(self.app.manager, "add") as add:
            dialog = DownloadEditor(self.app, {"original": self.app.url.get(), "url": self.app.url.get(), "kind": "file"})
            self.assertFalse(hasattr(dialog, "media_controls"))
            self.assertEqual(dialog.connections.get(), "32")
            dialog.destroy()
            self.pump()
            add.assert_not_called()
        self.app.url.set("https://youtu.be/example")
        dialog = DownloadEditor(self.app, {"original": self.app.url.get(), "url": self.app.url.get(), "kind": "media"})
        self.app.download_editor = dialog
        dialog.pack(fill="both", expand=True)
        self.app.editor_panel.grid(row=1, column=0, sticky="ew")
        dialog.toggle_advanced()
        self.pump()
        self.assertTrue(dialog.media_controls.winfo_ismapped())
        dialog.format.set("MP3")
        dialog.format_changed()
        self.assertFalse(dialog.quality_selector.winfo_manager())
        with patch.object(self.app, "add") as add:
            dialog.confirm()
            add.assert_called_once_with(resolved_source=("media", "https://youtu.be/example"))
            self.assertEqual(self.app.download_format.get(), "MP3")

    def test_detect_html_before_confirmation_and_do_not_start_download(self):
        self.app.url.set("https://example.com/watch")
        with patch("hngoos_dm.links.describe_source", return_value={"kind": "media", "original": self.app.url.get(),
                      "url": self.app.url.get(), "filename": "Example.mp4"}), \
                patch.object(self.app.manager, "add") as add:
            self.app.prepare_download()
            self.pump(0.6)
            dialog = self.app.download_editor
            self.assertEqual(dialog.kind, "media")
            add.assert_not_called()
            dialog.destroy()

    def test_completed_row_safety_button_uses_real_file_and_never_uploads_automatically(self):
        source = Path(self.folder.name)/"invoice.pdf"
        source.write_bytes(b"document fixture")
        row = self.app.store.create("https://example.com/invoice.pdf", source.parent, source.name)
        self.app.store.update(row["id"], state="complete", output=str(source), total=source.stat().st_size,
                              downloaded=source.stat().st_size)
        with patch("hngoos_dm.safety_ui.inspect_download", return_value={"reasons": [], "safety_note": "Sơ bộ + Defender"}), \
                patch("hngoos_dm.virustotal.VirusTotalClient.request") as remote:
            self.pump(0.6)
            button = self.app.row_safety_buttons[row["id"]]
            self.assertTrue(button.winfo_ismapped())
            button.invoke()
            self.pump(0.6)
            dialog = self.app.safety_dialog
            self.assertEqual(dialog.path.get(), str(source))
            self.assertEqual(len(dialog.digest), 64)
            remote.assert_not_called()
            dialog.show_report({"status": "queued", "stats": {}, "engines": [], "date": None})
            self.assertIn("chưa có kết luận", dialog.vt_status.get())
            dialog.show_report({"status": "completed", "stats": {}, "engines": [], "date": None})
            self.assertIn("không có kết quả", dialog.vt_status.get())
            dialog.destroy()

    def test_main_has_no_media_controls_and_panels_resize_in_both_themes(self):
        from tkinter import ttk
        def widgets(parent):
            for child in parent.winfo_children():
                yield child
                yield from widgets(child)
        labels = [child.cget("text") for child in widgets(self.root) if isinstance(child, ttk.Label)]
        self.assertNotIn("Định dạng", labels)
        self.assertNotIn("Độ cao tối đa", labels)
        for theme, geometry in (("light", "1120x720"), ("dark", "1440x900")):
            self.app.set_preference("theme", theme)
            self.root.geometry(geometry)
            self.pump()
            self.assertGreater(self.app.queue_panel.winfo_height(), 300)
            self.assertGreater(self.app.url_entry.winfo_width(), 400)
            self.assertLess(self.app.url_entry.winfo_rootx()+self.app.url_entry.winfo_width(),
                            self.root.winfo_rootx()+self.root.winfo_width())
            self.assertFalse(hasattr(self.app, "download_button"))
            self.assertLess(self.app.brand_label.winfo_rootx()+self.app.brand_label.winfo_width(),
                            self.app.categories.winfo_rootx())
            self.assertLessEqual(self.app.categories.winfo_rootx()+self.app.categories.winfo_width(),
                                 self.app.info_button.winfo_rootx())

    def test_light_theme_has_readable_selection_and_new_dialogs_after_repeated_toggles(self):
        from tkinter import ttk

        def luminance(color):
            values = [value/65535 for value in self.root.winfo_rgb(color)]
            linear = [value/12.92 if value <= 0.04045 else ((value+0.055)/1.055)**2.4 for value in values]
            return sum(value*weight for value, weight in zip(linear, (0.2126, 0.7152, 0.0722), strict=True))

        style = ttk.Style(self.root)
        for light in (True, False, True):
            self.app.set_preference("theme", "light" if light else "dark")
            self.pump()
            if not light:
                self.assertEqual(str(style.lookup("TFrame", "background")), "#0f121c")
                continue
            self.assertEqual(self.root.cget("background"), "#f5f6fa")
            for name, background, states in (("TButton", "background", ()),
                    ("Primary.TButton", "background", ()), ("Treeview", "background", ("selected",)),
                    ("TCombobox", "fieldbackground", ("readonly",)), ("TCheckbutton", "background", ()),
                    ("TNotebook.Tab", "background", ("selected",))):
                with self.subTest(style=name):
                    fg = luminance(style.lookup(name, "foreground", states))
                    bg = luminance(style.lookup(name, background, states))
                    self.assertGreaterEqual((max(fg, bg)+0.05)/(min(fg, bg)+0.05), 4.5)
            dialog = tk.Toplevel(self.root)
            button = ttk.Button(dialog, text="Theme check")
            button.pack()
            self.pump()
            self.assertEqual(dialog.cget("background"), "#f5f6fa")
            self.assertEqual(str(style.lookup("TButton", "foreground")), "#202434")
            dialog.destroy()

    def test_filters_keep_history_and_restore_completed_safety_actions(self):
        jobs = {}
        for name, state in (("invoice.pdf", "complete"), ("setup.exe.chuakiemtra", "quarantined"),
                            ("clip.mp4", "paused"), ("song.mp3", "paused")):
            path = Path(self.folder.name)/name
            path.touch()
            row = self.app.store.create("https://example.com/"+name, path.parent, name)
            self.app.store.update(row["id"], state=state, output=str(path))
            jobs[name] = row["id"]
        self.app.set_filter("all")
        self.pump()
        self.assertEqual(set(self.app.table.get_children()), set(jobs.values()))
        self.app.set_filter("app")
        self.pump()
        app_id = jobs["setup.exe.chuakiemtra"]
        self.assertEqual(self.app.table.get_children(), (app_id,))
        self.assertIn(app_id, self.app.row_safety_buttons)
        self.app.set_filter("image")
        self.pump()
        self.assertEqual(self.app.table.get_children(), ())
        self.assertTrue(self.app.empty_state.winfo_ismapped())
        self.app.set_filter("all")
        self.pump()
        self.assertEqual(set(self.app.table.get_children()), set(jobs.values()))
        self.assertEqual(len(self.app.store.all()), 4)
        self.assertIn(jobs["invoice.pdf"], self.app.row_safety_buttons)

    def test_active_media_title_without_extension_uses_selected_output_category(self):
        row = self.app.store.create("https://youtu.be/example", Path(self.folder.name), "Live title without extension")
        self.app.store.update(row["id"], kind="media", state="downloading", media_options={"audio": "mp3"})
        self.app.set_filter("music")
        self.pump()
        self.assertEqual(self.app.table.get_children(), (row["id"],))
        self.app.store.update(row["id"], media_options={"audio": ""})
        self.app.set_filter("video")
        self.pump()
        self.assertEqual(self.app.table.get_children(), (row["id"],))
        self.app.store.update(row["id"], state="complete", filename="Audio-only source.m4a")
        self.app.set_filter("music")
        self.pump()
        self.assertEqual(self.app.table.get_children(), (row["id"],))

    def test_speed_meter_ignores_stale_rates_and_includes_torrent_upload(self):
        from types import SimpleNamespace
        for name, state, rate in (("active.pdf", "downloading", 2048), ("old.zip", "complete", 9000)):
            row = self.app.store.create("https://example.com/"+name, Path(self.folder.name), name)
            self.app.store.update(row["id"], state=state, speed=rate)
        self.app.torrent_jobs = [SimpleNamespace(closed=False, completed=False,
            status=lambda: {"download_rate": 1024, "upload_rate": 512}, close=lambda: None)]
        self.app.set_filter("all")
        self.pump()
        self.assertEqual(self.app.speed_meter.down.get(), "3.0 KB/s")
        self.assertEqual(self.app.speed_meter.up.get(), "512.0 B/s")
        for mode, label in (("light", "LOW"), ("maximum", "HIGH"), ("medium", "MEDIUM")):
            self.app.set_bandwidth(mode)
            self.assertEqual(self.app.store.setting("bandwidth_mode"), mode)
            self.assertEqual(self.app.manager.bandwidth.rate, self.app.manager.bandwidth.MODES[mode])
            self.assertEqual(self.app.speed_meter.mode.label, label)

    def test_rounded_fields_preserve_native_editing_return_and_readonly_choices(self):
        from hngoos_dm.rounded import RoundedCombobox
        entry = self.app.url_entry
        entry.insert(0, "https://example.com/original")
        entry.delete(20, "end")
        entry.insert("end", "updated.pdf")
        self.assertEqual(entry.get(), "https://example.com/updated.pdf")
        with patch.object(self.app, "prepare_download") as prepare:
            entry.focus_force()
            self.pump()
            entry.event_generate("<Return>")
            self.pump()
            prepare.assert_called_once()
        combo = RoundedCombobox(self.root, values=("A", "B"), state="readonly")
        combo.current(1)
        self.assertEqual(combo.get(), "B")
        combo.configure(values=("C", "D"), state="readonly")
        combo.current(0)
        self.assertEqual(combo.get(), "C")
        combo.destroy()

    @patch("hngoos_dm.update_ui.check_update", return_value=None)
    def test_update_check_uses_single_dialog_and_stays_inside_app(self, check):
        with patch("hngoos_dm.app.webbrowser.open") as browser:
            self.app.check_update()
            dialog = self.app.update_dialog
            self.app.check_update()
            self.assertIs(self.app.update_dialog, dialog)
            self.pump()
            self.assertEqual(dialog.status.get(), "Bạn đang dùng phiên bản mới nhất.")
            self.assertFalse(dialog.busy)
            check.assert_called_once()
            browser.assert_not_called()
            dialog.close()

    def test_install_rejects_tampered_bytes_without_launching(self):
        import hashlib

        with patch("hngoos_dm.update_ui.check_update", return_value=None):
            self.app.check_update()
            self.pump()
        dialog = self.app.update_dialog
        dialog.path = Path(self.folder.name)/"HDM.exe"
        content = b"trusted fixture"
        dialog.asset = {"name": "HDM.exe", "size": len(content), "sha256": hashlib.sha256(content).hexdigest()}
        dialog.path.write_bytes(b"X"*len(content))
        with patch("hngoos_dm.update_ui.launch_installer") as launch:
            dialog.install()
            self.pump()
            self.assertIn("signed release", dialog.status.get())
            launch.assert_not_called()
        dialog.close()

    def test_windows_update_uses_independent_installer_before_closing_app(self):
        with patch("hngoos_dm.update_ui.check_update", return_value=None):
            self.app.check_update()
            self.pump()
        dialog = self.app.update_dialog
        path = Path(self.folder.name)/"HDM-Setup.exe"
        path.touch()
        with patch("hngoos_dm.update_ui.platform.system", return_value="Windows"), \
                patch("hngoos_dm.update_ui.launch_installer") as launch, patch.object(self.app, "close") as close:
            dialog.launch(path)
            launch.assert_called_once_with(path)
            close.assert_called_once_with()
        dialog.close()
