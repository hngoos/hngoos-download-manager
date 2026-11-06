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
    if host == "spotify.com" or host.endswith(".spotify.com") or host == "spotify.link":
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


def resolve_source(value, force_file=False):
    """Resolve only after Download is pressed; HTML pages go to the media extractor."""
    from .cloud import resolve
    from .engine import request

    kind = link_kind(value)
    if kind != "file":
        return kind, value
    direct = resolve(value)
    if force_file:
        return "file", direct
    with request(direct, {"Range": "bytes=0-0"}) as response:
        content_type = response.headers.get_content_type()
        if content_type in {"text/html", "application/xhtml+xml"} and not response.headers.get_filename():
            return "media", value
    return "file", direct
