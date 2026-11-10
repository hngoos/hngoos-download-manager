"""Cancellable yt-dlp jobs, explicit format choices and playlist/subtitle support."""

import re
import shutil
import sys
import threading
from dataclasses import dataclass
from pathlib import Path

from .media_formats import AUDIO_EXPORTS, VIDEO_CONTAINERS
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
    container: str = "mp4"
    audio_bitrate: int = 320
    proxy: dict | None = None


def find_ffmpeg():
    from importlib.resources import files

    bundled = files("hngoos_dm")/"assets/runtime"/("ffmpeg.exe" if sys.platform == "win32" else "ffmpeg")
    if bundled.is_file():
        return str(bundled)
    executable = shutil.which("ffmpeg")
    if executable:
        return executable
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except (ImportError, RuntimeError) as exc:
        raise ValueError("Chưa có FFmpeg. Cài gói processing hoặc FFmpeg trong PATH.") from exc


def javascript_runtimes():
    """Use installed runtimes, with a small bundled QuickJS-NG fallback."""
    runtimes = {name: {"path": path} for name in ("deno", "node") if (path := shutil.which(name))}
    if not runtimes:
        from importlib.resources import files
        try:
            runtime = files("hngoos_dm") / "assets" / "runtime" / ("qjs.exe" if sys.platform == "win32" else "qjs")
            if runtime.is_file():
                runtimes["quickjs"] = {"path": str(runtime)}
        except ImportError:
            pass  # Build-prepared runtimes are optional in source installations.
    return runtimes


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
    # Both metadata and downloads use the same explicit YouTube challenge runtime.
    settings["js_runtimes"] = javascript_runtimes()
    from .network import media_proxy
    proxy = media_proxy(options.proxy)
    if proxy is not None:
        settings["proxy"] = proxy
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
    if options.container not in VIDEO_CONTAINERS:
        raise ValueError("Định dạng video không được hỗ trợ.")
    if options.audio:
        if options.audio not in AUDIO_EXPORTS:
            raise ValueError("Định dạng âm thanh không được hỗ trợ.")
        if not ffmpeg:
            raise ValueError("Cần FFmpeg để tách nhạc.")
        if options.audio_bitrate not in {96, 128, 192, 256, 320}:
            raise ValueError("Bitrate âm thanh không hợp lệ.")
        # HDM encodes once after extraction, including when the source already has
        # the selected extension; yt-dlp otherwise copies it and ignores bitrate.
        settings.update(format="bestaudio/best")
    elif options.format_id:
        if not all(char.isalnum() or char in "_-.+" for char in options.format_id):
            raise ValueError("Format ID không hợp lệ.")
        settings["format"] = options.format_id
        if "+" in options.format_id:
            if not ffmpeg:
                raise ValueError("Cần FFmpeg để ghép video và âm thanh.")
            settings["merge_output_format"] = options.container
    elif ffmpeg:
        height = max(144, min(4320, int(options.height)))
        settings.update(format=f"bv*[height<=?{height}][ext=mp4][vcodec^=avc1]+ba[ext=m4a]/"
                               f"b[height<=?{height}][ext=mp4]/bv*[height<=?{height}]+ba/b[height<=?{height}]",
                        merge_output_format="mp4")
    else:
        height = max(144, min(4320, int(options.height)))
        settings["format"] = f"b[height<=?{height}][ext=mp4]/b[height<=?{height}]"
    if not options.audio and options.container in {"mov", "mkv", "m4v"}:
        if not ffmpeg:
            raise ValueError("Cần FFmpeg để đổi định dạng video.")
        settings["merge_output_format"] = options.container
        settings["postprocessors"] = [{"key": "FFmpegVideoRemuxer", "preferedformat": options.container}]
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


def video_quality(item):
    """Source quality tier, distinct from the pixel height of portrait video."""
    note = re.match(r"^(\d+)p(?:\b|\d)", str(item.get("format_note") or ""))
    if note:
        return int(note[1])
    dimensions = [int(item[key]) for key in ("width", "height") if item.get(key)]
    return min(dimensions) if dimensions else 0


def describe_media(url, proxy=None, cookie_file=""):
    """Bound preview requests; no playlist traversal, processing, or downloaded media."""
    from .tiktok_photos import describe_album, photo_id
    if photo_id(url):
        album = describe_album(url, proxy)
        return {"title": album["title"], "media_type": "photos", "extension": album["images"][0]["ext"],
                "heights": [], "formats": []}
    from yt_dlp import YoutubeDL
    settings = ydl_options(Path.cwd(), MediaOptions(proxy=proxy, cookie_file=cookie_file))
    settings.update(skip_download=True, extract_flat=False, playlistend=1,
                    socket_timeout=15, retries=1, extractor_retries=1, ignoreerrors=False,
                    format="best", ignore_no_formats_error=True)
    with YoutubeDL(settings) as downloader:
        info = downloader.extract_info(validate_url(url), download=False)
        if info.get("entries") is not None:
            info = next((item for item in info["entries"] if item), {})
        formats = [item for item in info.get("formats", []) if not item.get("has_drm")
                   and (item.get("vcodec") != "none" or item.get("acodec") != "none")]
        return {"title": info.get("title", ""), "heights": sorted({video_quality(item)
                for item in formats if item.get("height") and item.get("vcodec") != "none"}),
                "formats": [dict({key: item.get(key) for key in
                    ("format_id", "width", "height", "format_note", "ext", "vcodec", "acodec", "abr", "tbr",
                     "fps", "protocol", "filesize")},
                    quality=video_quality(item)) for item in formats]}


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
                inspection = {"reasons": [], "safety_note": ""}
                if high_security or antivirus:
                    if progress:
                        progress({"status": "verifying"})
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
    from yt_dlp.postprocessor.common import PostProcessor

    from .media_progress import MediaProgress
    options = options or MediaOptions(audio="mp3" if audio else "")
    stop = stop or threading.Event()
    from .tiktok_photos import describe_album, photo_id
    if identifier := photo_id(url):
        if stop.is_set():
            raise MediaCancelled("Đã dừng tác vụ tải.")
        album = describe_album(url, options.proxy)
        from .safety import safe_filename
        stem = safe_filename(Path(options.filename).stem if options.filename else album["title"])
        settings = {"quiet": True, "noprogress": True, "continuedl": True, "overwrites": False,
                    "outtmpl": str(Path(directory)/(stem.replace("%", "%%")+" - %(autonumber)03d.%(ext)s")),
                    "http_headers": {"Referer": "https://www.tiktok.com/"}, "socket_timeout": 15, "retries": 3}
        from .network import media_proxy
        if (proxy := media_proxy(options.proxy)) is not None:
            settings["proxy"] = proxy
        reporter = MediaProgress(progress)
        entries = [dict(image, id=f"{identifier}-{index}", title=album["title"], format_id="image")
                   for index, image in enumerate(album["images"], 1)]
        for entry in entries:
            reporter.plan(entry)
        def photo_progress(data):
            if stop.is_set():
                raise MediaCancelled("Đã dừng tác vụ tải.")
            # yt-dlp skips an image completed before pause without byte counters.
            if data.get("status") == "finished" and "downloaded_bytes" not in data and data.get("filename"):
                size = Path(data["filename"]).stat().st_size
                data = dict(data, downloaded_bytes=size, total_bytes=size)
            reporter(data)
        settings["progress_hooks"] = [photo_progress]
        with YoutubeDL(settings) as downloader:
            downloader.process_ie_result({"_type": "playlist", "id": identifier, "title": album["title"],
                                          "extractor": "TikTokPhotos", "extractor_key": "TikTokPhotos",
                                          "webpage_url": url, "entries": entries}, download=True)
        from .files import mark_internet
        for path in Path(directory).glob("*"):
            if path.suffix.lower() in {".jpg", ".png", ".webp", ".avif"}:
                mark_internet(path)
        return
    try:
        ffmpeg = find_ffmpeg()
    except ValueError:
        ffmpeg = None
    settings = ydl_options(directory, options, ffmpeg)
    downloaded = set()
    from .toolchain import active_ytdlp
    updated_tool = active_ytdlp()
    if updated_tool:
        external_download(updated_tool, url, settings, stop, progress)
        normalize_audio(directory, options, stop)
        return
    reporter = MediaProgress(progress)
    class ProgressPlan(PostProcessor):
        def run(self, info):
            reporter.plan(info)
            return [], info
    def hook(data):
        if stop.is_set():
            raise MediaCancelled("Đã dừng tác vụ video.")
        reporter(data)
        if data.get("status") == "finished":
            for path in (data.get("filename"), data.get("info_dict", {}).get("filepath")):
                if path:
                    downloaded.add(Path(path))
    settings["progress_hooks"] = [hook]
    settings["postprocessor_hooks"] = [hook]
    with YoutubeDL(settings) as downloader:
        downloader.add_post_processor(ProgressPlan(downloader), when="before_dl")
        downloader.download([validate_url(url)])
    from .files import mark_internet
    for path in downloaded:
        if path.is_file():
            mark_internet(path)
    normalize_audio(directory, options, stop)


def normalize_audio(directory, options, stop):
    """Encode extracted media once at the selected audio bitrate, before safety checks."""
    if not options.audio:
        return
    import tempfile

    from .processing import _execute_ffmpeg
    extensions = {".mp3", ".m4a", ".aac", ".opus", ".ogg", ".oga", ".wav", ".flac", ".webm", ".weba",
                  ".mp4", ".mkv", ".mov", ".m4v", ".3gp", ".ts", ".wma", ".avi"}
    sources = [path for path in Path(directory).rglob("*") if path.is_file() and path.suffix.lower() in extensions]
    for source in sources:
        if stop.is_set():
            raise MediaCancelled("Đã dừng tác vụ âm thanh.")
        with tempfile.TemporaryDirectory(prefix=".hdm-bitrate-", dir=source.parent) as folder:
            output = source.with_suffix("."+options.audio)
            if output != source and output.exists():
                raise FileExistsError(output)
            target = Path(folder)/output.name
            codec, rates = AUDIO_EXPORTS[options.audio]
            encoding = ["-c:a", codec]
            if rates:
                encoding += ["-b:a", f"{options.audio_bitrate}k"]
            if options.audio == "wma":
                encoding += ["-ac", "2", "-ar", "48000"]
            _execute_ffmpeg(["-i", source, "-map", "0:a:0", "-vn", *encoding, target], stop)
            target.replace(output)
            if output != source:
                source.unlink()


def external_download(executable, url, settings, stop, progress):
    import json
    import os
    import subprocess
    from collections import deque

    from .media_progress import MediaProgress
    reporter = MediaProgress(progress)
    # Match preview's explicit runtimes instead of adding yt-dlp's implicit Deno PATH scan.
    arguments = [str(executable), "--newline", "--progress", "--no-color", "--windows-filenames", "--no-overwrites",
                 "--no-js-runtimes",
                 "--no-playlist" if settings["noplaylist"] else "--yes-playlist", "-o", settings["outtmpl"], "-f", settings["format"]]
    arguments += ["--print", "after_move:HNGOOS_FILE:%(filepath)s"]
    arguments += ["--print", ("before_dl:HDM_PLAN:[%(.{id,duration,format_id,filesize,filesize_approx,tbr})j,"
                  "%(requested_formats.:.{format_id,filesize,filesize_approx,tbr})j]")]
    arguments += ["--progress-template",
                  ("download:HDM_PROGRESS:%(progress.downloaded_bytes)s|%(progress.total_bytes)s|%(progress.total_bytes_estimate)s|%(progress.speed)s|"
                  "[%(info.{id,format_id,title,filesize,filesize_approx})j,%(progress.status)j]")]
    arguments += ["--concurrent-fragments", str(settings.get("concurrent_fragment_downloads", 32))]
    for runtime, config in settings.get("js_runtimes", {}).items():
        arguments += ["--js-runtimes", runtime+":"+config["path"]]
    if "proxy" in settings:
        arguments += ["--proxy", settings["proxy"]]
    if settings.get("cookiefile"):
        arguments += ["--cookies", settings["cookiefile"]]
    if settings.get("http_headers", {}).get("Referer"):
        arguments += ["--referer", settings["http_headers"]["Referer"]]
    if settings.get("ffmpeg_location"):
        arguments += ["--ffmpeg-location", settings["ffmpeg_location"]]
    if settings.get("writesubtitles"):
        arguments += ["--write-subs", "--write-auto-subs", "--sub-langs", ",".join(settings["subtitleslangs"])]
    processors = settings.get("postprocessors", [])
    remux = next((item for item in processors if item["key"] == "FFmpegVideoRemuxer"), None)
    if settings.get("merge_output_format"):
        arguments += ["--merge-output-format", settings["merge_output_format"]]
    if remux:
        arguments += ["--remux-video", remux["preferedformat"]]
    arguments += ["--", validate_url(url)]
    process = subprocess.Popen(arguments, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                               encoding="utf-8", errors="replace", creationflags=0x08000000 if os.name == "nt" else 0)
    lines = deque(maxlen=20)
    completed_paths = set()
    def drain():
        for line in process.stdout:
            if line.startswith("HDM_PLAN:"):
                info, formats = json.loads(line.split(":", 1)[1])
                if isinstance(formats, list):
                    info["requested_formats"] = formats
                reporter.plan(info)
                continue
            lines.append(line.rstrip())
            if line.startswith("HNGOOS_FILE:"):
                completed_paths.add(Path(line.rstrip().split(":", 1)[1]))
            if line.startswith("HDM_PROGRESS:") and progress:
                values = line.strip().split(":", 1)[1].split("|", 4)
                if len(values) in {4, 5}:
                    data = {"status": "downloading"}
                    if len(values) == 5:
                        data["info_dict"], data["status"] = json.loads(values[4])
                    for name, value in zip(("downloaded_bytes", "total_bytes", "total_bytes_estimate", "speed"), values):
                        try:
                            data[name] = float(value) if name == "speed" else int(float(value))
                        except (ValueError, OverflowError):
                            data[name] = None
                    reporter(data)
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
