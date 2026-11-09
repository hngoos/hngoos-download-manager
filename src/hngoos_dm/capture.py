"""User-requested web capture with source URL and local timestamp recorded."""

import html
import json
import tempfile
import time
from datetime import datetime
from pathlib import Path

from .files import publish
from .safety import validate_url


def capture_page(url, destination, image=False, channel="msedge"):
    from .browser_render import BrowserPage
    url = validate_url(url)
    destination = Path(destination).resolve()
    if destination.exists():
        raise ValueError("Đầu ra đã tồn tại; chọn tên mới.")
    stamp = datetime.now().astimezone().isoformat(timespec="seconds")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with BrowserPage(channel) as page, tempfile.TemporaryDirectory(
            prefix=".hngoos-capture-", dir=destination.parent) as folder:
        page.navigate(url)
        time.sleep(1)  # Allow lazy page content, matching the previous capture backend.
        staged = Path(folder) / ("capture.png" if image else "capture.pdf")
        if image:
            page.evaluate("""(({url, stamp}) => {
                    const note = document.createElement('div');
                    note.textContent = 'Nguồn: ' + url + ' | Lưu lúc: ' + stamp;
                    note.style.cssText = 'display:block;background:white;color:black;padding:12px;font:14px sans-serif;position:relative;z-index:2147483647;overflow-wrap:anywhere';
                    document.body.prepend(note);
                })("""+json.dumps({"url": url, "stamp": stamp})+")")
            page.screenshot(staged)
        else:
            header = ("<div style='font-size:8px;width:100%;padding:0 20px;overflow-wrap:anywhere'>"
                      f"Nguồn: {html.escape(url)} | Lưu lúc: {stamp}</div>")
            page.pdf(staged, header=header,
                     margins={"top": 65/96, "bottom": 25/96, "left": 20/96, "right": 20/96})
        return publish(staged, destination.parent, destination.name)
