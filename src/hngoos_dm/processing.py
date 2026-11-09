"""Real FFmpeg transforms. Originals are never overwritten; failed outputs are removed."""

import os
import re
import subprocess
import tempfile
import threading
from pathlib import Path

from .files import mark_internet
from .media import MediaCancelled, find_ffmpeg


def _execute_ffmpeg(arguments, stop):
    if stop.is_set():
        raise MediaCancelled("Đã hủy xử lý media.")
    with tempfile.TemporaryFile() as error_log:
        process = subprocess.Popen([find_ffmpeg(), "-nostdin", "-hide_banner", "-n", *map(str, arguments)],
            stdout=subprocess.DEVNULL, stderr=error_log, creationflags=0x08000000 if os.name == "nt" else 0)
        while process.poll() is None:
            if stop.wait(0.1):
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                raise MediaCancelled("Đã hủy xử lý media.")
        if process.returncode:
            error_log.seek(0, 2)
            error_log.seek(max(0, error_log.tell()-4000))
            raise RuntimeError(error_log.read().decode("utf-8", errors="replace"))


def run_ffmpeg(arguments, destination, stop=None):
    destination = Path(destination).resolve()
    if destination.exists():
        raise ValueError("Tên đầu ra đã tồn tại. Chọn tên mới để giữ nguyên dữ liệu.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    stop = stop or threading.Event()
    with tempfile.TemporaryDirectory(prefix=".hngoos-media-", dir=destination.parent) as folder:
        temporary = Path(folder) / ("output" + destination.suffix)
        _execute_ffmpeg([*arguments, temporary], stop)
        from .files import publish
        output = publish(temporary, destination.parent, destination.name)
        mark_internet(output)
        return output


def inspect_media(source):
    source = Path(source).resolve()
    result = subprocess.run([find_ffmpeg(), "-hide_banner", "-i", str(source)], check=False,
                            capture_output=True, timeout=30,
                            creationflags=0x08000000 if os.name == "nt" else 0)
    text = result.stderr.decode("utf-8", errors="replace")
    duration = re.search(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)", text)
    if not duration:
        raise ValueError("Không đọc được thời lượng media.")
    seconds = int(duration[1])*3600 + int(duration[2])*60 + float(duration[3])
    dimensions = re.search(r"Video:[^\r\n]*?\b(\d{2,5})x(\d{2,5})\b", text)
    return {"duration": seconds, "size": source.stat().st_size, "video": "Video:" in text,
            "audio": "Audio:" in text, "width": int(dimensions[1]) if dimensions else 0,
            "height": int(dimensions[2]) if dimensions else 0, "details": text[-4000:]}


def validate_source(source, destination):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if not source.is_file() or source == destination:
        raise ValueError("Nguồn không tồn tại hoặc đầu ra trùng tệp gốc.")
    return source, destination


def convert(source, destination, stop=None, prefer_hardware=True):
    source, destination = validate_source(source, destination)
    if prefer_hardware and os.name == "nt":
        try:
            return run_ffmpeg(["-i", source, "-c:v", "h264_mf", "-hw_encoding", "1", "-b:v", "5M",
                               "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart"], destination, stop)
        except RuntimeError:
            pass  # Encoder/device unavailable: use the portable software encoder.
    return run_ffmpeg(["-i", source, "-c:v", "libx264", "-crf", "23", "-preset", "fast",
                       "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart"], destination, stop)


def extract_audio(source, destination, stop=None):
    source, destination = validate_source(source, destination)
    if destination.suffix.lower() not in {".mp3", ".m4a"}:
        raise ValueError("Chọn MP3 hoặc M4A làm định dạng đầu ra.")
    codec = ["-c:a", "libmp3lame", "-b:a", "320k"] if destination.suffix.lower() == ".mp3" else ["-c:a", "aac", "-b:a", "256k"]
    return run_ffmpeg(["-i", source, "-vn", *codec], destination, stop)


def cut(source, destination, start, end, exact=False, stop=None):
    source, destination = validate_source(source, destination)
    start, end = float(start), float(end)
    info = inspect_media(source)
    if not 0 <= start < end <= info["duration"] + 0.05:
        raise ValueError("Điểm cắt phải nằm trong thời lượng, điểm cuối lớn hơn điểm đầu.")
    if exact:
        codec = ["-c:v", "libx264", "-crf", "18", "-c:a", "aac"] if info["video"] else ["-c:a", "libmp3lame"]
        args = ["-i", source, "-ss", start, "-t", end-start, *codec]
    else:
        args = ["-ss", start, "-i", source, "-t", end-start, "-c", "copy", "-avoid_negative_ts", "make_zero"]
    return run_ffmpeg(args, destination, stop)


def compress(source, destination, target_mb, stop=None):
    source, destination = validate_source(source, destination)
    info = inspect_media(source)
    target = int(float(target_mb)*1024*1024)
    if not info["video"] or not 0 < target < info["size"]:
        raise ValueError("Chọn video và dung lượng đích nhỏ hơn tệp gốc.")
    audio_rate = 128000 if info["audio"] else 0
    bitrate = int(target * 8 / info["duration"] * 0.94) - audio_rate
    if bitrate < 64000:
        raise ValueError("Dung lượng đích quá nhỏ cho thời lượng video.")
    if destination.exists():
        raise ValueError("Tên đầu ra đã tồn tại. Chọn tên mới để giữ nguyên dữ liệu.")
    stop = stop or threading.Event()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".hdm-compress-", dir=destination.parent) as folder:
        log = Path(folder)/"two-pass"
        codec = ["-c:v", "libx264", "-b:v", bitrate, "-preset", "fast", "-passlogfile", log]
        _execute_ffmpeg(["-i", source, *codec, "-pass", "1", "-an", "-f", "null", "-"], stop)
        output = run_ffmpeg(["-i", source, *codec, "-pass", "2", "-c:a", "aac", "-b:a", "128k",
                            "-movflags", "+faststart"], Path(folder)/"compressed.mp4", stop)
        if output.stat().st_size >= info["size"]:
            raise ValueError("Video đã gọn; kết quả nén không nhỏ hơn nên đã bỏ, giữ nguyên bản gốc.")
        if output.stat().st_size > target:
            raise ValueError("Kết quả vượt dung lượng đích do chi phí đóng gói; chọn dung lượng cao hơn.")
        from .files import publish
        return publish(output, destination.parent, destination.name)


def concatenate(sources, destination, stop=None):
    if len(sources) < 2:
        raise ValueError("Chọn ít nhất hai tệp để ghép.")
    destination = Path(destination).resolve()
    paths = [validate_source(source, destination)[0] for source in sources]
    infos = [inspect_media(path) for path in paths]
    if len({info["video"] for info in infos}) > 1:
        raise ValueError("Ghép video với video, hoặc nhạc với nhạc; không trộn hai nhóm.")
    # Preserve the largest source canvas instead of reducing every video to 720p.
    # Even dimensions keep H.264/yuv420p output compatible with ordinary players.
    canvas = max(infos, key=lambda info: info["width"]*info["height"])
    width, height = max(2, canvas["width"]//2*2), max(2, canvas["height"]//2*2)
    with tempfile.TemporaryDirectory(prefix="hngoos-join-") as folder:
        intermediates = []
        for index, (path, info) in enumerate(zip(paths, infos, strict=True)):
            target = Path(folder) / (f"{index}.mp4" if info["video"] else f"{index}.m4a")
            if info["video"]:
                args = ["-i", path]
                if not info["audio"]:
                    args += ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000", "-shortest"]
                args += ["-vf", (f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                         f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30"),
                         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-c:a", "aac", "-ar", "48000", "-ac", "2"]
            else:
                args = ["-i", path, "-vn", "-c:a", "aac", "-ar", "48000", "-ac", "2"]
            intermediates.append(run_ffmpeg(args, target, stop))
        listing = Path(folder) / "concat.txt"
        listing.write_text("\n".join("file '"+path.as_posix().replace("'", "'\\''")+"'" for path in intermediates), encoding="utf-8")
        return run_ffmpeg(["-f", "concat", "-safe", "0", "-i", listing, "-c", "copy"], destination, stop)
