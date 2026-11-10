"""The compact download header follows the approved desktop sketch."""

import sys
import time
import unittest

import tests.test_ui_preferences as presentation


class SketchLayoutTests(unittest.TestCase):
    setUp = presentation.PresentationTests.setUp
    tearDown = presentation.PresentationTests.tearDown
    pump = presentation.PresentationTests.pump

    def test_youtube_selection_avoids_peak_bitrate_hls_when_direct_stream_exists(self):
        from hngoos_dm.download_ui import DownloadEditor
        from hngoos_dm.media_progress import MediaProgress

        app = self.app
        app.url.set("https://www.youtube.com/watch?v=-FNnwgaqf44")
        editor = app.download_editor = DownloadEditor(app, {
            "kind": "media", "url": app.url.get(), "original": app.url.get(), "filename": "Video.mp4",
            "heights": [1080], "formats": [
                {"format_id": "270", "ext": "mp4", "height": 1080, "vcodec": "avc1", "acodec": "none",
                 "protocol": "m3u8_native", "tbr": 2779.933},
                {"format_id": "137", "ext": "mp4", "height": 1080, "vcodec": "avc1", "acodec": "none",
                 "protocol": "https", "filesize": 533641485, "tbr": 1589.085},
                {"format_id": "140", "ext": "m4a", "vcodec": "none", "acodec": "aac",
                 "protocol": "https", "filesize": 43480781, "abr": 129.5}]})
        self.assertEqual(editor.format_id.get(), "137+140")
        # New reporter instances model a fresh transfer and its resumed transfer.
        received = []
        for downloaded, estimate in ((118900000, 718900000), (252300000, 681000000)):
            progress = MediaProgress(received.append)
            progress.plan({"id": "clip", "requested_formats": [
                {"format_id": "137", "filesize": 533641485},
                {"format_id": "140", "filesize": 43480781}]})
            progress({"downloaded_bytes": downloaded, "total_bytes_estimate": estimate,
                      "info_dict": {"id": "clip", "format_id": "137"}})
            self.assertEqual(received[-1]["total_bytes"], 577122266)
            self.assertFalse(received[-1]["total_estimated"])

    def test_clear_link_is_an_icon_at_the_end_of_url_row(self):
        app = self.app
        app.url.set("https://example.com/file.pdf")
        app.show_source_controls(True)
        self.pump()
        button = app.cancel_button
        self.assertEqual(button.label, "")
        self.assertIs(button.image, app.icons["close"])
        self.assertIs(button.master, app.url_form)
        self.assertEqual(int(button.grid_info()["row"]), 0)
        self.assertGreater(button.winfo_rootx(), app.url_entry.winfo_rootx()+app.url_entry.winfo_width())
        button.invoke()
        self.pump()
        self.assertEqual(app.url.get(), "")
        self.assertFalse(app.download_button.winfo_ismapped())

    def test_clear_link_appears_for_any_text_without_recognition(self):
        app = self.app
        self.assertFalse(app.cancel_button.winfo_ismapped())
        for value in ("x", "bad://link", "   "):
            app.url.set(value)
            self.pump(.1)
            self.assertTrue(app.cancel_button.winfo_ismapped(), repr(value))
            self.assertFalse(app.download_button.winfo_ismapped())
            app.cancel_button.invoke()
            self.pump(.1)
            self.assertEqual(app.url.get(), "")
            self.assertFalse(app.cancel_button.winfo_ismapped())

    def test_journal_separates_actions_and_completion_has_only_remove(self):
        from pathlib import Path

        app = self.app
        app.set_preference("language", "en")
        target = Path(self.folder.name)/"sample.bin"
        target.write_bytes(b"fixture")
        row = app.store.create("https://example.com/sample.bin", target.parent, target.name)
        app.store.update(row["id"], state="downloading")
        self.pump(.6)
        self.assertEqual(app.row_more_buttons[row["id"]].translate(app.row_more_buttons[row["id"]].label), "Stop")
        separator = app.row_cell_labels[row["id"], "actions_separator"]
        self.assertEqual(separator.cget("text"), "|")
        self.assertTrue(separator.winfo_ismapped())
        app.store.update(row["id"], state="complete", output=str(target))
        self.pump(.6)
        self.assertEqual(app.row_more_buttons[row["id"]].translate(app.row_more_buttons[row["id"]].label), "Remove")
        self.assertNotIn(row["id"], app.row_remove_buttons)
        self.assertNotIn((row["id"], "actions_separator"), app.row_cell_labels)
        separator = app.row_cell_labels[row["id"], "status_separator"]
        status = app.row_cell_labels[row["id"], "status"]
        check = app.row_safety_buttons[row["id"]]
        self.assertEqual(separator.cget("text"), "|")
        self.assertGreaterEqual(separator.winfo_x(), status.winfo_x()+status.winfo_width())
        self.assertLessEqual(separator.winfo_x()+separator.winfo_width(), check.winfo_x())

    def test_journal_shows_received_and_total_without_question_marks(self):
        app = self.app
        row = app.store.create("https://example.com/video", self.folder.name, "video.mp4")
        for language, unknown in (("en", "Determining size"), ("vi", "Đang xác định dung lượng")):
            app.set_preference("language", language)
            for total, estimated, expected in ((90*1024**2, False, "40.0 MB / 90.0 MB"),
                                                (90*1024**2, True, "40.0 MB / ≈90.0 MB"),
                                                (0, False, "40.0 MB / "+unknown)):
                app.store.update(row["id"], state="downloading", downloaded=40*1024**2,
                                 total=total, total_estimated=estimated)
                app._refresh_state()
                self.assertEqual(app.table.item(row["id"], "values")[1], expected)

    def test_media_postprocessor_cannot_erase_received_and_total(self):
        from unittest.mock import patch

        from hngoos_dm.media import MediaCancelled

        app = self.app
        app.media_url.set("https://example.com/video")
        def extract(_url, _directory, **kwargs):
            kwargs["progress"]({"status": "downloading", "downloaded_bytes": 40_000_000,
                                "total_bytes": 90_000_000, "total_estimated": False})
            kwargs["progress"]({"status": "finished", "postprocessor": "Merger"})
            raise MediaCancelled()
        with patch("hngoos_dm.media.download_video", side_effect=extract):
            app.start_media("")
            app.background_threads[-1].join(timeout=5)
            self.assertFalse(app.background_threads[-1].is_alive())
        row = app.store.get(app.media_job_id)
        self.assertEqual((row["downloaded"], row["total"]), (40_000_000, 90_000_000))

    def test_header_geometry(self):
        from hngoos_dm.rounded import RoundedPanel, UnderlinedEntry

        self.pump()
        app = self.app
        self.assertNotIsInstance(app.empty_panel, RoundedPanel)
        self.assertNotIsInstance(app.url_panel, RoundedPanel)
        self.assertIsInstance(app.url_entry, UnderlinedEntry)
        self.assertFalse(app.url_panel.winfo_ismapped())
        self.assertFalse(app.download_button.winfo_ismapped())
        self.assertFalse(app.cancel_button.winfo_ismapped())
        self.assertFalse(hasattr(app, "destination_row"))
        app.url.set("https://example.com/file.bin")
        app.show_source_controls(True)
        self.pump()
        for entry, button in ((app.url_entry, app.download_button), (app.url_entry, app.cancel_button)):
            self.assertAlmostEqual(entry.winfo_rooty()+entry.winfo_height()/2,
                                   button.winfo_rooty()+button.winfo_height()/2, delta=2)
            self.assertLess(entry.winfo_rootx()+entry.winfo_width(), button.winfo_rootx())
        self.assertLess(app.brand_label.winfo_rootx(), app.url_entry.winfo_rootx())
        self.assertLess(app.header.winfo_height(), self.root.winfo_height()/3)
        self.assertGreater(app.queue_panel.winfo_height(), self.root.winfo_height()*.6)

    def test_metadata_keeps_journal_fixed_and_name_editable(self):
        from hngoos_dm.download_ui import DownloadEditor

        self.pump()
        app = self.app
        expected = (app.queue_panel.winfo_y(), app.queue_panel.winfo_height())
        for kind, filename in (("file", "Document.pdf"), ("media", "Video.mp4")):
            app.url.set("https://example.com/"+filename)
            app.download_editor = editor = DownloadEditor(app, {
                "kind": kind, "url": app.url.get(), "original": app.url.get(),
                "filename": filename, "heights": [1080, 720] if kind == "media" else []})
            editor.pack(fill="both", expand=True)
            self.pump()
            self.assertTrue(editor.name_entry.winfo_ismapped())
            self.assertEqual((app.queue_panel.winfo_y(), app.queue_panel.winfo_height()), expected)
            editor.name.set("Renamed")
            self.assertEqual(editor.filename.get(), "Renamed"+editor.extension.get())
            self.assertEqual(editor.format_choices.winfo_ismapped(), kind == "media")
            app.cancel_download()
            self.pump()

    def test_update_notice_requires_available_release(self):
        app = self.app
        self.pump()
        self.assertFalse(app.update_notice.winfo_ismapped())
        app.automatic_updates.found({"version": "99.0.0"}, None, None)
        self.pump()
        self.assertTrue(app.update_notice.winfo_ismapped())
        app.automatic_updates.found(None, None, None)
        self.pump()
        self.assertFalse(app.update_notice.winfo_ismapped())

    def test_update_notice_is_only_on_main_view_and_scales(self):
        app = self.app
        app.show_update_notice(True)
        self.pump()
        self.assertTrue(app.update_notice.winfo_ismapped())
        page = app.open_preferences()
        self.pump()
        self.assertFalse(app.update_notice.winfo_ismapped(), "Update notice belongs only on the main view")
        surface = app.presentation_surface
        for geometry in ("1320x900", "900x640", "760x560", "800x500"):
            self.root.geometry(geometry)
            self.pump(.3)
            for language in ("vi", "en"):
                app.set_preference("language", language)
                app.set_preference("theme", "light" if language == "vi" else "dark")
                self.pump(.2)
                with self.subTest(geometry=geometry, language=language):
                    appearance_position = surface.bounds(page.sections["Chung"])
                    app.show_update_notice(False)
                    app.show_update_notice(True)
                    self.pump(.1)
                    self.assertFalse(app.update_notice.winfo_ismapped(), "Late notifications stay hidden in preferences")
                    self.assertFalse(any(widget is app.update_notice for widget, _, _ in surface.regions))
                    self.assertEqual(surface.bounds(page.sections["Chung"]), appearance_position)
                    for button in app.contact_buttons.values():
                        _, by, _, bh = surface.bounds(button)
                        self.assertLessEqual(by+bh, self.root.winfo_height())
                    page.hide()
                    self.pump(.2)
                    self.assertTrue(app.update_notice.winfo_ismapped())
                    x, y, width, height = surface.bounds(app.update_notice)
                    lx, ly, lw, lh = surface.bounds(app.brand_label)
                    _, hy, _, hh = surface.bounds(app.header)
                    self.assertGreaterEqual(y, ly+lh+4)
                    self.assertLessEqual(y+height, hy+hh, "Notice is outside its reserved header")
                    self.assertLessEqual(y+height, surface.bounds(app.queue_panel)[1])
                    self.assertGreaterEqual(x, lx)
                    self.assertLessEqual(x+width, lx+lw+1, "Notice is wider than the logo column")
                    self.assertTrue(any(widget is app.update_notice for widget, _, _ in surface.regions))
                    for item in app.update_notice.find_all():
                        if app.update_notice.type(item) == "text":
                            text_box = app.update_notice.bbox(item)
                            self.assertGreaterEqual(text_box[0], 0, "Update label is clipped")
                            self.assertLessEqual(text_box[2], width, "Update label is clipped")
                    page.show()
                    self.pump(.1)
                    self.assertFalse(app.update_notice.winfo_ismapped())
        app.show_update_notice(False)
        page.hide()
        self.pump()
        self.assertFalse(app.update_notice.winfo_ismapped())

    def test_update_notice_does_not_interrupt_shutdown_from_preferences(self):
        self.app.show_update_notice(True)
        self.app.open_preferences()
        self.pump()
        self.app.close()
        self.assertEqual(self.errors, [], "Closing preferences must finish destroying the window")

    def test_paste_recognizes_without_starting_and_cancel_restores_url_only(self):
        from unittest.mock import patch

        app = self.app
        for filename, options in (("Document.pdf", False), ("Image.png", False),
                                  ("Video.mp4", True), ("Audio.mp3", True)):
            url = "https://example.com/"+filename
            description = {"kind": "file", "url": url, "original": url, "filename": filename}
            with patch("hngoos_dm.links.describe_source", return_value=description), patch.object(app, "add") as add:
                app.url.set(url)
                app.manual_paste()
                deadline = time.monotonic()+10
                editor = None
                while time.monotonic() < deadline:
                    self.pump(.05)
                    editor = getattr(app, "download_editor", None)
                    if editor is not None and editor.original == url:
                        break
                self.assertIsNotNone(editor, f"Source preview did not finish: {app.source_message.get()}")
                self.assertEqual(editor.filename.get(), filename)
                self.assertTrue(editor.name_entry.winfo_ismapped())
                self.assertTrue(app.download_button.winfo_ismapped())
                self.assertTrue(app.cancel_button.winfo_ismapped())
                self.assertEqual(editor.format_choices.winfo_ismapped(), options)
                self.assertEqual(editor.quality_choices.winfo_ismapped(), options)
                add.assert_not_called()
                app.cancel_button.invoke()
                self.pump()
                self.assertEqual(app.url.get(), "")
                self.assertFalse(app.url_panel.winfo_ismapped())
                self.assertFalse(app.download_button.winfo_ismapped())
                self.assertFalse(app.cancel_button.winfo_ismapped())

    def test_journal_action_resumes_media_and_rechecks_state_when_clicked(self):
        from unittest.mock import patch

        app = self.app
        row = app.store.create("https://example.com/video", self.folder.name, "video.mp4")
        row_id = row["id"]
        app.store.update(row_id, kind="media", state="paused")
        self.pump(.6)
        button = app.row_more_buttons[row_id]
        self.assertEqual(button.label, "Tiếp tục")
        with patch.object(app, "resume_media") as resume:
            button.invoke()
            self.assertEqual(resume.call_args.args[0]["id"], row_id)
        # Completion can arrive between a scene being painted and its click.
        # Re-read current state so that click cannot restart a finished download.
        app.store.update(row_id, state="complete")
        with patch.object(app, "delete_job") as remove, patch.object(app, "resume_media") as resume:
            button.invoke()
            remove.assert_called_once_with(row_id, False)
            resume.assert_not_called()
        app.journal_action(row_id)
        app.journal_action(row_id)
        self.assertEqual(app.store.all(), [])

    def test_paused_download_can_be_removed_without_resuming(self):
        from pathlib import Path

        app = self.app
        existing = Path(self.folder.name)/"keep.iso"
        existing.write_bytes(b"existing file")
        row = app.store.create("https://example.com/keep.iso", self.folder.name, existing.name)
        app.store.update(row["id"], state="paused")
        self.pump(.6)
        self.assertEqual(app.row_more_buttons[row["id"]].label, "Tiếp tục")
        surface = app.presentation_surface
        self.assertIn(row["id"], getattr(app, "row_remove_buttons", {}), "Paused downloads need a visible Remove action")
        remove = app.row_remove_buttons[row["id"]]
        x, y, width, height = next(region[1] for region in surface.regions if region[0] is remove)
        surface.event_generate("<Button-1>", x=x+width//2, y=y+height//2)
        self.pump(.6)
        self.assertEqual(app.store.all(), [])
        self.assertEqual(existing.read_bytes(), b"existing file")
        self.assertNotIn(row["id"], app.manager.active)

    def test_completed_download_has_scan_icon_next_to_done_instead_of_check_column(self):
        from pathlib import Path
        from unittest.mock import patch

        app = self.app
        target = Path(self.folder.name)/"sample.bin"
        target.write_bytes(b"fixture")
        row = app.store.create("https://example.com/sample.bin", target.parent, target.name)
        self.pump(.6)
        self.assertNotIn(row["id"], app.row_safety_buttons)
        app.store.update(row["id"], state="complete", output=str(target))
        self.pump(.6)
        self.assertNotIn("check", app.table.cget("columns"))
        button = app.row_safety_buttons[row["id"]]
        self.assertEqual(button.label, "")
        self.assertIsNotNone(button.image)
        status = app.row_cell_labels[row["id"], "status"]
        self.assertGreaterEqual(button.winfo_x(), status.winfo_x()+status.winfo_width())
        self.assertEqual(button.winfo_x()-status.winfo_x()-status.winfo_width(), 18)
        self.assertIn((row["id"], "status_separator"), app.row_cell_labels)
        with patch.object(app, "check_selected_safety") as scan:
            button.invoke()
            scan.assert_called_once_with(row["id"])

    def test_manual_defender_scan_quarantines_flagged_file_with_automatic_checks_off(self):
        from pathlib import Path
        from types import SimpleNamespace
        from unittest.mock import patch

        app = self.app
        app.store.set_setting("auto_defender", False)
        app.store.set_setting("high_security", False)
        target = Path(self.folder.name)/"flagged.bin"
        target.write_bytes(b"synthetic fixture")
        row = app.store.create("https://example.com/flagged.bin", target.parent, target.name)
        app.store.update(row["id"], state="complete", output=str(target))
        with patch("hngoos_dm.app.scan_defender", return_value=SimpleNamespace(returncode=2, stdout="Threat", stderr="")):
            app.check_selected_safety(row["id"])
            self.pump(1)
        job = app.store.get(row["id"])
        self.assertEqual(job["state"], "quarantined")
        self.assertEqual(job["safety_check"]["status"], "threat")
        self.assertFalse(target.exists())
        self.assertEqual(Path(job["output"]).read_bytes(), b"synthetic fixture")

    def test_media_preview_uses_only_explicit_browser_session_for_the_same_url(self):
        from pathlib import Path
        from unittest.mock import patch

        app = self.app
        cookie_files, captured = [], []
        def describe(url, **options):
            path = options.get("cookie_file")
            if path:
                cookie_files.append(Path(path))
                captured.append("session\texplicit-value" in Path(path).read_text(encoding="utf-8"))
            else:
                captured.append(False)
            return {"kind": "media", "original": url, "url": url, "filename": "Audio.m4a", "formats": []}
        for same_url in (True, False):
            app.cancel_download()
            url = "https://zingmp3.vn/bai-hat/example/test.html"
            app.url.set(url)
            app.browser_session = "encrypted fixture"
            app.browser_session_url = url if same_url else "https://example.com/other"
            with patch("hngoos_dm.vault.decrypt", return_value=[{"domain": ".zingmp3.vn", "name": "session", "value": "explicit-value"}]), \
                    patch("hngoos_dm.links.describe_source", side_effect=describe):
                app.prepare_download()
                self.pump(.8)
            self.assertEqual(captured[-1], same_url)
        self.assertTrue(cookie_files)
        self.assertTrue(all(not path.exists() for path in cookie_files))

    @unittest.skipUnless(sys.platform == "win32", "Windows Defender integration")
    def test_automatic_media_defender_result_is_preserved_beside_done(self):
        import time
        from pathlib import Path
        from types import SimpleNamespace
        from unittest.mock import patch

        app = self.app
        app.store.set_setting("auto_defender", True)
        app.store.set_setting("high_security", False)
        app.media_url.set("https://example.com/clip.mp4")
        app.filename.set("clip.mp4")
        def extract(_url, staging, *_args):
            (staging/"clip.mp4").write_bytes(b"video fixture")
        with patch("hngoos_dm.media._download_video", side_effect=extract), \
                patch("hngoos_dm.safety.scan_defender", return_value=SimpleNamespace(returncode=0, stdout="", stderr="")), \
                patch("hngoos_dm.app.scan_defender", return_value=SimpleNamespace(returncode=0, stdout="", stderr="")):
            app.start_media("")
            deadline = time.monotonic()+5
            while time.monotonic() < deadline:
                self.pump(.05)
                if app.store.get(app.media_job_id).get("safety_check", {}).get("status") == "clean":
                    break
        job = app.store.get(app.media_job_id)
        self.assertEqual(job["state"], "complete", job.get("error"))
        self.assertEqual(job.get("safety_check", {}).get("status"), "clean")
        self.assertEqual(app.safety_status(job), "An toàn")
        self.assertTrue(Path(job["output"]).is_file())

    def test_failed_scan_can_be_retried_from_the_done_row(self):
        from pathlib import Path
        from types import SimpleNamespace
        from unittest.mock import patch

        app = self.app
        path = Path(self.folder.name)/"retry.txt"
        path.write_text("scan fixture")
        row = app.store.create("https://example.com/retry.txt", path.parent, path.name)
        app.store.update(row["id"], state="complete", output=str(path),
                         safety_check={"provider": "defender", "status": "error", "detail": "Previous scan interrupted"})
        self.pump(.6)
        self.assertIn(row["id"], app.row_safety_buttons)
        with patch("hngoos_dm.app.scan_defender", return_value=SimpleNamespace(returncode=0, stdout="", stderr="")):
            app.row_safety_buttons[row["id"]].invoke()
            self.pump(.7)
        self.assertEqual(app.store.get(row["id"])["safety_check"]["status"], "clean")

    def test_removing_active_download_waits_for_worker_before_removing_history(self):
        import threading
        from unittest.mock import patch

        from hngoos_dm.engine import Paused

        app = self.app
        stopped, release = threading.Event(), threading.Event()

        def download(_job_id, stop):
            stop.wait(5)
            stopped.set()
            release.wait(5)
            raise Paused()

        try:
            with patch.object(app.manager, "_download", side_effect=download):
                row = app.store.create("https://example.com/large.iso", self.folder.name, "large.iso")
                app.manager.start(row["id"])
                self.pump(.6)
                self.assertIn(row["id"], getattr(app, "row_remove_buttons", {}), "Active downloads need a visible Remove action")
                app.row_remove_buttons[row["id"]].invoke()
                self.assertTrue(stopped.wait(2))
                self.assertEqual(app.store.get(row["id"])["id"], row["id"])
                app.journal_action(row["id"])
                release.set()
                self.pump(1)
                self.assertEqual(app.store.all(), [])
                self.assertNotIn(row["id"], app.manager.active)
        finally:
            release.set()

