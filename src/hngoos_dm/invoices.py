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
    from .browser_render import BrowserPage

    site, order_id = validate_invoice(url, markup, order_id)
    now = datetime.now().astimezone()
    folder = Path(directory)/site/now.strftime("%Y-%m-%d")
    folder.mkdir(parents=True, exist_ok=True)
    policy = "default-src 'none'; img-src data:; style-src 'unsafe-inline'; font-src 'none'; base-uri 'none'; form-action 'none'"
    document = ('<!doctype html><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="'+policy+'">'
                '<style>body{font:12px Arial;color:#111;background:white}header{font-size:9px;overflow-wrap:anywhere;'
                'border-bottom:1px solid #ccc;padding-bottom:8px;margin-bottom:12px}img{max-width:100%}</style>'
                f'<header>{html.escape(url)}<br>{now.isoformat(timespec="seconds")}</header>'+markup)
    with RENDER_LOCK, BrowserPage(channel, timeout=15) as page, tempfile.TemporaryDirectory(prefix=".hdm-invoice-", dir=folder) as temporary:
        page.set_content(document, isolated=True)
        output = Path(temporary)/"invoice.pdf"
        page.pdf(output, a4=True, margins={"top": 12/25.4, "bottom": 12/25.4,
                                         "left": 10/25.4, "right": 10/25.4})
        return publish(output, folder, f"{order_id}-{now:%H%M%S}.pdf")
