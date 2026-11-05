"""OpenSubtitles search restricted to a matching movie hash, with explicit API credentials."""

import json
import struct
import urllib.parse
import urllib.request
from pathlib import Path


def movie_hash(path):
    path = Path(path)
    size = path.stat().st_size
    if size < 128*1024:
        raise ValueError("Tệp quá nhỏ để tính mã OpenSubtitles (cần ít nhất 128 KB).")
    value = size
    with path.open("rb") as source:
        for offset in (0, size-65536):
            source.seek(offset)
            block = source.read(65536)
            for item in struct.unpack("<8192Q", block):
                value = (value+item) & 0xffffffffffffffff
    return f"{value:016x}"


def api(path, api_key, token="", body=None):
    headers = {"Api-Key": api_key, "User-Agent": "HDM v0.1.0", "Accept": "application/json"}
    if token:
        headers["Authorization"] = "Bearer "+token
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")
    request = urllib.request.Request("https://api.opensubtitles.com/api/v1/"+path, headers=headers, data=data)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def download_vietnamese(movie, api_key, token=""):
    if not api_key.strip():
        raise ValueError("Cần API key OpenSubtitles của bạn.")
    movie = Path(movie).resolve()
    target = movie.with_suffix(".vi.srt")
    if target.exists():
        raise ValueError("Phim đã có tệp .vi.srt; không ghi đè phụ đề có sẵn.")
    digest = movie_hash(movie)
    result = api("subtitles?"+urllib.parse.urlencode({"moviehash": digest, "languages": "vi"}), api_key, token)
    candidates = [row for row in result.get("data", []) if row.get("attributes", {}).get("moviehash_match")]
    if not candidates:
        raise ValueError("Không tìm thấy phụ đề tiếng Việt khớp mã của chính tệp phim; không tải bản đoán theo tên.")
    candidates.sort(key=lambda item: item["attributes"].get("download_count", 0), reverse=True)
    files = candidates[0]["attributes"].get("files", [])
    if not files:
        raise ValueError("Kết quả phụ đề không có tệp tải.")
    download = api("download", api_key, token, {"file_id": files[0]["file_id"], "sub_format": "srt"})
    url = download.get("link", "")
    if not url.startswith("https://"):
        raise ValueError("Dịch vụ trả link tải không hợp lệ.")
    with urllib.request.urlopen(url, timeout=30) as response:
        data = response.read(5*1024*1024+1)
    if len(data) > 5*1024*1024:
        raise ValueError("Phụ đề vượt giới hạn 5 MB.")
    if b"-->" not in data:
        raise ValueError("Dữ liệu trả về chưa phải phụ đề SRT hợp lệ.")
    with target.open("xb") as stream:
        stream.write(data)
    from .files import mark_internet
    mark_internet(target)
    return target
