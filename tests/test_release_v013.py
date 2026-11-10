"""Acceptance coverage for local export choices and the browser guide."""

import os
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from hngoos_dm.media import MediaOptions, find_ffmpeg, normalize_audio, ydl_options


class ExportTests(unittest.TestCase):
    def test_added_audio_exports_are_readable_and_keep_the_selected_extension(self):
        from hngoos_dm.processing import run_ffmpeg

        for kind, codec in (("aac", "aac"), ("flac", "flac"), ("aiff", "pcm_s16be"),
                            ("wma", "wmav2"), ("ac3", "ac3")):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as folder:
                source = run_ffmpeg(["-f", "lavfi", "-i", "sine=sample_rate=48000", "-t", "0.3"],
                                    Path(folder)/"fixture.wav")
                options = MediaOptions(audio=kind, audio_bitrate=192)
                self.assertEqual(ydl_options(folder, options, find_ffmpeg())["format"], "bestaudio/best")
                normalize_audio(folder, options, threading.Event())
                target = source.with_suffix("."+kind)
                self.assertTrue(target.is_file())
                decoded = subprocess.run([find_ffmpeg(), "-hide_banner", "-i", str(target),
                                          "-f", "null", "-"], capture_output=True, text=True, check=False)
                self.assertEqual(decoded.returncode, 0, decoded.stderr)
                self.assertIn(codec, decoded.stderr)
                self.assertFalse(source.exists())

    def test_added_video_containers_remux_a_real_video(self):
        from yt_dlp import YoutubeDL
        from yt_dlp.postprocessor.ffmpeg import FFmpegVideoRemuxerPP

        from hngoos_dm.processing import run_ffmpeg

        for kind in ("mov", "mkv", "m4v"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as folder:
                source = run_ffmpeg(["-f", "lavfi", "-i", "color=s=64x64:r=10", "-t", "0.3",
                                     "-c:v", "libx264"], Path(folder)/"fixture.mp4")
                settings = ydl_options(folder, MediaOptions(container=kind, format_id="source"), find_ffmpeg())
                self.assertEqual(settings["postprocessors"][0]["preferedformat"], kind)
                with YoutubeDL(settings) as downloader:
                    _, info = FFmpegVideoRemuxerPP(downloader, preferedformat=kind).run(
                        {"filepath": str(source), "ext": "mp4"})
                target = Path(info["filepath"])
                self.assertEqual(target.suffix, "."+kind)
                decoded = subprocess.run([find_ffmpeg(), "-v", "error", "-i", str(target),
                                          "-f", "null", "-"], capture_output=True, check=False)
                self.assertEqual(decoded.returncode, 0, decoded.stderr)


class BrowserGuideTests(unittest.TestCase):
    def test_no_browser_is_launched_when_the_selected_browser_has_no_window(self):
        from hngoos_dm import browser

        with patch.object(browser.sys, "platform", "win32"), \
                patch.object(browser, "_opera_window", return_value=None), \
                patch("subprocess.Popen") as launch:
            with self.assertRaises(OSError):
                browser._open_opera_extensions(Path("Opera/opera.exe"))
            launch.assert_not_called()

    @unittest.skipUnless(__import__("sys").platform == "win32", "Windows registry")
    def test_orphan_opera_launcher_is_not_an_installed_browser(self):
        from hngoos_dm import browser

        with tempfile.TemporaryDirectory() as folder:
            launcher = Path(folder)/"Programs/Opera/launcher.exe"
            launcher.parent.mkdir(parents=True)
            launcher.touch()
            with patch.dict(os.environ, {"LOCALAPPDATA": folder, "PROGRAMFILES": folder,
                                        "PROGRAMFILES(X86)": folder}), \
                    patch("winreg.OpenKey", side_effect=FileNotFoundError):
                self.assertIsNone(browser.find_browser("opera"))
                (launcher.parent/"opera.exe").touch()
                self.assertIsNotNone(browser.find_browser("opera"))

    @unittest.skipUnless(__import__("sys").platform == "win32", "Windows registry")
    def test_opera_gx_product_is_not_misidentified_as_opera_in_a_custom_folder(self):
        from unittest.mock import MagicMock

        from hngoos_dm import browser

        with tempfile.TemporaryDirectory() as folder:
            executable = Path(folder)/"opera.exe"
            executable.touch()
            with patch("winreg.OpenKey", return_value=MagicMock()), \
                    patch("winreg.QueryValueEx", return_value=(str(executable), 1)), \
                    patch.object(browser, "_windows_product_name", return_value="Opera GX Internet Browser"), \
                    patch.dict(os.environ, {name: folder for name in ("LOCALAPPDATA", "PROGRAMFILES", "PROGRAMFILES(X86)")}):
                self.assertIsNone(browser.find_browser("opera"))
                self.assertEqual(browser.find_browser("opera-gx"), executable)


class InterfaceTests(unittest.TestCase):
    # Reuse the established isolated native fixture without inheriting its tests.
    from tests import test_ui_preferences as fixture
    setUp = fixture.PresentationTests.setUp
    tearDown = fixture.PresentationTests.tearDown
    pump = fixture.PresentationTests.pump

    def test_preferences_checkbox_text_does_not_overlap_adjacent_rows(self):
        from tkinter import ttk

        surface = self.app.presentation_surface
        for geometry in ("800x500", "1120x720", "1568x1000"):
            self.root.geometry(geometry)
            self.app.open_preferences()
            self.pump()
            boxes = []
            for widget, items in surface.items_by_widget.items():
                if isinstance(widget, ttk.Checkbutton):
                    for item in items:
                        if surface.type(item) == "text":
                            box = surface.bbox(item)
                            self.assertLessEqual(box[3]-box[1], widget.winfo_height()+4,
                                                 (geometry, widget.cget("text")))
                            boxes.append((widget.master, box))
            for parent, box in boxes:
                for other_parent, other in boxes:
                    if parent is other_parent and box != other:
                        self.assertTrue(box[3] <= other[1] or other[3] <= box[1], (geometry, box, other))

    def test_empty_hints_follow_language_and_disappear_with_content(self):
        surface = self.app.presentation_surface
        self.app.url.set("")
        self.pump()
        texts = lambda: [surface.itemcget(item, "text") for item in surface.find_all()
                         if surface.type(item) == "text"]
        self.assertIn("Dán đường dẫn tải file vào đây", texts())
        self.assertIn("Danh sách trống", texts())
        self.app.url.set("x")
        self.app.store.create("https://example.com/a", self.app.directory.get(), "a", 1)
        self.app._refresh_state()
        self.pump()
        self.assertNotIn("Dán đường dẫn tải file vào đây", texts())
        self.assertNotIn("Danh sách trống", texts())

    def test_browser_guide_surface_click_opens_link_and_copies_exact_folder(self):
        from hngoos_dm.information_ui import browser_dialog

        with patch("hngoos_dm.browser.connect_extension"):
            page = browser_dialog(self.app, "opera-gx")
        self.pump()
        surface = self.app.presentation_surface
        with patch("hngoos_dm.browser.open_extensions") as open_page:
            box = next(box for widget, box, _ in surface.regions if widget is page.extension_link)
            surface.event_generate("<Button-1>", x=int(box[0]+box[2]/2), y=int(box[1]+box[3]/2))
            self.pump(.05)
            open_page.assert_called_once_with("opera-gx")
        with patch.object(self.root, "clipboard_clear") as clear, \
                patch.object(self.root, "clipboard_append") as append:
            page.copy_folder.invoke()
            clear.assert_called_once()
            append.assert_called_once_with(str(page.folder_path))

    def test_browser_availability_is_refreshed_when_preferences_reopens(self):
        with patch("hngoos_dm.browser.find_browser", return_value=Path("browser.exe")):
            page = self.app.open_preferences()
        page.hide()
        with patch("hngoos_dm.browser.find_browser", return_value=None):
            self.app.open_preferences()
        for button in self.app.browser_install_buttons.values():
            self.assertEqual(str(button.cget("state")), "disabled")

    def test_added_formats_keep_source_quality_and_select_audio_conversion(self):
        from hngoos_dm.download_ui import DownloadEditor

        url = "https://youtu.be/formats"
        self.app.url.set(url)
        editor = self.app.download_editor = DownloadEditor(self.app, {
            "original": url, "url": url, "kind": "media", "filename": "Fixture.mp4", "formats": [
                {"format_id": "18", "ext": "mp4", "height": 360, "vcodec": "avc1", "acodec": "aac"}]})
        editor.pack(fill="both", expand=True)
        for kind in ("AAC", "FLAC", "AIFF", "WMA", "AC3", "MOV", "MKV", "M4V"):
            with self.subTest(kind=kind):
                self.assertIn(kind, editor.format_choices.buttons)
                editor.format_choices.buttons[kind].invoke()
                self.assertTrue(editor.filename.get().endswith("."+kind.lower()))
                if kind in {"MOV", "MKV", "M4V"}:
                    self.assertEqual(set(editor.quality_choices.buttons), {"360"})
                    self.assertEqual(editor.format_id.get(), "18")
                else:
                    self.assertFalse(editor.video_output)
                    self.assertEqual(editor.format_id.get(), "")

    def test_photo_album_keeps_image_name_and_hides_video_options(self):
        from hngoos_dm.download_ui import DownloadEditor

        url = "https://www.tiktok.com/@example/photo/7680913365123796231"
        self.app.url.set(url)
        editor = self.app.download_editor = DownloadEditor(self.app, {
            "original": url, "url": url, "kind": "media", "filename": "Album.jpg", "media_type": "photos"})
        editor.pack(fill="both", expand=True)
        self.pump()
        self.assertTrue(editor.ready)
        self.assertFalse(editor.show_options)
        self.assertEqual(editor.filename.get(), "Album.jpg")
        self.assertFalse(editor.format_choices.winfo_ismapped())
        self.assertFalse(editor.quality_choices.winfo_ismapped())
