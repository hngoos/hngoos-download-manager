"""UI behavior checks; headless runners exercise these in the packaged smoke test."""

import gc
import sys
import tempfile
import time
import tkinter as tk
import unittest
from pathlib import Path
from tkinter import ttk
from unittest.mock import patch

from hngoos_dm.app import App


class PresentationTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform == "win32", "Windows native painting")
    def test_native_redraw_does_not_erase_children_before_tk_can_repaint(self):
        import ctypes
        from ctypes import wintypes

        from hngoos_dm.ui_preferences import redraw_window

        user32 = ctypes.windll.user32
        set_proc = user32.SetWindowLongPtrW if ctypes.sizeof(ctypes.c_void_p) == 8 else user32.SetWindowLongW
        set_proc.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
        set_proc.restype = ctypes.c_ssize_t
        user32.CallWindowProcW.argtypes = [ctypes.c_void_p, wintypes.HWND, wintypes.UINT,
                                          wintypes.WPARAM, wintypes.LPARAM]
        user32.CallWindowProcW.restype = ctypes.c_ssize_t
        callback_type = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT,
                                          wintypes.WPARAM, wintypes.LPARAM)
        handle = self.app.empty_panel.winfo_id()
        erases = []

        @callback_type
        def observe(hwnd, message, wparam, lparam):
            if message == 0x14:  # WM_ERASEBKGND
                erases.append(message)
            return user32.CallWindowProcW(previous, hwnd, message, wparam, lparam)

        previous = set_proc(handle, -4, ctypes.cast(observe, ctypes.c_void_p).value)
        try:
            redraw_window(self.root)
            self.assertEqual(erases, [], "Native erasure must not expose a blank panel before Tk paints")
        finally:
            set_proc(handle, -4, previous)
        self.pump()

    @unittest.skipUnless(sys.platform == "win32", "Windows native painting")
    def test_transitions_hold_native_paint_until_tk_finishes(self):
        import ctypes
        from ctypes import wintypes

        import hngoos_dm.ui_preferences as preferences

        user32 = ctypes.windll.user32
        user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
        user32.GetAncestor.restype = wintypes.HWND
        user32.IsWindowVisible.argtypes = [wintypes.HWND]
        handle = user32.GetAncestor(self.root.winfo_id(), 2)
        observed = []
        original = preferences.recolor

        def recolor(*args):
            if args[0] is self.root:
                observed.append(bool(user32.IsWindowVisible(handle)))
            return original(*args)

        with patch.object(preferences, "recolor", side_effect=recolor):
            page = self.app.open_preferences()
            self.app.set_preference("theme", "light")
            self.app.set_preference("theme", "dark")
        self.assertTrue(observed)
        self.assertEqual(observed, [False, True, True],
                         "Navigation buffers native surfaces; the shared scene retains its own complete frame")
        self.assertTrue(user32.IsWindowVisible(handle))
        self.assertTrue(page.winfo_ismapped())
        self.assertTrue(self.app.preference_directory.control.winfo_ismapped())
        original_redraw = self.app.schedule_redraw
        observed.clear()

        def redraw():
            observed.append(bool(user32.IsWindowVisible(handle)))
            original_redraw()

        with patch.object(self.app, "schedule_redraw", side_effect=redraw):
            self.app.open_information()
            self.app.open_preferences()
        self.assertTrue(observed)
        self.assertEqual(observed, [False]*len(observed))
        self.assertTrue(user32.IsWindowVisible(handle))

    @unittest.skipUnless(sys.platform == "win32", "Windows native painting")
    def test_failed_presentation_restores_painting_without_showing_hidden_windows(self):
        from hngoos_dm.ui_preferences import buffered_presentation

        observed = []

        @buffered_presentation
        def fail(owner):
            observed.append(True)
            raise ValueError("presentation fixture")

        with self.assertRaisesRegex(ValueError, "presentation fixture"):
            fail(self.app)
        self.assertEqual(self.root._hdm_paint_depth, 0)
        self.assertTrue(self.root.winfo_viewable())
        self.root.withdraw()
        fail_without_mapping = buffered_presentation(lambda owner: observed.append(True))
        fail_without_mapping(self.app)
        self.root.update_idletasks()
        self.assertFalse(self.root.winfo_ismapped())
        self.assertEqual(observed, [True, True])

    @unittest.skipUnless(sys.platform == "win32" and __import__("os").environ.get("HDM_NATIVE_RENDER_TESTS") == "1",
                         "Requires an unobstructed Windows desktop")
    def test_theme_and_page_transitions_do_not_publish_partial_frames(self):
        """Read the screen, never PrintWindow: requesting a repaint hides this regression."""
        from PIL import ImageChops, ImageGrab

        import hngoos_dm.ui_preferences as preferences

        self.root.geometry("1280x800+30+30")
        self.root.attributes("-topmost", True)
        page = self.app.open_preferences()
        self.pump(.5)
        bounds = (self.root.winfo_rootx(), self.root.winfo_rooty(),
                  self.root.winfo_rootx()+self.root.winfo_width(),
                  self.root.winfo_rooty()+self.root.winfo_height()-80)

        def assert_atomic(action, owner, name):
            before = ImageGrab.grab(bbox=bounds, all_screens=True).convert("RGB")
            captured = []
            original = getattr(owner, name)

            def observe(*args, **kwargs):
                result = original(*args, **kwargs)
                if name == "recolor" and args[0] is not self.root:
                    return result
                # Pause halfway through the transition, giving Windows time to
                # expose any prematurely cleared or partly recolored children.
                self.root.update_idletasks()
                time.sleep(.12)
                captured.append(ImageGrab.grab(bbox=bounds, all_screens=True).convert("RGB"))
                return result

            with patch.object(owner, name, side_effect=observe):
                action()
            self.pump(.3)
            difference = ImageChops.difference(before, captured[0])
            changed = sum(max(pixel) > 12 for pixel in difference.getdata())
            self.assertLess(changed/(before.width*before.height), .002,
                            "The desktop exposed an unfinished theme/page transition")

        for theme in ("light", "dark"):
            assert_atomic(lambda theme=theme: self.app.set_preference("theme", theme),
                          preferences, "recolor")
        assert_atomic(self.app.open_information, self.app, "schedule_redraw")
        self.assertFalse(page.winfo_ismapped())
        assert_atomic(self.app.open_preferences, self.app, "schedule_redraw")
        self.assertTrue(page.winfo_ismapped())

    def test_preferences_text_icons_and_checks_share_one_drawing_surface(self):
        page = self.app.open_preferences()
        self.pump()
        surface = getattr(page, "surface", None)
        self.assertIsInstance(surface, tk.Canvas,
                              "Preferences must draw labels and icons on a common surface")
        self.assertTrue(surface.winfo_ismapped())
        self.assertIn(self.app.brand_label, surface.items_by_widget)
        caption = self.app.preference_rows["Giao diện"][0]
        self.assertIn(caption, surface.items_by_widget)
        self.assertEqual(surface.type(surface.items_by_widget[caption][0]), "text")
        self.assertIn(self.app.browser_capture_button, surface.items_by_widget)
        self.assertTrue(all(surface.type(item) != "window"
                            for item in surface.items_by_widget[self.app.browser_capture_button]))
        self.assertEqual(str(surface.cget("background")), "#121212")
        self.assertTrue(surface.editors)
        self.assertTrue(all(isinstance(field, ttk.Entry)
                            for field in surface.editors.values()))

    def test_shared_preferences_surface_replaces_language_and_theme_as_complete_frames(self):
        page = self.app.open_preferences()
        self.pump()
        surface = getattr(page, "surface", None)
        self.assertIsInstance(surface, tk.Canvas)
        for language, theme in (("en", "light"), ("vi", "dark"), ("en", "dark"), ("vi", "light")):
            self.app.set_preference("language", language)
            self.app.set_preference("theme", theme)
            self.pump(.1)
            caption = self.app.preference_rows["Giao diện"][0]
            items = surface.items_by_widget[caption]
            self.assertEqual(len(items), 1)
            self.assertEqual(surface.itemcget(items[0], "text"), "Appearance" if language == "en" else "Giao diện")
            self.assertEqual(surface.presented, (theme, language))
        self.app.open_information()
        self.pump()
        self.assertFalse(surface.winfo_ismapped())
        self.assertTrue(self.app.tabs.winfo_ismapped())
        self.app.open_preferences()
        self.pump()
        self.assertIs(self.app.preferences_dialog.surface, surface)
        self.assertTrue(surface.winfo_ismapped())

    def test_shared_surface_clicks_fields_and_nested_pages_preserve_commands(self):
        from unittest.mock import Mock

        from hngoos_dm.information_ui import ContentPage

        page = self.app.open_preferences()
        self.pump()
        surface = page.surface
        button = self.app.browser_capture_button
        previous = self.app.browser_capture.get()
        region = next(region for region in surface.regions if region[0] == button)
        x, y, width, height = region[1]
        surface.event_generate("<Button-1>", x=x+width//2, y=y+height//2)
        self.pump()
        self.assertEqual(self.app.browser_capture.get(), not previous)
        source = self.app.preference_directory.control
        editor = surface.editors[source]
        destination = str(Path(self.folder.name)/"chosen")
        editor.delete(0, "end")
        editor.insert(0, destination)
        editor.event_generate("<FocusOut>")
        self.pump()
        self.assertEqual(self.app.directory.get(), destination)
        self.assertEqual(self.app.store.setting("download_directory"), destination)
        action = self.app.preference_directory.action_button
        callback = Mock()
        action.command = callback
        surface.render()
        region = next(region for region in surface.regions if region[0] == action)
        x, y, width, height = region[1]
        surface.event_generate("<Button-1>", x=x+width//2, y=y+height//2)
        self.pump()
        callback.assert_called_once()
        child = ContentPage(self.app, "test")
        self.pump()
        self.assertFalse(surface.winfo_ismapped())
        child.destroy()
        self.pump()
        self.assertTrue(surface.winfo_ismapped())
        self.assertIn(self.app.brand_label, surface.items_by_widget)

    def test_shared_surface_rapid_choices_publish_only_complete_scenes(self):
        page = self.app.open_preferences()
        self.pump()
        surface = page.surface
        for index in range(20):
            choices = self.app.preference_language if index % 2 == 0 else self.app.preference_theme
            value = ("en" if index % 4 == 0 else "vi") if index % 2 == 0 else (
                "light" if index % 4 == 1 else "dark")
            button = choices.buttons[value]
            region = next(region for region in surface.regions if region[0] == button)
            x, y, width, height = region[1]
            surface.event_generate("<Button-1>", x=x+width//2, y=y+height//2)
            self.pump(.1)
            self.assertEqual(surface.presented, (self.app.theme, self.app.locale.language))
            for widget, items in surface.items_by_widget.items():
                if isinstance(widget, ttk.Label) and not widget.cget("image"):
                    self.assertEqual(len(items), 1)
                    self.assertEqual(surface.itemcget(items[0], "text"), surface.text(widget))
        final = self.app.preference_language.buttons["en"]
        region = next(region for region in surface.regions if region[0] == final)
        x, y, width, height = region[1]
        for index in range(20):
            surface.event_generate("<Button-1>", x=x+width//2, y=y+height//2, when="tail")
        self.pump(.4)
        self.assertEqual(self.app.locale.language, "en")
        self.assertIsNone(surface.action_timer)
        self.assertIsNone(surface.pending_action)

    @unittest.skipUnless(sys.platform == "win32", "Windows native painting")
    def test_shared_surface_does_not_force_native_erasure_during_preferences(self):
        import ctypes

        page = self.app.open_preferences()
        self.pump()
        with patch.object(ctypes.windll.user32, "RedrawWindow") as redraw:
            for language, theme in (("en", "light"), ("vi", "dark")):
                self.app.set_preference("language", language)
                self.app.set_preference("theme", theme)
                self.pump(.1)
                self.assertEqual(page.surface.presented, (theme, language))
            redraw.assert_not_called()

    def test_shared_surface_tracks_native_and_programmatic_settings_changes(self):
        page = self.app.open_preferences()
        self.pump()
        surface = page.surface
        button = self.app.browser_capture_button
        button.invoke()
        self.pump()
        mark = surface.items_by_widget[button][0]
        self.assertEqual(surface.itemcget(mark, "fill"), "#67d1f4" if self.app.browser_capture.get() else "#121212")
        self.app.proxy_mode.set("manual")
        self.pump()
        self.assertEqual(len(surface.editors), 2)
        visible = [item for item in surface.editor_windows.values()
                   if surface.itemcget(item, "state") != "hidden"]
        self.assertEqual(len(visible), 2)
        self.app.proxy_mode.set("direct")
        self.pump()
        visible = [item for item in surface.editor_windows.values()
                   if surface.itemcget(item, "state") != "hidden"]
        self.assertEqual(len(visible), 1)

    def test_shared_surface_retains_images_until_the_next_frame_is_ready(self):
        self.app.open_preferences()
        self.app.set_preference("theme", "light")
        self.pump()
        image = str(self.app.preference_directory.action_button.image)
        self.app.set_preference("theme", "dark")
        gc.collect()
        self.assertIn(image, self.root.tk.call("image", "names"),
                      "The displayed frame must retain its images until replacement")
        self.pump()
        self.assertEqual(self.app.preferences_dialog.surface.presented, ("dark", self.app.locale.language))

    def test_shared_surface_keeps_latest_choice_for_each_independent_setting(self):
        surface = self.app.open_preferences().surface
        self.pump()
        for choices, value in ((self.app.preference_theme, "light"), (self.app.preference_language, "en")):
            region = next(region for region in surface.regions if region[0] == choices.buttons[value])
            x, y, width, height = region[1]
            surface.event_generate("<Button-1>", x=x+width//2, y=y+height//2, when="tail")
        self.pump()
        self.assertEqual(surface.presented, ("light", "en"))

    def test_shared_surface_keyboard_modal_and_recreation_preserve_actions(self):
        from hngoos_dm.information_ui import CenteredCard

        page = self.app.open_preferences()
        self.pump()
        surface = page.surface
        surface.focus_force()
        surface.focused = self.app.browser_capture_button
        previous = self.app.browser_capture.get()
        surface.event_generate("<Return>")
        self.pump()
        self.assertEqual(self.app.browser_capture.get(), not previous)
        editor = surface.editors[self.app.preference_directory.control]
        editor.focus_force()
        self.pump()
        editor.event_generate("<Tab>")
        self.pump()
        self.assertIs(self.root.focus_get(), surface)
        surface.event_generate("<Shift-Tab>")
        self.pump()
        self.assertIs(self.root.focus_get(), editor)
        card = CenteredCard(self.app)
        self.pump()
        region = next(region for region in surface.regions if region[0] == self.app.browser_capture_button)
        x, y, width, height = region[1]
        surface.event_generate("<Button-1>", x=x+width//2, y=y+height//2)
        self.pump()
        self.assertFalse(card.winfo_exists())
        self.assertEqual(self.app.browser_capture.get(), not previous)
        for _ in range(3):
            old = self.app.preferences_dialog.surface
            button = self.app.preference_reset_button
            region = next(region for region in old.regions if region[0] == button)
            x, y, width, height = region[1]
            with patch("hngoos_dm.app.messagebox.askyesno", return_value=True):
                old.event_generate("<Button-1>", x=x+width//2, y=y+height//2)
            self.pump()
            self.assertFalse(old.winfo_exists())
            self.assertFalse(old.traces)
            self.assertFalse(old.geometry_bindings)
            self.assertTrue(self.app.preferences_dialog.surface.winfo_ismapped())

    def test_selected_status_and_last_column_icons_survive_theme_changes(self):
        for theme in ("dark", "light", "dark"):
            self.app.set_preference("theme", theme)
            self.pump()
            for column, icon in (("status", "progress"), ("properties", "alert")):
                self.assertEqual(tuple(map(str, self.app.heading_icons[column].cget("image"))),
                                 (str(self.app.icons[icon]),))

    def test_stop_action_preserves_job_and_files_and_journal_has_row_boundaries(self):
        import threading
        source = Path(self.folder.name)/"keep-partial.bin"
        source.write_bytes(b"keep this file")
        row = self.app.store.create("https://example.com/keep-partial.bin", source.parent, source.name)
        row_id = row["id"]
        self.app.store.update(row_id, state="downloading")
        stop = threading.Event()
        with patch.dict(self.app.manager.active, {row_id: stop}):
            self.pump(.6)
            button = self.app.row_more_buttons[row_id]
            self.assertEqual(button.label, "Dừng")
            self.assertEqual(str(button.cget("state")), "normal")
            with patch.object(self.app.manager, "pause", wraps=self.app.manager.pause) as pause:
                button.invoke()
                pause.assert_called_once_with(row_id)
            self.assertTrue(stop.is_set())
            self.assertTrue(source.exists())
            self.assertEqual(self.app.store.get(row_id)["id"], row_id)
        self.app.store.update(row_id, state="paused")
        self.pump(.6)
        self.assertEqual(button.label, "Xóa")
        line = self.app.row_separators[row_id]
        self.assertEqual(line.winfo_height(), 1)
        self.assertGreater(line.winfo_width(), self.app.table.winfo_width()-8)
        self.app.delete_job(row_id, False)
        self.pump(.6)
        self.assertNotIn(row_id, self.app.row_separators)
        self.assertTrue(source.exists())

    def test_theme_and_navigation_redraw_native_surfaces_after_layout(self):
        from tkinter import ttk
        with patch("hngoos_dm.ui_preferences.redraw_window") as redraw:
            page = self.app.open_preferences()
            self.pump()
            redraw.reset_mock()
            painted = []
            redraw.side_effect = lambda window: painted.append((
                ttk.Style(window).lookup("TFrame", "background"), bool(page.winfo_ismapped())))
            for theme, expected in (("light", "#f6f6f6"), ("dark", "#121212"), ("light", "#f6f6f6")):
                self.app.set_preference("theme", theme)
                self.pump()
                self.assertEqual(painted[-1], (expected, True))
            self.app.open_information()
            self.pump()
            self.assertEqual(painted[-1], ("#f6f6f6", False))

    def test_journal_colors_are_per_cell_and_survive_theme_language_and_missing_file(self):
        from hngoos_dm.ui_preferences import SEMANTIC_COLORS
        source = Path(self.folder.name)/"color-fixture.bin"
        source.write_bytes(b"fixture")
        row = self.app.store.create("https://example.com/color-fixture.bin", source.parent, source.name)
        row_id = row["id"]
        self.app.store.update(row_id, state="complete", output=str(source), safety_check={"status": "clean"})
        self.pump(.6)
        for theme in ("light", "dark"):
            for language in ("en", "vi"):
                self.app.set_preference("theme", theme)
                self.app.set_preference("language", language)
                self.pump(.6)
                colors = SEMANTIC_COLORS[theme]
                self.assertEqual(str(self.app.row_cell_labels[row_id, "status"]["foreground"]), colors["safe"])
                self.assertEqual(str(self.app.row_cell_labels[row_id, "check"]["foreground"]), colors["safe"])
                for status, level in (("risk", "risk"), ("threat", "risk"), ("danger", "danger"), ("error", "risk")):
                    self.app.store.update(row_id, safety_check={"status": status})
                    self.app.update_safety_buttons()
                    self.assertEqual(str(self.app.row_cell_labels[row_id, "check"]["foreground"]), colors[level])
                self.app.store.update(row_id, safety_check={"status": "clean"})
        source.unlink()
        self.pump(.6)
        self.assertTrue(self.app.table.exists(row_id))
        label = self.app.row_cell_labels[row_id, "status"]
        self.assertEqual(str(label["foreground"]), SEMANTIC_COLORS["dark"]["danger"])
        self.assertEqual(label["text"], "Tệp đã bị xóa")

    def test_journal_speed_colors_use_red_yellow_green_at_thresholds(self):
        from hngoos_dm.ui_preferences import PALETTES, SEMANTIC_COLORS
        row = self.app.store.create("https://example.com/speed.bin", self.folder.name, "speed.bin")
        row_id = row["id"]
        self.pump(.6)
        for theme in ("light", "dark"):
            self.app.set_preference("theme", theme)
            for speed, level in ((1, "danger"), (1024**2-1, "danger"), (1024**2, "risk"),
                                (10*1024**2-1, "risk"), (10*1024**2, "safe")):
                self.app.store.update(row_id, state="downloading", speed=speed)
                self.app.update_safety_buttons()
                self.assertEqual(str(self.app.row_cell_labels[row_id, "speed"]["foreground"]),
                                 SEMANTIC_COLORS[theme][level])
            self.app.store.update(row_id, state="paused", speed=0)
            self.app.update_safety_buttons()
            self.assertEqual(str(self.app.row_cell_labels[row_id, "speed"]["foreground"]), PALETTES[theme][3])

    def test_browser_download_restores_home_before_asking_where_to_save(self):
        page = self.app.open_preferences()
        self.pump()
        self.root.iconify()
        self.app.store.enqueue("from-browser", {"kind": "file", "url": "https://example.com/fixture.iso",
            "filename": "fixture.iso", "origin": "browser"})
        def choose(**kwargs):
            self.assertNotEqual(self.root.state(), "iconic")
            self.assertFalse(self.app.page_stack)
            self.assertIs(kwargs.get("parent"), self.root)
            self.assertTrue(self.root.attributes("-topmost"))
            return ""
        with patch("hngoos_dm.app.filedialog.asksaveasfilename", side_effect=choose) as prompt:
            self.root.after_cancel(self.app.refresh_id)
            self.app.refresh()
            prompt.assert_called_once()
        self.assertFalse(self.root.attributes("-topmost"))
        self.pump()
        self.assertFalse(page.winfo_ismapped())
        self.assertTrue(self.app.tabs.winfo_ismapped())

    def test_logo_coalesces_queued_clicks_without_replaying_navigation(self):
        with patch.object(self.app, "open_preferences", wraps=self.app.open_preferences) as opened:
            for i in range(20):
                self.app.brand_label.event_generate("<Button-1>", when="tail", time=1000+i*20)
            deadline = time.monotonic()+2
            while not (getattr(self.app, "preferences_dialog", None)
                       and self.app.preferences_dialog.winfo_ismapped()) and time.monotonic() < deadline:
                self.pump(.05)
            self.assertEqual(opened.call_count, 1)
            self.assertTrue(self.app.preferences_dialog.winfo_ismapped())
            self.pump(.3)
            self.assertTrue(self.app.preferences_dialog.winfo_ismapped())
        self.app.brand_label.event_generate("<Button-1>")
        self.pump()
        self.assertTrue(self.app.tabs.winfo_ismapped())

    def test_navigation_reuses_settings_without_retheming_or_collapsing_hidden_inputs(self):
        # Keep the same viewport across navigation. Hosted macOS can clamp a
        # window wider than its 1024px display only after switching pages.
        width = min(1120, self.root.winfo_screenwidth()-40)
        height = min(720, self.root.winfo_screenheight()-80)
        self.root.minsize(width, height)
        self.root.geometry(f"{width}x{height}")
        self.pump()
        initial_width = self.app.empty_panel.winfo_reqwidth()
        initial_window = (self.root.winfo_width(), self.root.winfo_height())
        page = self.app.open_preferences()
        self.pump()
        self.assertEqual(self.app.empty_panel.winfo_reqwidth(), initial_width,
                         (initial_window, (self.root.winfo_width(), self.root.winfo_height()),
                          self.app.header_logo.width()))
        with patch.object(self.app, "apply_preferences", wraps=self.app.apply_preferences) as present:
            for _ in range(3):
                self.app.open_information()
                self.pump()
                self.assertFalse(page.winfo_ismapped())
                self.assertTrue(self.app.tabs.winfo_ismapped())
                self.app.open_information()
                self.pump()
                self.assertIs(self.app.preferences_dialog, page)
                self.assertTrue(page.winfo_ismapped())
            present.assert_not_called()

    def test_update_has_one_centered_status_from_current_version_through_result(self):
        import threading

        from hngoos_dm import __version__
        self.app.check_update()
        dialog = self.app.update_dialog
        self.pump()
        self.assertIn(__version__, dialog.status.get())
        self.assertEqual(dialog.status_label.place_info()["rely"], "0.5")
        release = threading.Event()
        with patch("hngoos_dm.update_ui.check_update", side_effect=lambda: (release.wait(2), None)[1]):
            dialog.primary.invoke()
            self.assertEqual(dialog.status.get(), "Đang kiểm tra cập nhật…")
            release.set()
            self.pump(.4)
        self.assertEqual(dialog.status.get(), "Không có bản cập nhật mới.")
        dialog.close()

    def test_media_options_use_only_source_formats_and_quality_and_submit_native_stream(self):
        from hngoos_dm.download_ui import DownloadEditor
        self.app.url.set("https://youtu.be/source")
        editor = self.app.download_editor = DownloadEditor(self.app, {
            "original": self.app.url.get(), "url": self.app.url.get(), "kind": "media", "filename": "Source.mp4",
            "formats": [
                {"format_id": "22", "ext": "mp4", "height": 720, "vcodec": "avc1", "acodec": "aac"},
                {"format_id": "140", "ext": "m4a", "vcodec": "none", "acodec": "aac", "abr": 128},
            ]})
        editor.pack(fill="both", expand=True)
        self.pump()
        self.assertEqual(set(editor.format_choices.buttons), {"MP4", "M4A", "MP3"})
        self.assertEqual(set(editor.quality_choices.buttons), {"720"})
        self.assertEqual(editor.format_id.get(), "22")
        editor.format_choices.buttons["M4A"].invoke()
        self.assertEqual(set(editor.quality_choices.buttons), {"128"})
        self.assertEqual(editor.format_id.get(), "140")
        with patch.object(self.app, "add"):
            editor.confirm()
        self.assertEqual(self.app.media_format.get(), "140")

    def test_video_selection_keeps_available_audio_across_source_containers(self):
        from hngoos_dm.download_ui import DownloadEditor
        from hngoos_dm.media import MediaOptions, ydl_options
        self.app.url.set("https://youtu.be/source")
        formats = [
            {"format_id": "video", "ext": "mp4", "height": 1080, "vcodec": "avc1", "acodec": "none"},
            {"format_id": "audio-low", "ext": "webm", "vcodec": "none", "acodec": "opus", "abr": 64},
            {"format_id": "audio", "ext": "webm", "vcodec": "none", "acodec": "opus", "abr": 128},
        ]
        editor = self.app.download_editor = DownloadEditor(self.app, {
            "original": self.app.url.get(), "url": self.app.url.get(), "kind": "media",
            "filename": "Source.mp4", "formats": formats})
        editor.pack(fill="both", expand=True)
        self.assertEqual(editor.format_id.get(), "video+audio")
        settings = ydl_options("out", MediaOptions(format_id=editor.format_id.get()), "ffmpeg")
        self.assertEqual(settings["format"], "video+audio")
        self.assertEqual(settings["merge_output_format"], "mp4")
        formats.append({"format_id": "compatible-audio", "ext": "m4a", "vcodec": "none", "acodec": "aac", "abr": 96})
        editor.source_formats.append(formats[-1])
        editor.select_source_format()
        self.assertEqual(editor.format_id.get(), "video+compatible-audio")

    def test_theme_switch_does_not_flush_half_updated_custom_controls(self):
        from hngoos_dm.rounded import RoundedButton, RoundedField, RoundedScrollbar
        self.app.open_preferences()
        self.pump()
        original = tk.Misc.update_idletasks

        def flush(widget):
            def check(parent):
                for child in parent.winfo_children():
                    if isinstance(child, (RoundedButton, RoundedField, RoundedScrollbar)):
                        self.assertEqual(child.theme, self.app.theme, str(child))
                    check(child)
            check(self.root)
            return original(widget)

        for theme in ("light", "dark", "light", "dark"):
            with patch.object(tk.Misc, "update_idletasks", flush):
                self.app.preference_theme.select(theme)
            self.pump()

    def test_preferences_choices_follow_locale_without_clipping_proxy_labels(self):
        self.app.set_preference("language", "en")
        self.app.open_preferences()
        self.pump()
        for language, theme in (("vi", "dark"), ("en", "light"), ("vi", "light")):
            self.app.set_preference("language", language)
            self.app.set_preference("theme", theme)
            self.pump()
            self.assertEqual(self.app.preference_language.variable.get(), language)
            self.assertEqual(self.app.preference_theme.variable.get(), theme)
            for button in self.app.proxy_choices.buttons.values():
                self.assertGreaterEqual(button.winfo_width(),
                    button.label_font.measure(self.app.locale.text(button.label))+20)

    def test_webm_does_not_silently_drop_incompatible_audio_or_start_a_bad_merge(self):
        from hngoos_dm.download_ui import DownloadEditor
        self.app.url.set("https://youtu.be/source")
        editor = self.app.download_editor = DownloadEditor(self.app, {
            "original": self.app.url.get(), "url": self.app.url.get(), "kind": "media",
            "filename": "Source.webm", "formats": [
                {"format_id": "video", "ext": "webm", "height": 1080, "vcodec": "vp9", "acodec": "none"},
                {"format_id": "audio", "ext": "m4a", "vcodec": "none", "acodec": "aac", "abr": 128},
            ]})
        editor.pack(fill="both", expand=True)
        self.assertTrue(editor.error.get())
        with patch.object(self.app, "add") as add:
            editor.confirm()
            add.assert_not_called()
        editor.source_formats.append({"format_id": "opus", "ext": "webm", "vcodec": "none",
                                      "acodec": "opus", "abr": 96})
        editor.select_source_format()
        self.assertEqual(editor.format_id.get(), "video+opus")
        self.assertEqual(editor.error.get(), "")

    def test_centered_cards_close_only_on_outside_click_and_do_not_trigger_background_actions(self):
        about = self.app.open_about()
        self.pump()
        self.root.event_generate("<Button-1>", x=about.winfo_x()+40, y=about.winfo_y()+40)
        self.pump()
        self.assertTrue(about.winfo_exists())
        self.root.event_generate("<Button-1>", x=8, y=8)
        self.pump()
        self.assertFalse(about.winfo_exists())
        self.assertIsNone(self.app.modal_card)
        self.app.check_update()
        update = self.app.update_dialog
        self.pump()
        self.root.event_generate("<Button-1>", x=8, y=8)
        self.pump()
        self.assertTrue(update.closed)
        self.assertFalse(update.window.winfo_exists())

    def test_system_options_share_one_section_without_explanatory_captions(self):
        from tkinter import ttk
        page = self.app.open_preferences()
        def widgets(parent):
            for child in parent.winfo_children():
                yield child
                yield from widgets(child)
        for section in ("Chung", "Trình duyệt", "Mạng"):
            self.assertFalse(any(isinstance(w, ttk.Checkbutton) for w in widgets(page.sections[section])))
        flags = [w for w in widgets(page.sections["Hệ thống"]) if isinstance(w, ttk.Checkbutton)]
        self.assertEqual(len(flags), 5)
        self.assertEqual(len([w for w in widgets(page.sections["Tải xuống"]) if isinstance(w, ttk.Checkbutton)]), 7)
        self.assertNotIn("An toàn", page.sections)
        self.assertNotIn("Nâng cao", page.sections)
        labels = [str(w.cget("text")) for w in widgets(page) if isinstance(w, ttk.Label)]
        self.assertNotIn("Thiết lập", labels)
        for removed in ("Ví dụ:", "Kiểm tra dấu hiệu rủi ro", "Bấm Kiểm tra", "Tra cứu chỉ gửi", "Khôi phục tệp cách ly:"):
            self.assertFalse(any(removed in label for label in labels), removed)

    def test_file_options_are_visible_but_only_compatible_controls_can_be_used(self):
        from hngoos_dm.download_ui import DownloadEditor
        self.pump()
        empty = self.app.download_placeholder
        self.assertFalse(self.app.url_panel.winfo_ismapped())
        self.assertEqual(set(empty.format_choices.buttons), {"Original"})
        empty.format_choices.buttons["Original"].invoke()
        self.assertEqual(empty.format.get(), "Original")
        self.assertTrue(all(str(button.cget("state")) == "disabled" for button in empty.quality_choices.buttons.values()))
        self.app.url.set("https://example.com/document.pdf")
        editor = self.app.download_editor = DownloadEditor(self.app, {
            "original": self.app.url.get(), "url": self.app.url.get(), "kind": "file", "filename": "document.pdf"})
        editor.pack(fill="both", expand=True)
        self.pump()
        self.assertFalse(self.app.url_panel.winfo_ismapped())
        self.assertEqual(str(editor.format_choices.buttons["Original"].cget("state")), "normal")
        self.assertEqual(set(editor.format_choices.buttons), {"Original"})
        self.assertEqual(editor.filename.get(), "document.pdf")
        self.assertEqual(editor.format.get(), "Original")
        self.app.url.set("https://example.com/new.pdf")
        self.pump()
        self.assertIsNone(self.app.download_editor)
        self.assertFalse(self.app.url_panel.winfo_ismapped())

    def test_header_has_no_navigation_and_inputs_remain_readable(self):
        self.assertFalse(hasattr(self.app, "navigation_buttons"))
        self.assertFalse(hasattr(self.app, "navigation_canvas"))
        self.assertEqual(self.app.url_entry.text_font.cget("size"), 13)
        self.assertEqual(self.app.destination_entry.text_font.cget("size"), 13)
        self.assertFalse(hasattr(self.app, "account_client"))

    def test_report_action_opens_github_from_preferences_contact(self):
        page = self.app.open_preferences()
        self.pump()
        self.assertEqual(self.app.preference_report_button.master.master, page.sections["Hệ thống"])
        before = tuple(self.root.winfo_children())
        with patch("hngoos_dm.app.webbrowser.open") as browser:
            self.app.preference_report_button.invoke()
            browser.assert_called_once_with(
                "https://github.com/hngoos/hngoos-download-manager/issues/new?labels=bug")
        self.assertEqual(tuple(self.root.winfo_children()), before)
        self.assertFalse(hasattr(self.app, "bug_report_dialog"))

    def test_browser_panel_has_only_two_autosaving_options_and_detects_installed_browsers(self):
        from tkinter import ttk

        from hngoos_dm.rounded import RoundedField
        executable = Path(self.folder.name)/"msedge.exe"
        executable.touch()
        with patch("hngoos_dm.browser.find_browser", side_effect=lambda name: executable if name == "edge" else None):
            page = self.app.open_preferences()
        section = page.sections["Trình duyệt"]
        def widgets(parent):
            for child in parent.winfo_children():
                yield child
                yield from widgets(child)
        controls = list(widgets(section))
        self.assertEqual(len([item for item in controls if isinstance(item, ttk.Checkbutton)]), 0)
        self.assertFalse(any(isinstance(item, RoundedField) for item in controls))
        self.assertEqual(set(self.app.browser_install_buttons), {"chrome", "edge", "brave", "coccoc", "opera", "opera-gx", "vivaldi"})
        edge, chrome = self.app.browser_install_buttons["edge"], self.app.browser_install_buttons["chrome"]
        self.assertEqual(str(edge.cget("state")), "normal")
        self.assertEqual(str(chrome.cget("state")), "disabled")
        self.assertFalse(edge.primary)
        self.assertTrue(edge.flat)
        self.assertEqual(edge.label, "")
        self.assertFalse(chrome.primary)
        self.assertIsNotNone(edge.image)
        self.assertEqual((edge.image.width(), edge.image.height()), (48, 48))
        self.assertIsNotNone(chrome.image)
        self.assertNotEqual(str(edge.image), str(chrome.image))
        self.app.browser_capture_button.invoke()
        self.assertTrue(self.app.store.setting("browser_preferences")["capture"])
        self.app.browser_auto_start_button.invoke()
        self.assertTrue(self.app.store.setting("browser_preferences")["auto_start"])
        with patch("hngoos_dm.information_ui.browser_dialog") as launch:
            chrome.invoke()
            launch.assert_not_called()
            edge.invoke()
            launch.assert_called_once_with(self.app, "edge")
        page.destroy()

    def test_proxy_selection_saves_valid_policy_and_rejects_invalid_endpoint(self):
        page = self.app.open_preferences()
        self.app.proxy_mode.set("manual")
        self.app.proxy_url.set("http://localhost:8123")
        self.assertFalse(hasattr(self.app, "proxy_apply_button"))
        self.assertEqual(self.app.store.setting("proxy"), {"mode": "manual", "url": "http://localhost:8123"})
        self.app.proxy_url.set("file:///private")
        self.assertEqual(self.app.store.setting("proxy")["url"], "http://localhost:8123")
        for mode in ("system", "direct"):
            self.app.proxy_choices.select(mode)
            self.assertEqual(self.app.store.setting("proxy"), {"mode": mode, "url": ""})
        page.destroy()

    def test_journal_keeps_deleted_files_and_name_opens_only_the_containing_folder(self):
        source = Path(self.folder.name)/"journal.pdf"
        source.write_bytes(b"document")
        job = self.app.store.create("https://example.com/journal.pdf", source.parent, source.name)
        self.app.store.update(job["id"], state="complete", output=str(source))
        self.app.set_preference("language", "en")
        self.pump(.6)
        self.assertEqual(self.app.table.set(job["id"], "status"), "Done")
        x,y,w,h = self.app.table.bbox(job["id"], "name")
        with patch("hngoos_dm.app.open_path") as open_folder:
            self.app.table.event_generate("<Button-1>", x=x+12, y=y+h//2)
            open_folder.assert_called_once_with(source.parent)
            open_folder.reset_mock()
            self.app.table.event_generate("<Button-1>", x=x+w-12, y=y+h//2)
            open_folder.assert_not_called()
        source.unlink()
        self.pump(1.3)
        self.assertTrue(self.app.table.exists(job["id"]))
        self.assertEqual(self.app.table.set(job["id"], "status"), "File deleted")
        self.assertEqual(len(self.app.store.all()), 1)
        self.app.set_preference("language", "vi")
        self.pump(.6)
        self.assertEqual(self.app.table.set(job["id"], "status"), "Tệp đã bị xóa")
        source.write_bytes(b"restored")
        self.pump(.6)
        self.assertEqual(self.app.table.set(job["id"], "status"), "Hoàn tất")

    def test_system_actions_are_rounded_on_one_row(self):
        self.app.open_preferences()
        self.pump()
        check, reset = self.app.preference_update_button, self.app.preference_reset_button
        report = self.app.preference_report_button
        self.assertEqual(report.master, check.master)
        self.assertEqual(report.winfo_y(), check.winfo_y())
        self.assertLess(report.winfo_x(), check.winfo_x())
        self.assertEqual(check.master, reset.master)
        self.assertEqual(check.winfo_y(), reset.winfo_y())
        self.assertGreater(reset.winfo_x(), check.winfo_x())
        self.app.set_preference("language", "en")
        self.assertEqual(reset.translate(reset.label), "Reset to default")

    def test_download_and_update_checkboxes_persist_real_preferences(self):
        page = self.app.open_preferences()
        for key in ("retry_failed", "auto_install_updates", "auto_check_updates"):
            variable, button = self.app.preference_flags[key]
            before = variable.get()
            button.invoke()
            self.assertEqual(self.app.store.setting(key), not before)
        self.assertIn("disabled", self.app.preference_flags["auto_install_updates"][1].state())
        page.destroy()

    def test_reset_keeps_files_jobs_credentials_and_extension_registration(self):
        path = Path(self.folder.name)/"preserve.txt"
        path.write_text("keep me")
        job = self.app.store.create("https://example.com/preserve.txt", path.parent, path.name)
        self.app.store.set_setting("virustotal_api_key", "private-fixture")
        self.app.store.set_setting("extension_id", "a"*32)
        self.app.store.set_setting("remove_completed", True)
        self.app.store.set_setting("browser_preferences", {"capture": True, "skip_domains": ["example.com"]})
        self.app.set_preference("theme", "light")
        self.app.open_preferences()
        with patch("hngoos_dm.app.messagebox.askyesno", return_value=False):
            self.app.reset_preferences()
        self.assertTrue(self.app.store.setting("remove_completed"))
        with patch("hngoos_dm.app.messagebox.askyesno", return_value=True):
            self.app.reset_preferences()
        self.pump()
        self.assertEqual(self.app.theme, "dark")
        self.assertFalse(self.app.store.setting("remove_completed"))
        self.assertFalse(self.app.store.setting("browser_preferences")["capture"])
        self.assertEqual(self.app.store.get(job["id"])["filename"], "preserve.txt")
        self.assertEqual(path.read_text(), "keep me")
        self.assertEqual(self.app.store.setting("virustotal_api_key"), "private-fixture")
        self.assertEqual(self.app.store.setting("extension_id"), "a"*32)

    def test_preferences_do_not_show_removed_captions_or_manual_video_update(self):
        from tkinter import ttk
        self.app.store.set_setting("automatic_update_status", "Bạn đang dùng phiên bản mới nhất.")
        page = self.app.open_preferences()
        def texts(parent):
            for widget in parent.winfo_children():
                if isinstance(widget, (ttk.Label, ttk.Button)):
                    variable = widget.cget("textvariable")
                    yield str(self.root.getvar(str(variable))) if variable else str(widget.cget("text"))
                yield from texts(widget)
        labels = list(texts(page))
        self.assertEqual(self.app.preference_update_button.label, "Kiểm tra cập nhật")
        for removed in ("Chỉ xóa mục", "Kiểm tra mỗi", "Bạn đang dùng", "Cập nhật bộ tải video", "Sửa lỗi nhận diện"):
            self.assertFalse(any(removed in label for label in labels), removed)
        page.destroy()

    def test_media_tool_update_failure_is_silent_and_releases_busy_state(self):
        with patch("hngoos_dm.toolchain.update_ytdlp", side_effect=ValueError("offline")) as updater, \
                patch("hngoos_dm.app.messagebox.showinfo") as notice:
            self.app.update_ytdlp()
            self.app.background_threads[-1].join(3)
            deadline = time.monotonic()+3
            while self.app.media_tool_busy and time.monotonic() < deadline:
                self.pump(.05)
            updater.assert_called_once()
        self.assertFalse(self.app.media_tool_busy, {
            "events": self.app.events.qsize(), "errors": self.errors,
            "workers": [(thread.name, thread.is_alive()) for thread in self.app.background_threads],
            "next_check_in": self.app.automatic_video_updates.next_check-time.time(),
            "last_error": self.app.store.setting("video_tool_update_error"),
        })
        self.assertIsNone(self.app.store.setting("last_video_tool_check"))
        notice.assert_not_called()

    def test_media_tool_update_is_single_flight_and_persists_success(self):
        import threading
        started, release = threading.Event(), threading.Event()
        def update():
            started.set()
            release.wait(5)
            return "2026.11.06"
        with patch("hngoos_dm.toolchain.update_ytdlp", side_effect=update) as updater:
            try:
                self.app.update_ytdlp()
                self.assertTrue(started.wait(2))
                self.app.update_ytdlp()
                self.pump()
                self.assertTrue(self.app.media_tool_busy)
                updater.assert_called_once()
            finally:
                release.set()
            self.app.background_threads[-1].join(3)
            deadline = time.monotonic()+3
            while self.app.media_tool_busy and time.monotonic() < deadline:
                self.pump(.05)
        self.assertFalse(self.app.media_tool_busy)
        self.assertEqual(self.app.store.setting("video_tool_version"), "2026.11.06")
        self.assertGreater(self.app.store.setting("last_video_tool_check"), time.time()-5)

    def test_about_and_update_are_small_centered_cards_without_close_buttons(self):
        preferences = self.app.open_preferences()
        self.pump()
        with patch("hngoos_dm.update_ui.check_update", return_value=None):
            self.app.check_update()
            self.pump()
            update = self.app.update_dialog
            self.assertEqual(update.window.winfo_manager(), "place")
            self.assertTrue(preferences.winfo_ismapped())
            self.assertLess(update.window.winfo_width(), self.root.winfo_width()*.6)
            self.assertLess(update.window.winfo_height(), self.root.winfo_height()*.6)
            self.assertLess(abs(update.window.winfo_rootx()+update.window.winfo_width()/2
                                - self.root.winfo_rootx()-self.root.winfo_width()/2), 2)
            self.assertLess(abs(update.window.winfo_rooty()+update.window.winfo_height()/2
                                - self.root.winfo_rooty()-self.root.winfo_height()/2), 2)
            update.window.dismiss()
            self.pump()
            self.assertTrue(update.closed)
            self.assertFalse(update.window.winfo_exists())
        about = self.app.open_about()
        self.pump()
        self.assertEqual(about.winfo_manager(), "place")
        self.assertTrue(preferences.winfo_ismapped())
        self.assertLess(about.winfo_height(), self.root.winfo_height()*.6)
        self.assertIs(self.app.open_about(), about)
        self.assertFalse(any(isinstance(w, tk.Toplevel) for w in self.root.winfo_children()))
        self.app.set_preference("theme", "light")
        self.app.set_preference("language", "en")
        self.pump()
        self.assertEqual(about.theme, "light")
        self.assertFalse(hasattr(about, "close_button"))
        about.dismiss()
        self.pump()
        self.assertFalse(about.winfo_exists())
        self.assertIs(self.app.page_stack[-1], preferences)
        preferences.destroy()

    def test_about_is_brief_has_contact_and_neither_card_has_scroll_or_progress(self):
        from tkinter import ttk

        from hngoos_dm import __version__
        from hngoos_dm.rounded import RoundedButton, RoundedScrollbar
        def widgets(parent):
            for child in parent.winfo_children():
                yield child
                yield from widgets(child)
        about = self.app.open_about()
        self.pump()
        controls = list(widgets(about))
        labels = [str(w.cget("text")) for w in controls if isinstance(w, ttk.Label)]
        self.assertTrue(any(__version__ in label for label in labels))
        self.assertIn("Gmail", labels)
        self.assertFalse(any(isinstance(w, (RoundedScrollbar, ttk.Scrollbar, ttk.Progressbar)) for w in controls))
        self.assertFalse(any(isinstance(w, RoundedButton) and "cập nhật" in w.label for w in controls))
        self.assertFalse(hasattr(about, "close_button"))
        about.dismiss()
        with patch("hngoos_dm.update_ui.check_update", return_value={"version": "9.9.9"}) as check, \
                patch("hngoos_dm.update_ui.select_installer", return_value={"size": 1024}):
            self.app.check_update()
            dialog = self.app.update_dialog
            self.pump()
            check.assert_not_called()
            self.assertFalse(any(isinstance(w, (RoundedScrollbar, ttk.Scrollbar, ttk.Progressbar))
                                 for w in widgets(dialog.window)))
            dialog.primary.invoke()
            self.pump()
            self.assertIn("9.9.9", dialog.status.get())
            self.assertEqual(dialog.primary.label, "Tải bản cập nhật")
            self.assertFalse(dialog.busy)
            self.assertGreater(dialog.primary.winfo_rooty(), dialog.window.winfo_rooty()+dialog.window.winfo_height()*.65)
            dialog.window.dismiss()

    def test_browser_logo_opens_only_in_app_guide_with_bundled_zip(self):
        with patch("hngoos_dm.browser.find_browser", return_value=Path(self.folder.name)/"msedge.exe"):
            page = self.app.open_preferences()
        self.pump()
        with patch("hngoos_dm.browser.open_extensions") as first_launch, \
                patch("hngoos_dm.browser.connect_extension") as connect, \
                patch("hngoos_dm.platforms.open_path") as explorer:
            self.app.browser_install_buttons["edge"].invoke()
            self.pump(.6)
            first_launch.assert_not_called()
            explorer.assert_not_called()
            connect.assert_not_called()
        guide = self.app.browser_install_page
        self.assertEqual(self.app.page_stack, [page, guide])
        self.assertEqual(guide.browser_id, "edge")
        page.event_generate("<Configure>")
        self.pump()
        self.assertFalse(page.winfo_ismapped())
        self.assertTrue(guide.winfo_ismapped())
        self.assertGreaterEqual(guide.winfo_rooty(), self.app.header.winfo_rooty()+self.app.header.winfo_height())
        self.assertFalse(hasattr(guide, "download_zip_button"))
        self.assertFalse(hasattr(guide, "illustration"))
        self.assertEqual(guide.extension_link.cget("text"), "edge://extensions")
        self.assertFalse(hasattr(guide, "back_button"))
        guide.destroy()
        self.pump()
        self.assertTrue(page.winfo_ismapped())
        page.destroy()

    def test_extension_guide_uses_bundled_zip_and_connects_chosen_folder(self):
        from hngoos_dm.information_ui import browser_dialog
        target = Path(self.folder.name)/"HDM-Browser-Extension.zip"
        with patch("hngoos_dm.extension_package.bundled_extension_path", return_value=target), \
                patch("hngoos_dm.extension_package.prepare_extension") as prepare, \
                patch("tkinter.filedialog.asksaveasfilename") as save, \
                patch("hngoos_dm.browser.open_extensions") as launch:
            guide = browser_dialog(self.app, "opera-gx")
            self.pump()
            self.assertEqual(guide.archive_path, target)
            self.assertIn(str(target), guide.archive_label.cget("text"))
            prepare.assert_not_called()
            save.assert_not_called()
            launch.assert_not_called()
        unpacked = Path(__file__).resolve().parents[1]/"browser-extension"
        with patch("tkinter.filedialog.askdirectory", return_value=str(unpacked)), \
                patch("hngoos_dm.browser.connect_extension") as connect:
            guide.connect_button.invoke()
            connect.assert_called_once_with(unpacked, self.app.data_dir)
        for language, prefix, developer in (("en", "Step 1:", "Developer mode"),
                                             ("vi", "B1:", "Chế độ nhà phát triển")):
            self.app.set_preference("language", language)
            self.pump()
            self.assertTrue(guide.step_labels[0].cget("text").startswith(prefix))
            self.assertIn(developer, guide.step_labels[1].cget("text"))
            self.assertIn("HDM-Browser-Extension.zip", guide.step_labels[2].cget("text"))
            self.assertEqual(guide.extension_link.cget("text"), "opera://extensions")

    def test_extension_guide_steps_and_link_fit_without_illustration_or_scrolling(self):
        from hngoos_dm.information_ui import browser_dialog
        with patch("hngoos_dm.browser.open_extensions") as launch:
            guide = browser_dialog(self.app, "opera-gx")
            for geometry in ("1120x720", "1920x1080"):
                self.root.geometry(geometry)
                self.pump()
                self.assertFalse(hasattr(guide, "illustration"))
                self.assertFalse(hasattr(guide, "download_zip_button"))
                self.assertLessEqual(guide.step_labels[0].winfo_rooty(), guide.extension_link.winfo_rooty())
                self.assertLess(guide.extension_link.winfo_rooty(), guide.step_labels[1].winfo_rooty())
                self.assertLessEqual(guide.step_labels[-1].winfo_rooty()+guide.step_labels[-1].winfo_height(),
                                     self.root.winfo_rooty()+self.root.winfo_height())
            launch.assert_not_called()
            guide.extension_link.event_generate("<Button-1>")
            launch.assert_called_once_with("opera-gx")
            launch.reset_mock()
            guide.extension_link.focus_force()
            self.pump()
            guide.extension_link.event_generate("<Return>")
            launch.assert_called_once_with("opera-gx")

    def test_extension_link_failure_stays_in_guide_and_reports_problem(self):
        from hngoos_dm.information_ui import browser_dialog
        guide = browser_dialog(self.app, "edge")
        self.pump()
        with patch("hngoos_dm.browser.open_extensions", side_effect=OSError("Browser unavailable")):
            guide.extension_link.event_generate("<Button-1>")
        self.assertIn("Browser unavailable", guide.status.get())
        self.assertIs(self.app.page_stack[-1], guide)

    def test_url_input_and_native_text_align_with_the_caption(self):
        label = next(w for w in self.app.url_form.winfo_children() if w != self.app.url_entry)
        self.app.url.set("https://example.com/report.pdf")
        self.pump()
        field = self.app.url_entry
        label_center = label.winfo_rooty()+label.winfo_height()/2
        control_center = field.control.winfo_rooty()+field.control.winfo_height()/2
        self.assertLessEqual(abs(label_center-control_center), 1)
        self.assertTrue(any(field.type(item) == "polygon" for item in field.find_all()))
        self.assertFalse(any(field.type(item) == "line" for item in field.find_all()))
        self.assertEqual(field.get(), "https://example.com/report.pdf")

    def test_preferences_are_one_static_page_with_two_columns_and_no_navigation(self):
        from hngoos_dm.rounded import RoundedScrollbar
        for geometry in ("1120x720", "1920x1080"):
            self.root.geometry(geometry)
            page = self.app.open_preferences()
            self.pump()
            self.assertFalse(hasattr(self.app, "navigation_canvas"))
            self.assertFalse(hasattr(page, "scroller"))
            self.assertFalse(hasattr(page, "section_buttons"))
            left, right = page.sections["Tải xuống"], page.sections["Chung"]
            self.assertGreater(left.winfo_rootx(), right.winfo_rootx())
            self.assertLess(left.winfo_rooty(), self.app.brand_label.winfo_rooty()+self.root.winfo_height()*.08)
            self.assertLess(left.winfo_rootx()-right.winfo_rootx(), max(600, self.root.winfo_width()*.4))
            self.assertEqual(left.master, page.sections["Hệ thống"].master)
            self.assertEqual(right.master, page.sections["Trình duyệt"].master)
            self.assertEqual(right.master, page.sections["Mạng"].master)
            self.assertEqual(right.master, page.sections["Liên hệ"].master)
            self.app.proxy_mode.set("manual")
            self.pump()
            def widgets(parent):
                for child in parent.winfo_children():
                    yield child
                    yield from widgets(child)
            self.assertFalse(any(isinstance(w, RoundedScrollbar) for w in widgets(page)))
            for section in page.sections.values():
                self.assertTrue(section.winfo_ismapped())
                self.assertLessEqual(section.winfo_rooty()+section.winfo_height(),
                                     self.root.winfo_rooty()+self.root.winfo_height())
            self.app.open_information()
            self.pump()
            self.assertFalse(self.app.page_stack)

    def test_media_card_is_hidden_until_a_video_audio_or_image_source_is_detected(self):
        from hngoos_dm.download_ui import DownloadEditor
        self.pump()
        self.assertFalse(self.app.url_panel.winfo_ismapped())
        for filename, shown in (("report.pdf", False), ("setup.exe", False), ("archive.zip", False),
                                ("photo.png", True), ("audio.mp3", True), ("video.mp4", True)):
            self.app.url.set("https://example.com/"+filename)
            editor = self.app.download_editor = DownloadEditor(self.app, {
                "original": self.app.url.get(), "url": self.app.url.get(), "kind": "file", "filename": filename})
            editor.pack(fill="both", expand=True)
            self.pump()
            self.assertEqual(self.app.url_panel.winfo_ismapped(), shown, filename)
            self.app.cancel_download()
            self.pump()
            self.assertFalse(self.app.url_panel.winfo_ismapped())

    def test_info_menu_has_exactly_three_groups(self):
        from hngoos_dm.information_ui import information_menu
        menu = information_menu(self.app)
        groups = [[]]
        for item in menu.items:
            if item is None:
                groups.append([])
            else:
                groups[-1].append(item[0])
        self.assertEqual(groups, [["Thiết lập"], ["Báo lỗi"],
                                  ["Kiểm tra cập nhật", "Giới thiệu", "Thoát"]])
        menu.destroy()

    def test_preferences_are_fully_localized_and_switch_back(self):
        from tkinter import ttk

        from hngoos_dm.rounded import RoundedButton
        def texts(parent):
            for child in parent.winfo_children():
                if isinstance(child, RoundedButton):
                    for item in child.find_all():
                        if child.type(item) == "text":
                            yield child.itemcget(item, "text")
                elif isinstance(child, (ttk.Label, ttk.Button, ttk.Checkbutton)):
                    variable = child.cget("textvariable")
                    yield str(self.root.getvar(str(variable))) if variable else child.cget("text")
                yield from texts(child)
        page = self.app.open_preferences()
        for language, expected in (("en", "Save as:"), ("vi", "Lưu tại:"), ("en", "Save as:")):
            self.app.set_preference("language", language)
            self.pump()
            labels = list(texts(page))
            self.assertIn(expected, labels)
            if language == "en":
                # Brand names are unchanged; all HDM-owned labels must be English.
                remaining = [label for label in labels if any(ord(c) > 127 and c.isalpha()
                             for c in label.replace("Cốc Cốc", ""))]
                self.assertEqual(remaining, [])
        page.destroy()

    def test_folder_path_is_readonly_shared_with_home_and_changed_by_clicking_path(self):
        page = self.app.open_preferences()
        self.pump()
        self.assertEqual(str(self.app.preference_directory.control.cget("textvariable")), str(self.app.directory))
        self.assertIsNotNone(self.app.preference_directory.action_button)
        with patch("hngoos_dm.app.filedialog.askdirectory", return_value=self.folder.name):
            self.app.preference_directory.action_button.invoke()
        self.assertEqual(self.app.directory.get(), self.folder.name)
        self.assertEqual(self.app.destination_entry.get(), self.app.directory.get())
        self.app.preference_directory.delete(0, "end")
        self.app.preference_directory.insert(0, self.folder.name)
        self.app.preference_directory.focus_force()
        self.app.preference_directory.event_generate("<Return>")
        self.pump()
        self.assertEqual(self.app.directory.get(), self.folder.name)
        self.assertEqual(self.app.store.setting("download_directory"), self.folder.name)
        self.assertEqual(self.app.destination_entry.get(), self.folder.name)
        page.destroy()

    def test_folder_icon_changes_shared_destination_and_focus_borders_stay_neutral(self):
        from hngoos_dm.ui_preferences import PALETTES
        with patch("hngoos_dm.app.filedialog.askdirectory", return_value=self.folder.name):
            self.app.destination_entry.action_button.invoke()
        self.assertEqual(self.app.directory.get(), self.folder.name)
        self.assertEqual(self.app.store.setting("download_directory"), self.folder.name)
        for theme in ("dark", "light"):
            self.app.set_preference("theme", theme)
            self.app.url_entry.focus_force()
            self.pump()
            field = self.app.url_entry
            outlines = [field.itemcget(item, "outline") for item in field.find_withtag("surface")
                        if field.type(item) == "polygon"]
            self.assertEqual(outlines, [PALETTES[theme][3]])

    def test_only_journal_scrolls_and_its_thumb_has_round_caps(self):
        for i in range(40):
            self.app.store.create(f"https://example.com/{i}.txt", Path(self.folder.name), f"{i}.txt")
        self.pump(1)
        self.assertEqual(len(self.app.table.get_children()), 40)
        bar = self.app.journal_scrollbar
        self.assertTrue(bar.winfo_ismapped())
        self.assertEqual(bar.itemcget(bar.find_withtag("thumb")[0], "capstyle"), "round")
        before = self.app.table.yview()
        self.app.table.event_generate("<MouseWheel>", delta=-120)
        self.pump()
        self.assertGreater(self.app.table.yview()[0], before[0])
        self.app.url_entry.event_generate("<MouseWheel>", delta=-120)
        self.pump()
        self.assertEqual(self.app.input_content.master.yview()[0], 0)
        self.assertFalse(self.app.input_content.scrollbar.winfo_ismapped())
        self.assertFalse(self.app.source_content.scrollbar.winfo_ismapped())
        self.assertFalse(hasattr(self.app, "journal_pager"))

    def test_no_proxy_default_hides_address_until_manual_is_selected(self):
        page = self.app.open_preferences()
        self.pump()
        self.assertEqual(self.app.proxy_mode.get(), "direct")
        self.assertFalse(self.app.proxy_address_row.winfo_ismapped())
        self.assertFalse(hasattr(page, "scroller"))
        self.app.proxy_mode.set("manual")
        self.pump()
        self.assertTrue(self.app.proxy_address_row.winfo_ismapped())
        for mode in ("direct", "system"):
            self.app.proxy_mode.set(mode)
            self.pump()
            self.assertFalse(self.app.proxy_address_row.winfo_ismapped())
        page.destroy()

    def test_preferences_and_update_stay_in_the_main_window_and_preserve_inputs(self):
        from tkinter import ttk
        original = self.app.manager
        self.app.url.set("https://example.com/preserve.pdf")
        page = self.app.open_preferences()
        self.pump()
        self.assertIsInstance(page, ttk.Frame)
        self.assertIs(page.winfo_toplevel(), self.root)
        self.assertFalse(self.app.tabs.winfo_ismapped())
        with patch("hngoos_dm.update_ui.check_update", return_value=None):
            self.app.check_update()
            self.pump()
            update = self.app.update_dialog
            self.assertIs(update.window.winfo_toplevel(), self.root)
            # Check navigation ownership even if the interactive desktop has
            # minimized the top-level window (which unmaps every child).
            self.assertIn(page, self.app.page_stack)
            self.assertEqual(page.winfo_manager(), "place")
            update.window.dismiss()
            self.pump()
            self.assertIn(page, self.app.page_stack)
            self.assertEqual(page.winfo_manager(), "place")
        self.app.brand_label.event_generate("<Button-1>")
        self.pump()
        self.assertTrue(self.app.tabs.winfo_ismapped())
        self.assertIs(self.app.manager, original)
        self.assertEqual(self.app.url.get(), "https://example.com/preserve.pdf")

    def test_maximum_transfer_defaults_replace_legacy_normal_mode(self):
        url = "https://example.com/file"
        host = self.app.manager.hosts.key(url)
        self.app.manager.hosts.limits[host] = 32
        self.app.store.set_setting("host_limits", {host: 2})
        self.app.set_transfer_mode("normal")
        self.assertEqual(self.app.manager.hosts.default_limit, 8)
        self.assertEqual(self.app.manager.bandwidth.rate, 4*1024*1024)
        self.app.close()
        self.root = tk.Tk()
        self.app = App(self.root, Path(self.folder.name))
        self.root.update()
        self.assertFalse(hasattr(self.app.speed_meter, "mode"))
        self.assertEqual(self.app.store.setting("transfer_mode"), "maximum")
        self.assertEqual(self.app.manager.hosts.default_limit, 32)
        self.assertEqual(self.app.manager.bandwidth.rate, 0)
        self.assertEqual(self.app.connections.get(), "32")
        self.assertEqual(self.app.manager.hosts.limits[host], 2)

    def test_labels_and_completed_status_follow_selected_language(self):
        row = self.app.store.create("https://example.com/report.pdf", Path(self.folder.name), "report.pdf")
        self.app.store.update(row["id"], state="complete")
        for language, headings, done in (
            ("vi", ("Tệp", "Trạng thái", "Tốc độ", "Kiểm tra", "Xóa"), "Hoàn tất"),
            ("en", ("File", "Status", "Speed", "Check", "Remove"), "Done"),
            ("vi", ("Tệp", "Trạng thái", "Tốc độ", "Kiểm tra", "Xóa"), "Hoàn tất"),
        ):
            self.app.set_preference("language", language)
            self.pump(0.6)
            self.assertEqual([self.app.table.heading(col, "text") for col in self.app.table["columns"]], [""]*5)
            self.assertTrue(all(label.cget("image") for label in self.app.heading_icons.values()))
            self.assertEqual(self.app.table.item(row["id"], "values")[1], done)
            labels = [w.cget("text") for w in self.app.url_form.winfo_children() if "text" in set(w.keys())]
            self.assertIn("URL:", labels)
            self.app.open_information()
            self.pump()
            button = self.app.preference_report_button
            rendered = [button.itemcget(item, "text") for item in button.find_all() if button.type(item) == "text"]
            self.assertIn("Báo lỗi" if language == "vi" else "Report", rendered)
            self.app.open_information()

    def test_minimal_header_and_table_have_no_hidden_actions(self):
        self.assertEqual(self.root.title(), "Hngoos Download Manager")
        self.assertFalse(hasattr(self.app, "categories"))
        self.assertFalse(hasattr(self.app, "empty_state"))
        self.assertEqual(tuple(self.app.table.cget("columns")),
                         ("name", "status", "speed", "check", "properties"))
        with patch("hngoos_dm.app.open_path") as open_folder:
            self.app.table.event_generate("<Button-1>", x=20, y=10)
            self.app.table.event_generate("<ButtonRelease-1>", x=20, y=10)
            self.pump()
            open_folder.assert_not_called()
        self.assertEqual(self.app.table.bind("<Double-1>"), "")

    def test_url_and_name_underlines_follow_text_and_file_extension_is_separate(self):
        from hngoos_dm.download_ui import DownloadEditor
        self.app.url.set("https://example.com/a.pdf")
        self.pump()
        label = next(w for w in self.app.url_form.winfo_children() if w != self.app.url_entry)
        gap = self.app.url_entry.winfo_rootx()-label.winfo_rootx()-label.winfo_width()
        self.assertLessEqual(gap, 10)
        short_width = self.app.url_entry.winfo_width()
        self.app.url.set("https://example.com/longer-file-name-and-document.pdf")
        self.pump()
        self.assertEqual(self.app.url_entry.winfo_width(), short_width)
        editor = self.app.download_editor = DownloadEditor(self.app, {
            "original": self.app.url.get(), "url": self.app.url.get(), "kind": "file", "filename": "Report.pdf"})
        editor.pack(fill="both", expand=True)
        self.app.resize_source_card()
        self.pump()
        self.assertEqual(editor.name_entry.get(), "Report")
        self.assertEqual(editor.extension.get(), ".pdf")
        editor.name_entry.delete(0, "end")
        editor.name_entry.insert(0, "A longer edited report")
        self.pump()
        self.assertEqual(editor.filename.get(), "A longer edited report.pdf")
        with patch.object(self.app, "add"):
            editor.confirm()
        self.assertEqual(self.app.filename.get(), "A longer edited report.pdf")

    def test_cards_center_their_controls_and_blend_corners(self):
        from tkinter import ttk
        about = self.app.open_about()
        self.pump()
        def widgets(parent):
            for child in parent.winfo_children():
                yield child
                yield from widgets(child)
        labels = [w for w in widgets(about) if isinstance(w, ttk.Label)]
        self.assertNotIn("Giới thiệu", [w.cget("text") for w in labels])
        self.assertNotIn("Liên hệ", [w.cget("text") for w in labels])
        self.assertTrue(about.find_withtag("backdrop"))
        contacts = [w for w in labels if w.cget("text") in ("Facebook", "Instagram", "Gmail", "GitHub")]
        left = min(w.winfo_rootx() for w in contacts)
        right = max(w.winfo_rootx()+w.winfo_width() for w in contacts)
        self.assertLessEqual(abs((left+right)/2-about.winfo_rootx()-about.winfo_width()/2), 2)
        about.dismiss()
        self.app.check_update()
        dialog = self.app.update_dialog
        self.pump()
        self.assertEqual(str(dialog.status_label.cget("anchor")), "center")
        self.assertEqual(str(dialog.status_label.cget("justify")), "center")
        self.assertEqual(dialog.primary.label, "")
        self.assertIs(dialog.primary.image, self.app.icons["refresh"])
        dialog.close()

    def test_column_separators_are_locked_and_rows_align_without_dark_button_blocks(self):
        from tkinter import ttk
        sample = Path(self.folder.name)/"fixture.pdf"
        sample.write_bytes(b"fixture")
        row = self.app.store.create("https://example.com/fixture.pdf", sample.parent, sample.name)
        self.app.store.update(row["id"], state="complete", output=str(sample))
        self.pump(.7)
        self.app.table.selection_set(row["id"])
        self.pump()
        for col in self.app.table["columns"]:
            anchor = "w" if col == "name" else "center"
            self.assertEqual(str(self.app.table.heading(col, "anchor")), anchor)
            self.assertEqual(str(self.app.table.column(col, "anchor")), anchor)
        total = sum(self.app.table.column(col, "width") for col in self.app.table["columns"])
        self.assertAlmostEqual(self.app.table.column("name", "width")/total, .4, delta=.005)
        separator = self.app.heading_separators[0]
        before = self.app.table.column("name", "width")
        separator.event_generate("<Button-1>", x=4, y=12, rootx=separator.winfo_rootx()+4)
        separator.event_generate("<B1-Motion>", x=-36, y=12, rootx=separator.winfo_rootx()-36)
        separator.event_generate("<ButtonRelease-1>", x=-36, y=12)
        self.pump()
        self.assertEqual(self.app.table.column("name", "width"), before)
        self.assertEqual(str(separator.cget("cursor")), "arrow")
        style = ttk.Style(self.root)
        selected = style.lookup("Treeview", "background", ("selected",))
        for col, button in (("check", self.app.row_safety_buttons[row["id"]]),
                            ("properties", self.app.row_more_buttons[row["id"]])):
            box = self.app.table.bbox(row["id"], col)
            self.assertLessEqual(abs(button.winfo_x()+button.winfo_width()/2-box[0]-box[2]/2), 1)
            self.assertEqual(button.cget("background"), selected)

    def test_source_and_queue_cards_stay_fixed_when_url_and_metadata_change(self):
        from hngoos_dm.download_ui import DownloadEditor
        def geometry(widget):
            return (widget.winfo_rootx(), widget.winfo_rooty(), widget.winfo_width(), widget.winfo_height())
        for window in ("1120x720", "1440x900"):
            self.root.geometry(window)
            self.app.dismiss_download()
            self.app.url.set("")
            self.pump()
            expected = (geometry(self.app.url_panel), geometry(self.app.queue_panel))
            blank = self.app.empty_panel
            self.assertEqual(self.app.url_form.master, self.app.input_content)
            self.assertEqual(self.app.destination_entry.master.master, self.app.input_content)
            self.assertLess(blank.winfo_rooty(), self.app.queue_panel.winfo_rooty())
            self.assertEqual(blank.winfo_rooty(), self.app.brand_label.winfo_rooty())
            self.assertFalse(self.app.url_panel.winfo_ismapped())
            # Hosted macOS displays can constrain the requested window width.
            # The input card must still fit its controls without clipping.
            for control in (self.app.url_entry, self.app.destination_entry,
                            self.app.download_button, self.app.cancel_button):
                self.assertGreater(control.winfo_width(), 0)
                self.assertGreaterEqual(control.winfo_rootx(), blank.winfo_rootx())
                self.assertLessEqual(control.winfo_rootx()+control.winfo_width(),
                                     blank.winfo_rootx()+blank.winfo_width())
            self.assertLess(blank.winfo_rooty()+blank.winfo_height(), self.app.queue_panel.winfo_rooty())
            for kind in ("file", "media"):
                self.app.url.set("https://example.com/" + "long-url/"*30 + "file")
                editor = self.app.download_editor = DownloadEditor(self.app, {
                    "original": self.app.url.get(), "url": self.app.url.get(), "kind": kind,
                    "filename": "A long file name "*12 + ".mp4",
                    "heights": [4320,2160,1440,1080,960,720,640,480,360,240,144]})
                editor.pack(fill="both", expand=True)
                self.app.resize_source_card()
                self.pump()
                self.assertEqual(geometry(self.app.queue_panel), expected[1])
                if kind == "media":
                    editor.format.set("MP4")
                    editor.format_changed()
                    self.pump()
                    self.assertEqual(geometry(self.app.queue_panel), expected[1])
                    self.app.source_content.master.yview_moveto(1)
                    self.pump()
                self.app.cancel_download()
                self.pump()
                self.assertEqual(geometry(self.app.queue_panel), expected[1])
                self.assertEqual(self.app.source_content.master.yview()[0], 0)

    def test_enter_from_url_recognizes_then_downloads_once_with_edited_name(self):
        url = "https://example.com/file.pdf"
        description = {"original": url, "url": url, "kind": "file", "filename": "Source.pdf"}
        self.app.url.set(url)
        with patch("hngoos_dm.links.describe_source", return_value=description), \
                patch.object(self.app, "add") as add:
            self.app.url_entry.focus_force()
            self.app.url_entry.event_generate("<Return>")
            self.pump(0.7)
            add.assert_called_once_with(resolved_source=("file", url))
        from hngoos_dm.download_ui import DownloadEditor
        self.app.download_editor = editor = DownloadEditor(self.app, description)
        editor.pack(fill="both", expand=True)
        editor.filename.set("My document.pdf")
        with patch.object(self.app, "add") as add:
            self.app.download_button.invoke()
            self.assertEqual(self.app.filename.get(), "My document.pdf")
            add.assert_called_once()

    def test_info_is_text_only_and_appearance_and_language_are_preferences(self):
        from hngoos_dm.information_ui import information_menu
        menu = information_menu(self.app)
        labels = [item[0] for item in menu.items if item]
        self.assertFalse(any("Giao diện" in label or "Ngôn ngữ" in label for label in labels))
        self.assertTrue(all(item[2] is None for item in menu.items if item))
        menu.destroy()
        dialog = self.app.open_preferences()
        self.pump()
        self.app.preference_theme.select("light")
        self.app.preference_language.select("en")
        self.pump()
        self.assertEqual(self.app.theme, "light")
        self.assertEqual(self.app.locale.language, "en")
        dialog.destroy()

    def test_manual_paste_reveals_metadata_in_url_card_without_starting(self):
        url = "https://example.com/document.pdf"
        description = {"original": url, "url": url, "kind": "file", "filename": "Document.pdf"}
        with patch("hngoos_dm.links.describe_source", return_value=description) as describe, \
                patch.object(self.app.manager, "add") as add:
            self.root.clipboard_clear()
            self.root.clipboard_append(url)
            self.app.url_entry.event_generate("<<Paste>>")
            self.pump(1)
            describe.assert_called_once_with(url, proxy={"mode": "direct", "url": ""})
            editor = self.app.download_editor
            self.assertEqual(editor.filename.get(), "Document.pdf")
            self.assertIs(editor.master, self.app.source_content)
            self.assertFalse(hasattr(editor, "source_url"))
            add.assert_not_called()

    def test_background_refresh_never_reads_clipboard_even_with_old_setting(self):
        self.app.store.set_setting("clipboard_enabled", True)
        with patch.object(self.root, "clipboard_get", return_value="https://example.com/secret") as read:
            self.pump(1.2)
            read.assert_not_called()
            self.assertEqual(self.app.url.get(), "")

    def test_compact_controls_and_readable_heading_hover(self):
        from tkinter import ttk
        self.assertFalse(hasattr(self.app, "transfer_button"))
        self.assertFalse(hasattr(self.app, "categories"))
        self.assertGreater(self.app.destination_entry.winfo_rootx(), self.app.speed_meter.winfo_rootx())
        style = ttk.Style(self.root)
        for theme in ("dark", "light"):
            self.app.set_preference("theme", theme)
            self.pump()
            self.assertEqual(style.lookup("Treeview.Heading", "foreground", ("active",)),
                             style.lookup("Treeview.Heading", "foreground"))
            bg = str(style.lookup("Treeview.Heading", "background", ("active",)))
            self.assertEqual(bg, str(style.lookup("Card.TFrame", "background")))
            self.assertEqual(style.lookup("Rounded.TEntry", "fieldbackground", ("readonly",)),
                             style.lookup("Card.TFrame", "background"))
            self.assertEqual(style.lookup("Rounded.TEntry", "background", ("readonly",)),
                             style.lookup("Card.TFrame", "background"))

    def test_media_choices_are_visible_and_filename_is_automatic(self):
        from hngoos_dm.download_ui import DownloadEditor
        url = "https://youtu.be/example"
        self.app.url.set(url)
        editor = self.app.download_editor = DownloadEditor(self.app, {
            "original": url, "url": url, "kind": "media", "filename": "Example.mp4", "heights": [360, 720], "formats": [
                {"format_id": "18", "ext": "mp4", "height": 360, "vcodec": "avc1", "acodec": "aac"},
                {"format_id": "22", "ext": "mp4", "height": 720, "vcodec": "avc1", "acodec": "aac"},
                {"format_id": "140", "ext": "m4a", "vcodec": "none", "acodec": "aac", "abr": 128},
                {"format_id": "141", "ext": "m4a", "vcodec": "none", "acodec": "aac", "abr": 192}]})
        editor.pack(fill="both", expand=True)
        self.app.resize_source_card()
        self.pump()
        self.assertTrue(editor.media_controls.winfo_ismapped())
        self.assertFalse(hasattr(editor, "toggle_advanced"))
        from tkinter import ttk
        self.assertIsInstance(editor.name_entry.control, ttk.Entry)
        self.assertEqual({key for key, button in editor.quality_choices.buttons.items() if str(button.cget("state")) == "normal"}, {"360", "720"})
        editor.format_choices.buttons["M4A"].invoke()
        self.assertEqual(editor.filename.get(), "Example.m4a")
        self.assertEqual(set(editor.quality_choices.buttons), {"128", "192"})
        editor.quality_choices.buttons["192"].invoke()
        self.assertEqual(editor.bitrate.get(), "192")
        editor.format_choices.buttons["MP4"].invoke()
        self.assertEqual(editor.filename.get(), "Example.mp4")
        self.assertEqual({key for key, button in editor.quality_choices.buttons.items() if str(button.cget("state")) == "normal"}, {"360", "720"})

    def test_row_options_keep_file_on_remove_and_require_confirmation_for_delete(self):
        sample = Path(self.folder.name)/"keep.pdf"
        sample.write_bytes(b"fixture")
        row = self.app.store.create("https://example.com/keep.pdf", sample.parent, sample.name)
        self.app.store.update(row["id"], state="complete", output=str(sample))
        self.pump(0.6)
        self.assertEqual(self.app.row_safety_buttons[row["id"]].label, "Kiểm tra")
        more = self.app.row_more_buttons[row["id"]]
        self.assertEqual(more.label, "Xóa")
        more.invoke()
        self.pump()
        self.assertFalse(hasattr(self.app, "job_menu"))
        self.assertTrue(sample.exists())
        self.assertEqual(self.app.store.all(), [])
        row = self.app.store.create("https://example.com/keep.pdf", sample.parent, sample.name)
        self.app.store.update(row["id"], state="complete", output=str(sample))
        with patch("hngoos_dm.app.messagebox.askyesno", return_value=False):
            self.app.delete_job(row["id"], True)
        self.assertTrue(sample.exists())
        self.assertEqual(len(self.app.store.all()), 1)
        self.app.delete_job(row["id"], False)
        self.assertTrue(sample.exists())
        self.assertEqual(self.app.store.all(), [])
        row = self.app.store.create("https://example.com/keep.pdf", sample.parent, sample.name)
        self.app.store.update(row["id"], state="complete", output=str(sample))
        with patch("hngoos_dm.app.messagebox.askyesno", return_value=True):
            self.app.delete_job(row["id"], True)
        self.assertFalse(sample.exists())
        self.assertEqual(self.app.store.all(), [])

    def test_logo_toggles_preferences_and_media_card_uses_half_window_width(self):
        from hngoos_dm.download_ui import DownloadEditor
        def geometry():
            logo = self.app.brand_label
            return logo.winfo_rootx(), logo.winfo_rooty(), logo.winfo_width(), logo.winfo_height()
        for size in ("1120x720", "1920x1080"):
            self.root.geometry(size)
            self.pump()
            expected = geometry()
            self.app.brand_label.event_generate("<Button-1>")
            self.pump()
            page = self.app.preferences_dialog
            self.assertTrue(page.winfo_ismapped())
            self.assertEqual(geometry(), expected)
            self.app.brand_label.event_generate("<Button-1>")
            self.pump()
            self.assertFalse(page.winfo_ismapped())
            self.assertEqual(geometry(), expected)
            self.assertFalse(self.app.page_stack)
            self.app.url.set("https://example.com/video.mp4")
            self.app.download_editor = DownloadEditor(self.app, {
                "original": self.app.url.get(), "url": self.app.url.get(), "kind": "media",
                "filename": "video.mp4", "heights": [720]})
            self.app.download_editor.pack(fill="both", expand=True)
            self.pump()
            for column, widget in enumerate((self.app.header_left, self.app.empty_panel, self.app.url_panel)):
                self.assertEqual(int(widget.grid_info()["column"]), column)
            self.assertAlmostEqual(self.app.header_logo.height(), self.root.winfo_height()/5, delta=1)
            self.assertAlmostEqual(self.app.url_panel.winfo_width(), self.root.winfo_width()/2, delta=1)
            self.assertLess(self.app.brand_label.winfo_rooty()+self.app.brand_label.winfo_height(),
                            self.app.queue_panel.winfo_rooty())
            self.app.cancel_download()

    def test_portrait_quality_matches_source_tier_and_mp3_is_an_encoding_choice(self):
        from hngoos_dm.download_ui import DownloadEditor
        self.app.url.set("https://youtu.be/portrait")
        editor = self.app.download_editor = DownloadEditor(self.app, {
            "original": self.app.url.get(), "url": self.app.url.get(), "kind": "media", "filename": "Portrait.mp4",
            "formats": [
                {"format_id": "134", "ext": "mp4", "height": 468, "quality": 360, "vcodec": "avc1", "acodec": "none"},
                {"format_id": "140", "ext": "m4a", "vcodec": "none", "acodec": "aac", "abr": 129.5}]})
        editor.pack(fill="both", expand=True)
        self.pump()
        self.assertEqual(set(editor.quality_choices.buttons), {"360"})
        self.assertEqual(editor.format_id.get(), "134+140")
        editor.format_choices.buttons["MP3"].invoke()
        self.assertEqual(set(editor.quality_choices.buttons), {"320", "256", "192", "128"})
        self.assertEqual(editor.extension.get(), ".mp3")
        self.assertEqual(editor.format_id.get(), "")
        with patch.object(self.app, "add"):
            editor.confirm()
        self.assertEqual(self.app.download_format.get(), "MP3")
        self.assertEqual(self.app.media_bitrate.get(), "320")

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
        # Release old Tk cycles on the UI thread, before a worker can trigger GC.
        gc.collect()

    def tearDown(self):
        self.app.close()
        self.folder.cleanup()

    def pump(self, seconds=0.2):
        end = time.monotonic()+seconds
        while time.monotonic() < end:
            self.root.update()
            time.sleep(0.01)
        self.assertEqual(self.errors, [])

    def test_media_link_download_uses_shared_history_and_mp3_choice(self):
        target = Path(self.folder.name)/"clip.mp3"
        target.write_bytes(b"audio fixture")
        self.app.url.set("https://youtu.be/example")
        self.app.download_format.set("MP3")
        self.app.media_bitrate.set("192")
        with patch("hngoos_dm.media.download_video", return_value=[target]) as download:
            self.app.add()
            self.pump(0.6)
        row = self.app.store.all()[0]
        self.assertEqual(row["kind"], "media")
        self.assertEqual(row["state"], "complete")
        self.assertEqual(row["output"], str(target))
        self.assertEqual(download.call_args.kwargs["options"].audio, "mp3")
        self.assertEqual(download.call_args.kwargs["options"].audio_bitrate, 192)
        self.assertFalse(self.app.media_busy)

    def test_information_menu_contains_language_and_browser_and_preferences_open_once(self):
        from hngoos_dm.information_ui import information_menu
        menu = information_menu(self.app)
        labels = [item[0].removesuffix("  ›") for item in menu.items if item]
        self.assertNotIn("Ngôn ngữ", labels)
        self.assertNotIn("Giao diện", labels)
        self.assertNotIn("Tiện ích trình duyệt", labels)
        self.assertFalse(hasattr(self.app, "header_controls"))
        self.assertFalse(hasattr(self.app, "language_switch"))
        self.assertFalse(hasattr(self.app, "theme_switch"))
        self.assertFalse(hasattr(self.app, "info_button"))
        self.assertFalse(hasattr(self.app, "navigation_buttons"))
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
        self.assertEqual(self.app.table.heading("name", "text"), "")
        self.assertTrue(self.app.heading_icons["name"].cget("image"))
        self.assertEqual(inputs, (self.app.url.get(), self.app.filename.get(), self.app.connections.get()))
        self.app.set_bandwidth("medium")
        self.pump()
        self.assertEqual(self.app.store.setting("bandwidth_mode"), "medium")
        self.assertEqual(self.app.bandwidth_mode.get(), "Vừa (4 MB/s)")
        self.app.set_preference("language", "vi")
        self.pump()
        self.assertEqual(self.app.tabs.tab(0, "text"), "Tải xuống")
        self.assertFalse(hasattr(self.app.speed_meter, "mode"))

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
        dialog = DownloadEditor(self.app, {"original": self.app.url.get(), "url": self.app.url.get(), "kind": "media",
            "filename": "Example.m4a", "formats": [
                {"format_id": "140", "ext": "m4a", "vcodec": "none", "acodec": "aac", "abr": 128},
                {"format_id": "141", "ext": "m4a", "vcodec": "none", "acodec": "aac", "abr": 192}]})
        self.app.download_editor = dialog
        dialog.pack(fill="both", expand=True)
        self.app.resize_source_card()
        self.pump()
        self.assertTrue(dialog.media_controls.winfo_ismapped())
        dialog.format.set("M4A")
        dialog.format_changed()
        self.assertEqual(dialog.quality_choices.buttons["192"].label, "192 kbps")
        dialog.quality_choices.buttons["128"].invoke()
        with patch.object(self.app, "add") as add:
            dialog.confirm()
            add.assert_called_once_with(resolved_source=("media", "https://youtu.be/example"))
            self.assertEqual(self.app.download_format.get(), "M4A")
            self.assertEqual(self.app.media_bitrate.get(), "128")

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

    def test_completed_row_check_scans_defender_directly_and_blocks_duplicate_clicks(self):
        import threading
        from types import SimpleNamespace
        source = Path(self.folder.name)/"invoice.pdf"
        source.write_bytes(b"document fixture")
        row = self.app.store.create("https://example.com/invoice.pdf", source.parent, source.name)
        self.app.store.update(row["id"], state="complete", output=str(source))
        release = threading.Event()
        def scan(path):
            release.wait(3)
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        with patch("hngoos_dm.app.scan_defender", side_effect=scan) as defender, \
                patch("hngoos_dm.app.webbrowser.open") as remote:
            self.pump(.6)
            self.app.row_safety_buttons[row["id"]].invoke()
            self.app.check_selected_safety(row["id"])
            self.assertIn(row["id"], self.app.safety_scanning)
            self.assertEqual(self.app.store.get(row["id"])["safety_check"]["status"], "scanning")
            release.set()
            self.pump(.7)
            defender.assert_called_once_with(str(source))
            remote.assert_not_called()
        self.assertFalse(hasattr(self.app, "safety_dialog"))
        self.assertEqual(self.app.page_stack, [])
        self.assertEqual(self.app.store.get(row["id"])["safety_check"]["status"], "clean")
        for lang, label in (("en", "Safe"), ("vi", "An toàn")):
            self.app.set_preference("language", lang)
            self.pump(.6)
            self.assertNotIn(row["id"], self.app.row_safety_buttons)
            self.assertEqual(self.app.table.set(row["id"], "check"), label)

    def test_defender_failure_and_file_changes_are_never_reported_clean(self):
        from types import SimpleNamespace
        source = Path(self.folder.name)/"fixture.txt"
        source.write_bytes(b"original")
        job = self.app.store.create("https://example.com/fixture.txt", source.parent, source.name)
        self.app.store.update(job["id"], state="complete", output=str(source))
        for code, expected in ((2, "threat"), (1, "error")):
            with patch("hngoos_dm.app.scan_defender", return_value=SimpleNamespace(returncode=code, stdout="", stderr="")):
                self.app.check_selected_safety(job["id"])
                self.pump(.6)
            self.assertEqual(self.app.store.get(job["id"])["safety_check"]["status"], expected)
        with patch("hngoos_dm.app.scan_defender", side_effect=FileNotFoundError("Defender unavailable")):
            self.app.check_selected_safety(job["id"])
            self.pump(.6)
        self.assertEqual(self.app.store.get(job["id"])["safety_check"]["status"], "error")
        def mutate(path):
            source.write_bytes(b"changed")
            return SimpleNamespace(returncode=0)
        with patch("hngoos_dm.app.scan_defender", side_effect=mutate):
            self.app.check_selected_safety(job["id"])
            self.pump(.6)
        self.assertEqual(self.app.store.get(job["id"])["safety_check"]["status"], "error")

    def test_main_has_no_media_controls_and_panels_resize_in_both_themes(self):
        from tkinter import ttk
        def widgets(parent):
            for child in parent.winfo_children():
                yield child
                yield from widgets(child)
        labels = [child.cget("text") for child in widgets(self.root) if isinstance(child, ttk.Label)]
        self.assertIn("Định dạng", labels)
        self.assertTrue(all(str(button.cget("state")) == "disabled" for button in self.app.download_placeholder.format_choices.buttons.values()))
        self.assertNotIn("Độ cao tối đa", labels)
        for theme, geometry in (("light", "1120x720"), ("dark", "1440x900")):
            self.app.set_preference("theme", theme)
            self.root.geometry(geometry)
            self.pump()
            styles = ttk.Style(self.root)
            for name in ("TFrame", "Card.TFrame", "TEntry", "TCombobox", "Treeview", "TButton"):
                red, green, blue = self.root.winfo_rgb(str(styles.lookup(name, "background")))
                self.assertEqual((red, green), (green, blue), (theme, name))
            self.assertGreater(self.app.queue_panel.winfo_height(), 300)
            self.assertGreaterEqual(self.app.url_entry.winfo_width(), 115)
            self.assertLess(self.app.url_entry.winfo_width(), self.app.empty_panel.winfo_width())
            self.assertLess(self.app.url_entry.winfo_rootx()+self.app.url_entry.winfo_width(),
                            self.root.winfo_rootx()+self.root.winfo_width())
            self.assertTrue(self.app.download_button.winfo_ismapped())
            self.assertGreater(self.app.destination_entry.winfo_rooty(),
                               self.app.brand_label.winfo_rooty())

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
                self.assertEqual(str(style.lookup("TFrame", "background")), "#121212")
                continue
            self.assertEqual(self.root.cget("background"), "#f6f6f6")
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
            self.assertEqual(dialog.cget("background"), "#f6f6f6")
            self.assertEqual(str(style.lookup("TButton", "foreground")), "#222222")
            dialog.destroy()

    def test_all_downloads_and_safety_controls_remain_visible_without_categories(self):
        for name in ("invoice.pdf", "setup.exe.chuakiemtra", "clip.mp4", "song.mp3"):
            path = Path(self.folder.name)/name
            path.touch()
            job = self.app.store.create("https://example.com/"+name, path.parent, name)
            self.app.store.update(job["id"], state="complete", output=str(path))
        self.pump(0.6)
        self.assertEqual(len(self.app.table.get_children()), 4)
        self.assertEqual(len(self.app.row_safety_buttons), 4)
        self.assertTrue(all(self.app.table.item(row, "values")[1] == "Hoàn tất" for row in self.app.table.get_children()))

    def test_speed_meter_ignores_stale_rates_and_includes_torrent_upload(self):
        from types import SimpleNamespace
        self.assertFalse(self.app.footer.winfo_ismapped())
        for name, state, rate in (("active.pdf", "downloading", 2048), ("old.zip", "complete", 9000)):
            row = self.app.store.create("https://example.com/"+name, Path(self.folder.name), name)
            self.app.store.update(row["id"], state=state, speed=rate)
        self.app.torrent_jobs = [SimpleNamespace(closed=False, completed=False,
            status=lambda: {"download_rate": 1024, "upload_rate": 512}, close=lambda: None)]
        self.pump(0.6)
        self.assertEqual(self.app.speed_meter.down.get(), "3.0 KB/s")
        self.assertEqual(self.app.speed_meter.up.get(), "512.0 B/s")
        for mode, label in (("light", "LOW"), ("maximum", "HIGH"), ("medium", "MEDIUM")):
            self.app.set_bandwidth(mode)
            self.assertEqual(self.app.store.setting("bandwidth_mode"), mode)
            self.assertEqual(self.app.manager.bandwidth.rate, self.app.manager.bandwidth.MODES[mode])
            self.assertFalse(hasattr(self.app.speed_meter, "mode"))

    def test_rounded_fields_preserve_native_editing_return_and_readonly_choices(self):
        from hngoos_dm.rounded import RoundedCombobox
        entry = self.app.url_entry
        entry.insert(0, "https://example.com/original")
        entry.delete(20, "end")
        entry.insert("end", "updated.pdf")
        self.assertEqual(entry.get(), "https://example.com/updated.pdf")
        with patch.object(self.app, "submit_download") as prepare:
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
            check.assert_not_called()
            self.assertEqual(dialog.primary.label, "")
            self.assertIs(dialog.primary.image, self.app.icons["refresh"])
            dialog.primary.invoke()
            self.pump()
            self.assertEqual(dialog.status.get(), "Không có bản cập nhật mới.")
            self.assertFalse(dialog.busy)
            check.assert_called_once()
            browser.assert_not_called()
            dialog.close()

    def test_install_rejects_tampered_bytes_without_launching(self):
        import hashlib
        from tkinter import ttk

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
            self.assertIn("bản phát hành đã ký", dialog.status.get())
            self.app.set_preference("language", "en")
            self.pump()
            output = self.root.getvar(str(next(widget.cget("textvariable") for widget in
                dialog.window.body.winfo_children()[0].winfo_children() if isinstance(widget, ttk.Label)
                and widget.cget("textvariable"))))
            self.assertIn("signed release", output)
            self.assertNotIn("Không thể", output)
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
