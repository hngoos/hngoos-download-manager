"""Local seller print archive: static HTML only, isolated browser, no outgoing requests."""

import html
import tempfile
import threading
from datetime import datetime
from pathlib import Path

from .files import publish
from .invoice_rules import validate_invoice

RENDER_LOCK = threading.Lock()


def save_invoice(url, markup, order_id, directory, channel="msedge"):
    from playwright.sync_api import Error, sync_playwright

    site, order_id = validate_invoice(url, markup, order_id)
    now = datetime.now().astimezone()
    folder = Path(directory)/site/now.strftime("%Y-%m-%d")
    folder.mkdir(parents=True, exist_ok=True)
    policy = "default-src 'none'; img-src data:; style-src 'unsafe-inline'; font-src 'none'; base-uri 'none'; form-action 'none'"
    document = ('<!doctype html><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="'+policy+'">'
                '<style>body{font:12px Arial;color:#111;background:white}header{font-size:9px;overflow-wrap:anywhere;'
                'border-bottom:1px solid #ccc;padding-bottom:8px;margin-bottom:12px}img{max-width:100%}</style>'
                f'<header>{html.escape(url)}<br>{now.isoformat(timespec="seconds")}</header>'+markup)
    with RENDER_LOCK, sync_playwright() as playwright, tempfile.TemporaryDirectory(prefix=".hdm-invoice-", dir=folder) as temporary:
        try:
            browser = playwright.chromium.launch(channel=channel, headless=True) if channel else playwright.chromium.launch(headless=True)
        except Error:
            browser = playwright.chromium.launch(headless=True)
        try:
            context = browser.new_context(java_script_enabled=False, service_workers="block")
            context.route("**/*", lambda route: route.abort())
            page = context.new_page()
            page.set_content(document, wait_until="domcontentloaded", timeout=15000)
            output = Path(temporary)/"invoice.pdf"
            page.pdf(path=str(output), format="A4", print_background=True,
                     margin={"top": "12mm", "bottom": "12mm", "left": "10mm", "right": "10mm"})
        finally:
            browser.close()
        return publish(output, folder, f"{order_id}-{now:%H%M%S}.pdf")
