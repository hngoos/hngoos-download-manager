"""Real rendering contract for the small installed-browser backend."""

import os
import tempfile
import unittest
from pathlib import Path


@unittest.skipUnless(os.environ.get("HNGOOS_BROWSER_TESTS") == "1", "Requires installed Chromium")
class BrowserRenderTests(unittest.TestCase):
    def test_static_document_pdf_and_screenshot_and_profile_cleanup(self):
        from PIL import Image

        from hngoos_dm import browser_render
        from hngoos_dm.pdf_tools import open_pdf

        with tempfile.TemporaryDirectory() as folder:
            pdf = Path(folder)/"page.pdf"
            png = Path(folder)/"page.png"
            with browser_render.BrowserPage() as page:
                profile = page.profile
                page.set_content("<h1>HDM small renderer</h1><div style='height:1400px'>Long page</div>")
                page.pdf(pdf)
                page.screenshot(png)
            self.assertFalse(profile.exists(), "Temporary browser profile must be removed")
            self.assertIsNotNone(page.process.poll(), "Owned browser must exit")
            with open_pdf(pdf) as document:
                first = document[0]
                text = first.get_textpage()
                try:
                    self.assertIn("HDM small renderer", text.get_text_range())
                finally:
                    text.close()
                    first.close()
            with Image.open(png) as image:
                self.assertEqual(image.width, 1280)
                self.assertGreaterEqual(image.height, 1400)

    def test_navigation_capture_preserves_source_and_rejects_overwrite(self):
        import threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

        from hngoos_dm.capture import capture_page
        from hngoos_dm.pdf_tools import open_pdf

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"<h1>HDM web capture fixture</h1>")

            def log_message(self, *_args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            with tempfile.TemporaryDirectory() as folder:
                target = Path(folder)/"capture.pdf"
                url = f"http://127.0.0.1:{server.server_port}/fixture"
                capture_page(url, target)
                with open_pdf(target) as document:
                    first = document[0]
                    text = first.get_textpage()
                    try:
                        value = text.get_text_range()
                    finally:
                        text.close()
                        first.close()
                self.assertIn("HDM web capture fixture", value)
                self.assertIn(url, value)
                with self.assertRaises(ValueError):
                    capture_page(url, target)
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=5)

    def test_failed_start_removes_owned_profile(self):
        from hngoos_dm import browser_render

        page = browser_render.BrowserPage(executable=Path("missing-hdm-browser.exe"), timeout=0.5)
        with self.assertRaises(OSError), page:
            self.fail("Missing browser must fail before entering")
        self.assertFalse(page.profile.exists())
