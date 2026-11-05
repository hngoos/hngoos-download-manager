"""Bounded native messaging: durable URL requests and opt-in DPAPI session storage."""

import json
import os
import struct
import subprocess
import sys
import uuid
from pathlib import Path
from urllib.parse import urlsplit

from .paths import data_directory
from .safety import safe_filename, validate_url
from .store import Store

MAX_MESSAGE = 128 * 1024


def read_message(stream):
    header = stream.read(4)
    if not header:
        return None
    if len(header) != 4:
        raise ValueError("Incomplete native message header")
    length = struct.unpack("<I", header)[0]
    if length > MAX_MESSAGE:
        raise ValueError("Native message too large")
    data = stream.read(length)
    if len(data) != length:
        raise ValueError("Incomplete native message")
    value = json.loads(data)
    if not isinstance(value, dict):
        raise TypeError("Native message must be an object")
    return value


def write_message(stream, value):
    data = json.dumps(value, ensure_ascii=False).encode("utf-8")
    stream.write(struct.pack("<I", len(data)))
    stream.write(data)
    stream.flush()


def handle_message(message, store):
    if message.get("action") == "ping":
        return {"ok": True, "protocol": 1}
    if message.get("action") == "save-invoice":
        from .invoice_rules import validate_invoice
        url = validate_url(str(message.get("url", "")))
        site, order_id = validate_invoice(url, message.get("html"), message.get("order_id"))
        request_id = str(message.get("id") or uuid.uuid4().hex)[:100]
        inserted = store.enqueue(request_id, {"kind": "invoice", "url": url, "site": site,
            "order_id": order_id, "html": message["html"], "origin": "browser"})
        return {"ok": True, "queued": True, "id": request_id, "duplicate": not inserted}
    if message.get("action") != "download":
        raise ValueError("Unsupported native action")
    url = validate_url(str(message.get("url", "")))
    if len(url) > 32768:
        raise ValueError("URL too long")
    kind = message.get("kind", "file")
    if kind not in {"file", "video"}:
        raise ValueError("Unsupported download kind")
    filename = str(message.get("filename", ""))
    if message.get("takeover"):
        from .engine import probe
        info = probe(url)
        filename = filename or info.get("filename", "")
        expected_size = message.get("expected_size", 0)
        if (not isinstance(expected_size, (int, float)) or expected_size < 0
                or (expected_size and info["total"] != expected_size)):
            raise ValueError("Không xác minh được kích thước nguồn; trình duyệt giữ lượt tải.")
    request_id = str(message.get("id") or uuid.uuid4().hex)
    if len(request_id) > 100:
        raise ValueError("Request id too long")
    data = {"url": url, "filename": safe_filename(filename) if filename else "", "kind": kind, "origin": "browser"}
    if kind == "video" and message.get("referrer"):
        referrer = validate_url(str(message["referrer"]))
        if len(referrer) > 8192:
            raise ValueError("Referrer too long")
        # Keep only the website origin, never a private page path or query token.
        parts = urlsplit(referrer)
        data["referrer"] = f"{parts.scheme}://{parts.netloc}/"
    cookies = message.get("cookies", [])
    if isinstance(cookies, list) and cookies:
        if len(cookies) > 500 or kind != "video":
            raise ValueError("Session cookies are only accepted for an explicit video request")
        host = urlsplit(url).hostname.lower()
        for cookie in cookies:
            if not isinstance(cookie, dict):
                raise TypeError("Cookie must be an object")
            domain = str(cookie.get("domain", "")).lstrip(".").lower()
            if not domain or not (host == domain or host.endswith("."+domain)):
                raise ValueError("Cookie is outside the requested website")
            if any(char in str(cookie.get(key, "")) for key in ("domain", "path", "name", "value") for char in "\r\n\t"):
                raise ValueError("Cookie contains control characters")
            if not isinstance(cookie.get("name"), str) or not isinstance(cookie.get("value"), str):
                raise TypeError("Cookie name/value must be strings")
        from .vault import encrypt
        data["session_dpapi"] = encrypt(cookies)
    inserted = store.enqueue(request_id, data)
    return {"ok": True, "id": request_id, "queued": True, "duplicate": not inserted}


def launch_app():
    if os.name != "nt" and os.environ.get("APPIMAGE"):
        executable = Path(os.environ["APPIMAGE"])
        if executable.is_file():
            subprocess.Popen([str(executable)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return
    if getattr(sys, "frozen", False):
        executable = Path(sys.executable).with_name("HDM.exe" if os.name == "nt" else "HDM")
        if sys.platform == "darwin":
            executable = Path(sys.executable).parents[1]/"MacOS/HDM"
        if executable.is_file():
            subprocess.Popen([str(executable)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             creationflags=0x08000000 if os.name == "nt" else 0)
    else:
        subprocess.Popen([sys.executable, "-m", "hngoos_dm"], stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, creationflags=0x08000000 if os.name == "nt" else 0)


def main():
    if os.name == "nt":
        import msvcrt
        msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
        msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
    data_dir = data_directory()
    store = Store(data_dir / "downloads.sqlite3")
    while True:
        try:
            message = read_message(sys.stdin.buffer)
            if message is None:
                return
            response = handle_message(message, store)
            if response.get("queued"):
                # The app starts only for a user-initiated download, never for a ping.
                if not (data_dir / "instance.lock").exists():
                    launch_app()
                else:
                    from .instance import InstanceLock
                    try:
                        lock = InstanceLock(data_dir / "instance.lock")
                    except RuntimeError:
                        pass
                    else:
                        lock.close()
                        launch_app()
            write_message(sys.stdout.buffer, response)
        except (ValueError, TypeError, OSError) as exc:
            write_message(sys.stdout.buffer, {"ok": False, "error": str(exc)})
            return
