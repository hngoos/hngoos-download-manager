"""Conservative local triage, SHA-256 and Windows Defender integration."""

import hashlib
import io
import re
import subprocess
import time
import zipfile
from pathlib import Path
from urllib.parse import unquote, urlsplit

RISKY = {".exe", ".msi", ".msix", ".com", ".scr", ".bat", ".cmd", ".ps1", ".vbs", ".js",
         ".jse", ".wsf", ".hta", ".lnk", ".url", ".pif", ".cpl", ".dll", ".reg",
         ".docm", ".xlsm", ".pptm", ".xlam", ".iso", ".img", ".vbe", ".wsh", ".sct",
         ".scf", ".chm", ".jar", ".appref-ms", ".application", ".settingcontent-ms",
         ".sh", ".command", ".desktop", ".app", ".pkg", ".dmg", ".deb", ".rpm", ".run", ".appimage"}
WINDOWS_DEVICES = {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$",
                   *(f"{prefix}{number}" for prefix in ("COM", "LPT") for number in "123456789¹²³")}
BIDI = "\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069"


def archive_name_is_unsafe(name):
    """Reject names with different meanings on Windows, regardless of the scanning OS."""
    components = name.replace("\\", "/").removesuffix("/").split("/")
    return any(not part or part in {".", ".."} or part[-1:] in {" ", "."}
               or any(c in '<>:"|?*'+BIDI or ord(c) < 32 for c in part)
               or part.split(".")[0].rstrip(" ").upper() in WINDOWS_DEVICES
               for part in components)


def validate_url(value):
    value = value.strip()
    parsed = urlsplit(value)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Chỉ nhận đường dẫn HTTP hoặc HTTPS hợp lệ.")
    if parsed.username or parsed.password:
        raise ValueError("Không đặt tài khoản/mật khẩu trực tiếp trong URL.")
    if any(ord(c) < 32 for c in value):
        raise ValueError("URL chứa ký tự điều khiển.")
    return value


def safe_filename(value):
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value).strip(" .")
    if not value:
        value = "download.bin"
    if value.split(".")[0].rstrip(" ").upper() in WINDOWS_DEVICES:
        value = "_" + value
    if len(value) > 150:
        suffix = Path(value).suffix[:20]
        value = value[:150 - len(suffix)] + suffix
    return value


def filename_from_url(url):
    return safe_filename(unquote(urlsplit(url).path.rsplit("/", 1)[-1]))


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def inspect_file(path, filename, password=None, high_security=False):
    reasons = []
    if Path(filename).suffix.lower() in RISKY:
        reasons.append("Định dạng có thể thực thi hoặc chứa mã")
    if any(c in filename for c in BIDI):
        reasons.append("Tên tệp có ký tự điều hướng văn bản")
    with Path(path).open("rb") as source:
        prefix = source.read(8)
        if prefix[:2] == b"MZ":
            reasons.append("Tệp thực thi Windows (MZ)")
        if prefix[:4] == b"\x7fELF":
            reasons.append("Tệp thực thi Linux (ELF)")
        if prefix[:4] in {b"\xfe\xed\xfa\xce", b"\xce\xfa\xed\xfe", b"\xfe\xed\xfa\xcf", b"\xcf\xfa\xed\xfe",
                          b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca", b"\xca\xfe\xba\xbf", b"\xbf\xba\xfe\xca"}:
            reasons.append("Tệp nhị phân macOS hoặc Java")
        if prefix[:2] == b"#!":
            reasons.append("Tệp script có thể thực thi")
    if prefix[:4] in {b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"}:
        try:
            with zipfile.ZipFile(path) as archive:
                reasons.extend(inspect_zip(archive, password=password))
        except (zipfile.BadZipFile, OSError):
            reasons.append("Cấu trúc ZIP/Office bị hỏng hoặc không đọc được")
    if prefix.startswith((b"7z\xbc\xaf\x27\x1c", b"Rar!\x1a\x07")):
        from .archive_tools import inspect_archive
        reasons.extend(inspect_archive(path, password=password))
    suffixes = [suffix.lower() for suffix in Path(filename).suffixes]
    if len(suffixes) > 1 and suffixes[-1] in RISKY:
        reasons.append("Tên tệp có nhiều đuôi, đuôi cuối có thể thực thi")
    if high_security and (prefix[:2] == b"MZ" or Path(filename).suffix.lower() in {".msi", ".msix", ".dll", ".ps1"}):
        signature = authenticode(path)
        if signature.get("status") != "Valid":
            reasons.append("An toàn cao: chương trình chưa có chữ ký Windows hợp lệ")
    return list(dict.fromkeys(reasons))


OFFICIAL_DOWNLOADS = {
    "zalo": ("https://zalo.me/pc", ("vng", "zalo")),
    "chrome": ("https://www.google.com/chrome/", ("google",)),
    "telegram": ("https://desktop.telegram.org/", ("telegram",)),
    "unikey": ("https://www.unikey.org/", ("pham kim long", "unikey")),
}


def installer_guidance(path, filename):
    """Return source guidance, never a claim that a brand-looking filename is authentic."""
    lower = filename.lower()
    for brand, (url, signers) in OFFICIAL_DOWNLOADS.items():
        if brand in lower and Path(filename).suffix.lower() in {".exe", ".msi", ".msix"}:
            signature = authenticode(path)
            matches = signature.get("status") == "Valid" and any(
                signer in signature.get("signer", "").lower() for signer in signers)
            return {"brand": brand, "official_url": url, "publisher_matches": matches,
                    "signature_status": signature.get("status", "Unavailable")}
    return None


HASH_SERVICES = {
    "VirusTotal": "https://www.virustotal.com/gui/file/{digest}",
    "MetaDefender": "https://metadefender.com/results/hash/{digest}/regular/overview",
    "Kaspersky": "https://opentip.kaspersky.com/{digest}/",
}


def hash_lookup_url(digest, service="VirusTotal"):
    digest = digest.strip().lower()
    if not re.fullmatch(r"[a-f0-9]{64}", digest) or service not in HASH_SERVICES:
        raise ValueError("Chọn dịch vụ hợp lệ và mã SHA-256 đủ 64 ký tự.")
    return HASH_SERVICES[service].format(digest=digest)


def inspect_zip(archive, password=None, depth=0, budget=None):
    """Bounded inspection; never extract attacker-controlled paths to disk."""
    budget = budget or {"bytes": 64 * 1024 * 1024, "files": 5000, "deadline": time.monotonic()+10}
    reasons = []
    for item in archive.infolist():
        budget["files"] -= 1
        if budget["files"] < 0 or time.monotonic() > budget["deadline"]:
            reasons.append("Tệp nén vượt giới hạn kiểm tra; cần quét riêng")
            break
        name = item.filename.replace("\\", "/")
        if (archive_name_is_unsafe(name)
                or ((item.external_attr >> 16) & 0o170000) == 0o120000):
            reasons.append("Tệp nén chứa đường dẫn/tên Windows không an toàn hoặc liên kết tượng trưng")
        if item.is_dir():
            continue
        suffix = Path(name).suffix.lower()
        if suffix in RISKY or name.lower().endswith("vbaproject.bin"):
            reasons.append(f"Tệp nén chứa mã/lối tắt rủi ro: {name[:160]}")
        if item.file_size > 512*1024*1024 and item.file_size > max(1, item.compress_size)*200:
            reasons.append("Tệp nén có tỷ lệ giải nén bất thường")
            continue
        if item.flag_bits & 1 and not password:
            reasons.append("ZIP có mật khẩu, chưa kiểm tra được nội dung")
            continue
        if budget["bytes"] <= 0:
            reasons.append("Đã hết ngân sách kiểm tra tệp nén")
            break
        try:
            with archive.open(item, pwd=password.encode() if isinstance(password, str) else password) as stream:
                prefix = stream.read(min(64, budget["bytes"]))
                budget["bytes"] -= len(prefix)
                if prefix.startswith(b"MZ"):
                    reasons.append(f"Tệp nén chứa chương trình Windows: {name[:160]}")
                if prefix.startswith(b"PK\x03\x04"):
                    if depth >= 2 or item.file_size > min(budget["bytes"], 16*1024*1024):
                        reasons.append("Tệp nén lồng nhau vượt giới hạn kiểm tra")
                        continue
                    data = prefix + stream.read(min(item.file_size, budget["bytes"]))
                    budget["bytes"] -= len(data) - len(prefix)
                    with zipfile.ZipFile(io.BytesIO(data)) as nested:
                        reasons.extend(inspect_zip(nested, password, depth+1, budget))
        except (RuntimeError, NotImplementedError, zipfile.BadZipFile, OSError):
            reasons.append("Không đọc được thành phần ZIP; cần mật khẩu đúng hoặc bộ quét chuyên dụng")
        if len(reasons) >= 30:
            reasons.append("Còn các dấu hiệu khác trong tệp nén; đã giới hạn báo cáo")
            break
    return reasons


def authenticode(path):
    """Query local Windows trust without interpolating paths into PowerShell source."""
    import json
    import os
    if os.name != "nt":
        return {"status": "Unavailable", "signer": ""}
    environment = os.environ.copy()
    environment["HNGOOS_SIGNATURE_PATH"] = str(Path(path).resolve())
    script = ("$s = Get-AuthenticodeSignature -LiteralPath $env:HNGOOS_SIGNATURE_PATH; "
              "@{status=$s.Status.ToString(); signer=$s.SignerCertificate.Subject} | ConvertTo-Json -Compress")
    result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                            check=False, capture_output=True, timeout=30, env=environment,
                            creationflags=0x08000000)
    if result.returncode:
        return {"status": "Error", "signer": ""}
    return json.loads(result.stdout.decode("utf-8-sig", errors="replace"))


def scan_defender(path):
    import os
    root = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Windows Defender"
    tool = root / "MpCmdRun.exe"
    if not tool.is_file():
        raise FileNotFoundError("Không tìm thấy Windows Defender trên máy này.")
    return subprocess.run([str(tool), "-Scan", "-ScanType", "3", "-DisableRemediation", "-File", str(Path(path).resolve())],
                          check=False, capture_output=True, text=True, timeout=600, creationflags=0x08000000)


def inspect_download(path, filename, high_security=False, antivirus=False):
    """Distinguish unavailable antivirus from a completed scan; never certify a file clean."""
    reasons = inspect_file(path, filename, high_security=high_security)
    note = "Đã kiểm tra sơ bộ"
    if antivirus:
        try:
            result = scan_defender(path)
        except (OSError, subprocess.SubprocessError):
            note = "Sơ bộ · Defender chưa quét"
        else:
            if result.returncode == 0:
                note = "Sơ bộ + Defender"
            else:
                reasons.append("Defender phát hiện rủi ro hoặc chưa hoàn tất quét; cần kiểm tra trước khi mở")
    return {"reasons": reasons, "safety_note": "Cách ly" if reasons else note}
