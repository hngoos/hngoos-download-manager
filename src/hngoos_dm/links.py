"""Local link recognition; clipboard inspection never makes network requests."""

from pathlib import PurePosixPath
from urllib.parse import parse_qs, urlsplit

from .safety import validate_url

MEDIA_HOSTS = (
    "youtube.com", "youtu.be", "facebook.com", "fb.watch", "instagram.com", "tiktok.com",
    "twitter.com", "x.com", "threads.net", "threads.com", "bilibili.com", "b23.tv",
    "douyin.com", "soundcloud.com", "vimeo.com", "dailymotion.com", "twitch.tv",
    "pinterest.com", "pin.it", "zingmp3.vn",
)


def link_kind(value):
    parsed = urlsplit(value.strip())
    host = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme.lower() == "magnet":
        if not any(value.startswith(("urn:btih:", "urn:btmh:")) for value in parse_qs(parsed.query).get("xt", [])):
            raise ValueError("Magnet cần có mã nhận diện torrent hợp lệ.")
        return "torrent"
    validate_url(value)
    if host == "spotify.link":
        return "file"  # Resolve the public redirect before deciding episode versus music.
    if host == "spotify.com" or host.endswith(".spotify.com"):
        if "episode" in parsed.path.split("/"):
            return "media"
        return "spotify"
    if PurePosixPath(parsed.path).suffix.lower() in {".m3u8", ".mpd"}:
        return "media"
    if any(host == domain or host.endswith("."+domain) for domain in MEDIA_HOSTS):
        return "media"
    return "file"


def clipboard_link(value):
    """Accept only a single explicit link, leaving unrelated clipboard text alone."""
    value = value.strip()
    if not value or len(value) > 16384 or any(char.isspace() for char in value):
        return None
    try:
        link_kind(value)
    except (ValueError, UnicodeError):
        return None
    return value


def spotify_destination(value, proxy=None):
    """Resolve public Spotify short links with the selected transport and no account cookies."""
    if (urlsplit(value).hostname or "").lower().rstrip(".") != "spotify.link":
        return value
    from .engine import request
    with request(value, {"Range": "bytes=0-0"}, **({"proxy": proxy} if proxy else {})) as response:
        destination = validate_url(response.geturl())
    parsed = urlsplit(destination)
    host = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme != "https" or not (host == "spotify.com" or host.endswith(".spotify.com")):
        raise ValueError("Link Spotify không chuyển tới nguồn Spotify công khai hợp lệ.")
    return destination


def resolve_source(value, force_file=False, proxy=None):
    """Resolve only after Download is pressed; HTML pages go to the media extractor."""
    from .cloud import resolve
    from .engine import request

    value = spotify_destination(value, proxy)
    kind = link_kind(value)
    if kind != "file":
        return kind, value
    direct = resolve(value, **({"proxy": proxy} if proxy else {}))
    if force_file:
        return "file", direct
    with request(direct, {"Range": "bytes=0-0"}, **({"proxy": proxy} if proxy else {})) as response:
        content_type = response.headers.get_content_type()
        if content_type in {"text/html", "application/xhtml+xml"} and not response.headers.get_filename():
            return "media", value
    return "file", direct


def describe_source(value, proxy=None, cookie_file=""):
    """Fetch metadata after manual paste or Enter; never save content in the user folder."""
    from .cloud import resolve
    from .engine import request
    from .safety import filename_from_url, safe_filename

    original = value
    value = spotify_destination(value, proxy)
    kind = link_kind(value)
    result = {"original": original, "kind": kind, "url": value, "filename": "", "size": None}
    if kind == "file":
        direct = resolve(value, **({"proxy": proxy} if proxy else {}))
        with request(direct, {"Range": "bytes=0-0"}, **({"proxy": proxy} if proxy else {})) as response:
            headers = response.headers
            content_type = headers.get_content_type()
            if content_type in {"text/html", "application/xhtml+xml"} and not headers.get_filename():
                kind = "media"
            else:
                result.update(url=direct, filename=safe_filename(headers.get_filename())
                              if headers.get_filename() else filename_from_url(direct), content_type=content_type)
                total = headers.get("Content-Range", "").rsplit("/", 1)[-1]
                if not total.isdigit():
                    total = headers.get("Content-Length", "")
                result["size"] = int(total) if total.isdigit() else None
    result["kind"] = kind
    if kind == "media":
        from .media import describe_media
        try:
            options = {"proxy": proxy} if proxy else {}
            if cookie_file:
                options["cookie_file"] = cookie_file
            metadata = describe_media(value, **options)
            result.update(heights=metadata.get("heights", []), formats=metadata.get("formats", []))
            if metadata.get("title"):
                result["filename"] = safe_filename(metadata["title"])+".mp4"
        except Exception as error:  # noqa: BLE001 -- Cookie-protected sources remain configurable.
            result["metadata_error"] = str(error)
            result["filename"] = filename_from_url(value).rsplit(".", 1)[0]+".mp4"
    return result


def source_error_message(error):
    """Show actionable provider failures instead of hiding every cause as a missing name."""
    text = str(error)
    lowered = text.lower()
    if any(value in lowered for value in ("vip", "premium", "payment required")):
        return "Nguồn này yêu cầu tài khoản VIP hoặc trả phí có quyền truy cập."
    if any(value in lowered for value in ("sign in", "login", "log in", "authentication", "http error 401", "http error 403")):
        return "Nguồn yêu cầu đăng nhập hoặc quyền truy cập. Hãy gửi lượt tải từ trình duyệt đã đăng nhập."
    if "unsupported url" in lowered and "spotify" in lowered:
        return "Tập podcast Spotify này chưa có nguồn âm thanh công khai mà HDM đọc được. Hãy dùng link tệp hoặc RSS của nhà phát hành."
    if "drm" in lowered:
        return "Nguồn có bảo vệ DRM nên không cung cấp tệp tải trực tiếp."
    if "http error 404" in lowered or "not found" in lowered:
        return "Không tìm thấy nội dung. Link có thể đã bị xóa hoặc hết hạn."
    return text.splitlines()[0][:240] or "Không lấy được tên tệp từ nguồn. Hãy thử lại hoặc kiểm tra quyền truy cập."
