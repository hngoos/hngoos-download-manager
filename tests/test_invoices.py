"""Seller archive validation, durable queue and isolated PDF output."""

import os
import tempfile
import unittest
from pathlib import Path

from hngoos_dm.bridge import handle_message
from hngoos_dm.invoices import validate_invoice
from hngoos_dm.store import Store


class InvoiceTests(unittest.TestCase):
    def test_queue_preserves_print_until_success_and_scrubs_accepted_html(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder)/"state.sqlite3")
            message = {"action": "save-invoice", "id": "print-1", "url": "https://sellercenter.lazada.vn/orders",
                       "order_id": "ORDER-12345", "html": "<h1>ORDER-12345</h1>"}
            self.assertTrue(handle_message(message, store)["ok"])
            self.assertTrue(handle_message(message, store)["duplicate"])
            store.acknowledge("print-1", "reviewing")
            self.assertEqual(store.inbox(), [])
            store.recover()
            self.assertEqual(store.inbox()[0][1]["html"], message["html"])
            store.acknowledge("print-1")
            with store.connect() as db:
                retained = db.execute("SELECT data FROM inbox WHERE id='print-1'").fetchone()[0]
            self.assertNotIn("<h1>", retained)

    def test_reject_untrusted_hosts_http_and_oversize(self):
        for url in ("https://sellercenter.lazada.vn.evil.test/", "https://example.com/", "http://seller.shopee.vn/"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_invoice(url, "<h1>Order</h1>", "001")
        with self.assertRaises(ValueError):
            validate_invoice("https://seller.shopee.vn/", "x"*90001, "001")

    @unittest.skipUnless(os.environ.get("HNGOOS_BROWSER_TESTS") == "1", "Requires Playwright Chromium")
    def test_pdf_archives_order_without_running_script_or_loading_network(self):
        import threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

        import pypdfium2 as pdfium

        from hngoos_dm.invoices import save_invoice
        requests = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass
            def do_GET(self):
                requests.append(self.path)
                self.send_response(200)
                self.end_headers()
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with tempfile.TemporaryDirectory() as folder:
                remote = f"http://127.0.0.1:{server.server_port}"
                markup = ("<h1>ORDER-12345</h1><p>Fixture receipt</p>"
                          f'<img src="{remote}/image"><iframe src="{remote}/frame"></iframe>'
                          f'<script>fetch("{remote}/script");document.body.innerHTML="BAD SCRIPT"</script>')
                output = save_invoice("https://sellercenter.lazada.vn/orders", markup, "ORDER-12345", folder, channel=None)
                self.assertEqual(output.parent.parent.name, "Lazada")
                with pdfium.PdfDocument(output) as pdf:
                    page = pdf[0]
                    text = page.get_textpage()
                    value = text.get_text_range()
                    text.close()
                    page.close()
                self.assertIn("ORDER-12345", value)
                self.assertIn("sellercenter.lazada.vn/orders", value)
                self.assertNotIn("BAD SCRIPT", value)
                self.assertEqual(requests, [])
        finally:
            server.shutdown()
            server.server_close()
