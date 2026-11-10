"""Read public TikTok photo albums from TikTok's own embed metadata."""

import json
import re
from urllib.parse import urlsplit

from .safety import validate_url


def photo_id(url):
    parsed = urlsplit(validate_url(url))
    if (parsed.hostname or "").lower().rstrip(".") not in {"tiktok.com", "www.tiktok.com", "m.tiktok.com"}:
        return None
    match = re.fullmatch(r"/@[^/]+/photo/(\d+)/?", parsed.path)
    return match[1] if match else None


def parse_embed(html, identifier):
    match = re.search(r'<script\b[^>]*\bid=["\']__FRONTITY_CONNECT_STATE__["\'][^>]*>(.*?)</script>', html, re.DOTALL)
    if not match:
        raise ValueError("TikTok chưa cung cấp dữ liệu ảnh công khai. Hãy thử lại hoặc kiểm tra quyền truy cập.")
    data = json.loads(match[1])
    page = data.get("source", {}).get("data", {}).get("/embed/"+identifier, {})
    video = page.get("videoData") or {}
    item = video.get("itemInfos") or {}
    source = (video.get("imagePostInfo") or {}).get("displayImages") or []
    if str(item.get("id")) != identifier or not source:
        raise ValueError("Không tìm thấy ảnh công khai của bài đăng TikTok này.")
    images = []
    for image in source:
        candidates = []
        for url in image.get("urlList") or []:
            parsed = urlsplit(validate_url(url))
            host = (parsed.hostname or "").lower()
            if parsed.scheme == "https" and any(host.endswith("."+domain) for domain in
                    ("tiktokcdn.com", "tiktokcdn-us.com", "tiktokcdn-eu.com", "ibytedtos.com")):
                candidates.append(url)
        if not candidates:
            raise ValueError("TikTok chưa cung cấp đường dẫn tải cho tất cả ảnh trong bài đăng.")
        extension = urlsplit(candidates[0]).path.rsplit(".", 1)[-1].lower()
        extension = "jpg" if extension == "jpeg" else extension
        if extension not in {"jpg", "png", "webp", "avif"}:
            raise ValueError("Định dạng ảnh TikTok chưa được hỗ trợ.")
        images.append({"url": candidates[0], "ext": extension})
    return {"title": item.get("text", "").strip() or "TikTok "+identifier, "images": images}


def describe_album(url, proxy=None):
    from .engine import request

    identifier = photo_id(url)
    if not identifier:
        raise ValueError("Link bài đăng ảnh TikTok không hợp lệ.")
    # The public embed carries the full photo list even when the desktop page
    # serves only an application shell. No third-party downloader or cookies.
    with request("https://www.tiktok.com/embed/"+identifier,
                 {"User-Agent": "Mozilla/5.0", "Referer": "https://www.tiktok.com/"}, proxy=proxy) as response:
        payload = response.read(4*1024*1024+1)
    if len(payload) > 4*1024*1024:
        raise ValueError("Dữ liệu bài đăng TikTok vượt quá giới hạn.")
    return parse_embed(payload.decode("utf-8"), identifier)
