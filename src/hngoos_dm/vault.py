"""Windows DPAPI storage for browser session data, scoped to the current Windows user."""

import base64
import ctypes
import json
import os
from ctypes import wintypes


class Blob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]


def transform(data, decrypt=False):
    if os.name != "nt":
        raise ValueError("Dữ liệu đăng nhập trình duyệt chỉ được lưu khi có Windows DPAPI.")
    buffer = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    target = Blob()
    if decrypt:
        ok = ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(source), None, None, None, None, 0, ctypes.byref(target))
    else:
        ok = ctypes.windll.crypt32.CryptProtectData(ctypes.byref(source), "HDM browser session", None, None, None, 0, ctypes.byref(target))
    if not ok:
        raise ctypes.WinError()
    try:
        return ctypes.string_at(target.pbData, target.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(target.pbData)


def encrypt(value):
    return base64.b64encode(transform(json.dumps(value).encode("utf-8"))).decode("ascii")


def decrypt(value):
    return json.loads(transform(base64.b64decode(value, validate=True), decrypt=True))


def cookie_jar(cookies):
    lines = ["# Netscape HTTP Cookie File", "# Temporary session supplied explicitly by the user"]
    for cookie in cookies:
        domain = cookie["domain"]
        if cookie.get("httpOnly"):
            domain = "#HttpOnly_" + domain
        lines.append("\t".join((domain, "TRUE" if cookie["domain"].startswith(".") else "FALSE",
                                cookie.get("path", "/"), "TRUE" if cookie.get("secure") else "FALSE",
                                str(int(cookie.get("expirationDate", 0))), cookie["name"], cookie["value"])))
    return "\n".join(lines)+"\n"
