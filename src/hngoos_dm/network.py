"""Per-request proxy policy; never change the operating system's proxy settings."""

import urllib.request
from urllib.parse import urlsplit


def validate_proxy(value):
    if not isinstance(value, dict) or value.get("mode", "direct") not in {"system", "direct", "manual"}:
        raise ValueError("Cấu hình proxy không hợp lệ.")
    mode, url = value.get("mode", "direct"), str(value.get("url", "")).strip()
    if mode == "manual":
        try:
            parsed = urlsplit(url)
            valid = (parsed.scheme in {"http", "https"} and parsed.hostname and parsed.port
                     and not parsed.username and not parsed.password and parsed.path in {"", "/"}
                     and not parsed.query and not parsed.fragment and not any(char.isspace() for char in url))
        except ValueError:
            valid = False
        if not valid:
            raise ValueError("Nhập proxy HTTP(S) dạng http://máy-chủ:cổng, không kèm tài khoản hoặc đường dẫn.")
    return {"mode": mode, "url": url if mode == "manual" else ""}


def media_proxy(value):
    policy = validate_proxy(value or {})
    return None if policy["mode"] == "system" else policy["url"]


def open_url(request, timeout=15, proxy=None):
    policy = validate_proxy(proxy or {})
    if policy["mode"] == "system":
        return urllib.request.urlopen(request, timeout=timeout)
    proxies = {} if policy["mode"] == "direct" else {"http": policy["url"], "https": policy["url"]}
    return urllib.request.build_opener(urllib.request.ProxyHandler(proxies)).open(request, timeout=timeout)
