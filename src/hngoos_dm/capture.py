"""User-requested web capture with source URL and local timestamp recorded."""

import html
import tempfile
from datetime import datetime
from pathlib import Path

from .files import publish
from .safety import validate_url


def capture_page(url, destination, image=False, channel="msedge"):
    from playwright.sync_api import sync_playwright
    url = validate_url(url)
    destination = Path(destination).resolve()
    if destination.exists():
        raise ValueError("Đầu ra đã tồn tại; chọn tên mới.")
    stamp = datetime.now().astimezone().isoformat(timespec="seconds")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright, tempfile.TemporaryDirectory(
            prefix=".hngoos-capture-", dir=destination.parent) as folder:
        launch = {"headless": True}
        if channel:
            launch["channel"] = channel
        try:
            browser = playwright.chromium.launch(**launch)
        except Exception:
            if not channel:
                raise
            browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(1000)
            staged = Path(folder) / ("capture.png" if image else "capture.pdf")
            if image:
                page.evaluate("""({url, stamp}) => {
                    const note = document.createElement('div');
                    note.textContent = 'Nguồn: ' + url + ' | Lưu lúc: ' + stamp;
                    note.style.cssText = 'display:block;background:white;color:black;padding:12px;font:14px sans-serif;position:relative;z-index:2147483647;overflow-wrap:anywhere';
                    document.body.prepend(note);
                }""", {"url": url, "stamp": stamp})
                page.screenshot(path=str(staged), full_page=True, timeout=45000)
            else:
                header = ("<div style='font-size:8px;width:100%;padding:0 20px;overflow-wrap:anywhere'>"
                          f"Nguồn: {html.escape(url)} | Lưu lúc: {stamp}</div>")
                page.pdf(path=str(staged), print_background=True, display_header_footer=True,
                         header_template=header, footer_template="<span></span>",
                         margin={"top": "65px", "bottom": "25px", "left": "20px", "right": "20px"})
            return publish(staged, destination.parent, destination.name)
        finally:
            browser.close()
