"""Resolve supported cloud-sharing pages without bypassing authentication."""

import re
from urllib.parse import parse_qs, quote, urlencode, urlsplit, urlunsplit

from .safety import validate_url


def resolve(url):
    url = validate_url(url)
    parsed = urlsplit(url)
    host = parsed.hostname.lower()
    if host in {"drive.google.com", "docs.google.com"}:
        match = re.search(r"/file/d/([a-zA-Z0-9_-]+)", parsed.path)
        file_id = match[1] if match else parse_qs(parsed.query).get("id", [""])[0]
        if not file_id or not re.fullmatch(r"[a-zA-Z0-9_-]+", file_id):
            raise ValueError("Link Google Drive chưa có ID tệp.")
        return "https://drive.usercontent.google.com/download?" + urlencode({"id": file_id, "export": "download", "confirm": "t"})
    if host in {"www.dropbox.com", "dropbox.com"}:
        params = parse_qs(parsed.query)
        params.pop("dl", None)
        params["raw"] = ["1"]
        return urlunsplit(("https", parsed.netloc, parsed.path, urlencode(params, doseq=True), ""))
    if host in {"onedrive.live.com", "1drv.ms"}:
        import base64
        encoded = base64.urlsafe_b64encode(url.encode()).decode().rstrip("=")
        return f"https://api.onedrive.com/v1.0/shares/u!{quote(encoded)}/root/content"
    # MediaFire requires parsing a public page. Never follow JavaScript or supply account cookies.
    if host in {"www.mediafire.com", "mediafire.com"} and parsed.path.startswith("/file/"):
        import html

        from .engine import request
        with request(url) as response:
            text = response.read(2 * 1024 * 1024).decode("utf-8", errors="replace")
        for tag in re.findall(r"<a\b[^>]+>", text, re.IGNORECASE):
            if re.search(r'id=[\"\']downloadButton[\"\']', tag, re.IGNORECASE):
                match = re.search(r'href=[\"\']([^\"\']+)', tag, re.IGNORECASE)
                if match:
                    direct = validate_url(html.unescape(match[1]))
                    if urlsplit(direct).hostname.endswith(".mediafire.com"):
                        return direct
        raise ValueError("Không tìm thấy link MediaFire công khai; có thể trang cần xác minh hoặc đăng nhập.")
    return url
