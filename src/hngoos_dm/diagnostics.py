"""Offline acceptance checks that also run inside the distributed executable."""

import json
import tempfile
import traceback
from pathlib import Path

from . import __version__


def check_media(folder):
    import threading
    from functools import partial
    from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

    from yt_dlp import YoutubeDL

    from .media import MediaOptions, find_ffmpeg, ydl_options
    from .processing import inspect_media, run_ffmpeg

    source = run_ffmpeg(["-f", "lavfi", "-i", "color=c=blue:s=160x120:r=10",
                        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100",
                        "-t", "1", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac"],
                       folder/"source.mp4")
    class Handler(SimpleHTTPRequestHandler):
        def log_message(self, *_args):
            pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(Handler, directory=str(folder)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        target = folder/"download"
        target.mkdir()
        settings = ydl_options(target, MediaOptions(audio="mp3"), find_ffmpeg())
        with YoutubeDL(settings) as downloader:
            downloader.download([f"http://127.0.0.1:{server.server_port}/{source.name}"])
        outputs = list(target.glob("*.mp3"))
        if len(outputs) != 1 or not inspect_media(outputs[0])["audio"]:
            raise RuntimeError("yt-dlp/FFmpeg did not produce a readable MP3")
    finally:
        server.shutdown()
        server.server_close()


def check_pdf(folder):
    from PIL import Image

    from .pdf_tools import open_pdf, redact

    source = folder/"original.pdf"
    with Image.new("RGB", (100, 100), "white") as image:
        image.save(source, "PDF")
    output = redact(source, folder/"redacted.pdf", {0: [(0.1, 0.1, 0.9, 0.9)]})
    with open_pdf(output) as document:
        page = document[0]
        bitmap = page.render()
        try:
            with bitmap.to_pil().copy() as image:
                if max(image.convert("RGB").getpixel((50, 50))) > 10:
                    raise RuntimeError("Redacted region is not black")
        finally:
            bitmap.close()
            page.close()


def check_spreadsheet(folder):
    import openpyxl

    source = folder/"list.xlsx"
    book = openpyxl.Workbook()
    book.active.append(["https://example.com/file", "example"])
    book.save(source)
    book.close()
    book = openpyxl.load_workbook(source, read_only=True)
    try:
        if book.active.cell(1, 2).value != "example":
            raise RuntimeError("XLSX round trip failed")
    finally:
        book.close()


def check_signatures(_folder):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    private = Ed25519PrivateKey.generate()
    message = b"HDM packaged diagnostic"
    private.public_key().verify(private.sign(message), message)


def check_torrent(_folder):
    import libtorrent as lt

    encoded = lt.bencode({"name": "diagnostic", "length": 1})
    if lt.bdecode(encoded)[b"length"] != 1:
        raise RuntimeError("libtorrent native module failed")


def check_tray(_folder):
    import pystray

    if not callable(pystray.Icon):
        raise TypeError("System tray backend is unavailable")


def check_browser(folder):
    from playwright.sync_api import Error, sync_playwright

    from .pdf_tools import open_pdf

    # Use installed Edge with an isolated temporary profile, as web capture does.
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(channel="msedge", headless=True)
        except Error:
            browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.set_content("<h1>HNGOOS-PACKAGED-CAPTURE</h1>")
            output = folder/"browser.pdf"
            page.pdf(path=str(output))
        finally:
            browser.close()
    with open_pdf(output) as document:
        page = document[0]
        text = page.get_textpage()
        try:
            if "HNGOOS-PACKAGED-CAPTURE" not in text.get_text_range():
                raise RuntimeError("Browser PDF lacks page content")
        finally:
            text.close()
            page.close()


def run_diagnostics(report_path):
    """Write results without touching user settings, accounts, or downloaded files."""
    report = {"version": __version__, "checks": {}}
    with tempfile.TemporaryDirectory(prefix="hngoos-diagnostic-") as temporary:
        for name, check in (("media", check_media), ("pdf", check_pdf), ("xlsx", check_spreadsheet),
                            ("signatures", check_signatures), ("torrent", check_torrent),
                            ("tray", check_tray), ("browser", check_browser)):
            folder = Path(temporary)/name
            folder.mkdir()
            try:
                check(folder)
                report["checks"][name] = {"ok": True}
            except Exception:  # noqa: BLE001 -- record each independent failure for build diagnostics
                report["checks"][name] = {"ok": False, "error": traceback.format_exc()}
    report["ok"] = all(result["ok"] for result in report["checks"].values())
    Path(report_path).write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0 if report["ok"] else 1
