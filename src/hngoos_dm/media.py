"""Cancellable yt-dlp jobs, explicit format choices and playlist/subtitle support."""

import shutil
import threading
from dataclasses import dataclass
from pathlib import Path

from .safety import validate_url


class MediaCancelled(Exception):
    pass


@dataclass
class MediaOptions:
    height: int = 1080
    audio: str = ""
    playlist: bool = False
    subtitles: bool = False
    subtitle_languages: tuple = ("vi", "en")
    cookie_file: str = ""
    format_id: str = ""
    referrer: str = ""
    connections: int = 32
    filename: str = ""


def find_ffmpeg():
    executable = shutil.which("ffmpeg")
    if executable:
        return executable
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except (ImportError, RuntimeError) as exc:
        raise ValueError("Chưa có FFmpeg. Cài gói processing hoặc FFmpeg trong PATH.") from exc


def ydl_options(directory, options=None, ffmpeg=None):
    options = options or MediaOptions()
    settings = {
        "outtmpl": str(Path(directory) / "%(uploader|Unknown)s - %(title).140s [%(id)s].%(ext)s"),
        "windowsfilenames": True, "noplaylist": not options.playlist, "retries": 5,
        "continuedl": True, "quiet": True, "noprogress": True, "no_color": True,
        "writesubtitles": options.subtitles, "writeautomaticsub": options.subtitles,
        "subtitleslangs": list(options.subtitle_languages), "restrictfilenames": False,
        "overwrites": False,
        "concurrent_fragment_downloads": max(1, min(32, int(options.connections))),
        "allow_unplayable_formats": False,
    }
    if options.filename and not options.playlist:
        from .safety import safe_filename
        name = safe_filename(Path(options.filename).stem).replace("%", "%%")
        settings["outtmpl"] = str(Path(directory)/(name+".%(ext)s"))
    if options.cookie_file:
        cookie_file = Path(options.cookie_file).resolve()
        if not cookie_file.is_file():
            raise ValueError("Không tìm thấy tệp cookie do bạn chọn.")
        settings["cookiefile"] = str(cookie_file)
    if options.referrer:
        settings["http_headers"] = {"Referer": validate_url(options.referrer)}
    if ffmpeg:
        settings["ffmpeg_location"] = str(ffmpeg)
    if options.audio:
        if options.audio not in {"mp3", "m4a"}:
            raise ValueError("Chỉ nhận định dạng âm thanh MP3 hoặc M4A.")
        if not ffmpeg:
            raise ValueError("Cần FFmpeg để tách nhạc.")
        settings.update(format="bestaudio/best", postprocessors=[{
            "key": "FFmpegExtractAudio", "preferredcodec": options.audio, "preferredquality": "320"
        }])
    elif options.format_id:
        if not all(char.isalnum() or char in "_-.+" for char in options.format_id):
            raise ValueError("Format ID không hợp lệ.")
        settings["format"] = options.format_id
    elif ffmpeg:
        height = max(144, min(4320, int(options.height)))
        settings.update(format=f"bv*[height<={height}][ext=mp4][vcodec^=avc1]+ba[ext=m4a]/"
                               f"b[height<={height}][ext=mp4]/bv*[height<={height}]+ba/b[height<={height}]",
                        merge_output_format="mp4")
    else:
        height = max(144, min(4320, int(options.height)))
        settings["format"] = f"b[height<={height}][ext=mp4]/b[height<={height}]"
    return settings


def inspect_video(url, options=None):
    from yt_dlp import YoutubeDL
    settings = ydl_options(Path.cwd(), options)
    settings.update(skip_download=True, extract_flat="in_playlist")
    with YoutubeDL(settings) as downloader:
        info = downloader.extract_info(validate_url(url), download=False)
        if info.get("_type") == "playlist":
            return {"title": info.get("title", "Playlist"), "entries": [
                {"title": item.get("title", ""), "id": item.get("id", "")} for item in info.get("entries", []) if item]}
        return {"title": info.get("title", ""), "duration": info.get("duration"), "formats": [
            {key: item.get(key) for key in ("format_id", "ext", "height", "vcodec", "acodec", "filesize")}
            for item in info.get("formats", []) if not item.get("has_drm")],
            "subtitles": list(info.get("subtitles", {}))}


def describe_media(url):
    """Bound preview requests; no playlist traversal, processing, or downloaded media."""
    from yt_dlp import YoutubeDL
    settings = ydl_options(Path.cwd())
    settings.update(skip_download=True, extract_flat=True, playlistend=1,
                    socket_timeout=15, retries=1, extractor_retries=1, ignoreerrors=False)
    with YoutubeDL(settings) as downloader:
        info = downloader.extract_info(validate_url(url), download=False)
        return {"title": info.get("title", "")}


def download_video(url, directory, audio=False, progress=None, options=None, stop=None,
                   high_security=False, staging_root=None, antivirus=False):
    """Keep incomplete media on the local disk; publish only after all processing succeeds."""
    import hashlib
    import json
    from dataclasses import asdict

    from .files import deliver
    from .instance import InstanceLock
    from .paths import data_directory

    directory = Path(directory).expanduser().resolve()
    identity = asdict(options) if options else {"audio": audio}
    identity.pop("cookie_file", None)
    identifier = hashlib.sha256((validate_url(url)+str(directory)+json.dumps(identity, sort_keys=True)).encode()).hexdigest()
    staging = (Path(staging_root) if staging_root else data_directory()/"media-staging")/identifier
    staging.mkdir(parents=True, exist_ok=True)
    lock = InstanceLock(staging/"task.lock")
    try:
        _download_video(url, staging, audio, progress, options, stop)
        outputs = []
        for path in sorted(staging.rglob("*")):
            if (path.is_file() and path.name != "task.lock"
                    and path.suffix.lower() not in {".part", ".ytdl", ".temp", ".tmp"}
                    and not path.name.startswith("cookies")):
                relative = path.relative_to(staging)
                from .safety import inspect_download
                if stop and stop.is_set():
                    raise MediaCancelled("Đã dừng tác vụ video.")
                inspection = inspect_download(path, path.name.removesuffix(".chuakiemtra"),
                                              high_security=high_security, antivirus=antivirus)
                if progress:
                    progress({"status": "verifying", "safety_note": inspection["safety_note"]})
                if stop and stop.is_set():
                    raise MediaCancelled("Đã dừng tác vụ video.")
                if not path.name.endswith(".chuakiemtra") and inspection["reasons"]:
                    name = path.name+".chuakiemtra"
                else:
                    name = path.name
                outputs.append(deliver(path, directory/relative.parent, name, stop))
        if not outputs:
            raise ValueError("Không có tệp hoàn chỉnh từ nguồn này. Nội dung có thể cần đăng nhập hoặc không hỗ trợ tải.")
        return outputs
    finally:
        lock.close()


def _download_video(url, directory, audio=False, progress=None, options=None, stop=None):
    from yt_dlp import YoutubeDL
    options = options or MediaOptions(audio="mp3" if audio else "")
    stop = stop or threading.Event()
    try:
        ffmpeg = find_ffmpeg()
    except ValueError:
        ffmpeg = None
    settings = ydl_options(directory, options, ffmpeg)
    downloaded = set()
    from .toolchain import active_ytdlp
    updated_tool = active_ytdlp()
    if updated_tool:
        return external_download(updated_tool, url, settings, stop, progress)
    def hook(data):
        if stop.is_set():
            raise MediaCancelled("Đã dừng tác vụ video.")
        if progress:
            progress(data)
        if data.get("status") == "finished":
            for path in (data.get("filename"), data.get("info_dict", {}).get("filepath")):
                if path:
                    downloaded.add(Path(path))
    settings["progress_hooks"] = [hook]
    settings["postprocessor_hooks"] = [hook]
    with YoutubeDL(settings) as downloader:
        downloader.download([validate_url(url)])
    from .files import mark_internet
    from .safety import inspect_file
    for path in downloaded:
        if path.is_file():
            mark_internet(path)
            if inspect_file(path, path.name):
                target = path.with_name(path.name+".chuakiemtra")
                if not target.exists():
                    path.rename(target)


def external_download(executable, url, settings, stop, progress):
    import os
    import subprocess
    from collections import deque
    arguments = [str(executable), "--newline", "--progress", "--no-color", "--windows-filenames", "--no-overwrites",
                 "--no-playlist" if settings["noplaylist"] else "--yes-playlist", "-o", settings["outtmpl"], "-f", settings["format"]]
    arguments += ["--print", "after_move:HNGOOS_FILE:%(filepath)s"]
    arguments += ["--progress-template",
                  "download:HDM_PROGRESS:%(progress.downloaded_bytes)s|%(progress.total_bytes)s|%(progress.total_bytes_estimate)s|%(progress.speed)s"]
    arguments += ["--concurrent-fragments", str(settings.get("concurrent_fragment_downloads", 32))]
    if settings.get("cookiefile"):
        arguments += ["--cookies", settings["cookiefile"]]
    if settings.get("http_headers", {}).get("Referer"):
        arguments += ["--referer", settings["http_headers"]["Referer"]]
    if settings.get("ffmpeg_location"):
        arguments += ["--ffmpeg-location", settings["ffmpeg_location"]]
    if settings.get("writesubtitles"):
        arguments += ["--write-subs", "--write-auto-subs", "--sub-langs", ",".join(settings["subtitleslangs"])]
    if settings.get("postprocessors"):
        arguments += ["-x", "--audio-format", settings["postprocessors"][0]["preferredcodec"], "--audio-quality", "320K"]
    elif settings.get("merge_output_format"):
        arguments += ["--merge-output-format", settings["merge_output_format"]]
    arguments += ["--", validate_url(url)]
    process = subprocess.Popen(arguments, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                               encoding="utf-8", errors="replace", creationflags=0x08000000 if os.name == "nt" else 0)
    lines = deque(maxlen=20)
    completed_paths = set()
    def drain():
        for line in process.stdout:
            lines.append(line.rstrip())
            if line.startswith("HNGOOS_FILE:"):
                completed_paths.add(Path(line.rstrip().split(":", 1)[1]))
            if line.startswith("HDM_PROGRESS:") and progress:
                values = line.strip().split(":", 1)[1].split("|")
                if len(values) == 4:
                    data = {"status": "downloading"}
                    for name, value in zip(("downloaded_bytes", "total_bytes", "total_bytes_estimate", "speed"), values):
                        try:
                            data[name] = float(value) if name == "speed" else int(value)
                        except ValueError:
                            data[name] = None
                    progress(data)
                continue
            if progress:
                progress({"status": "downloading", "_percent_str": line.strip()[:500]})
    reader = threading.Thread(target=drain, daemon=True)
    reader.start()
    while process.poll() is None:
        if stop.wait(0.1):
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], check=False,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=0x08000000)
            else:
                process.terminate()
            process.wait(timeout=10)
            reader.join(timeout=2)
            process.stdout.close()
            raise MediaCancelled("Đã dừng tác vụ video.")
    reader.join(timeout=5)
    process.stdout.close()
    if process.returncode:
        raise RuntimeError("\n".join(lines))
    from .files import mark_internet
    from .safety import inspect_file
    for path in completed_paths:
        if path.is_file():
            mark_internet(path)
            if inspect_file(path, path.name):
                target = path.with_name(path.name+".chuakiemtra")
                if not target.exists():
                    path.rename(target)


def convert_mp4(source, destination):
    from .processing import convert
    return convert(source, destination)
