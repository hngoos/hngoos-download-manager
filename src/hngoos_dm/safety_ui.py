"""Safety scans run directly from download rows via Windows Defender."""

from pathlib import Path

from .safety import sha256_file


def scan_files(paths, scanner):
    """Scan every output; a failure or changed file must never become a clean result."""
    for path in paths:
        if not Path(path).is_file():
            raise FileNotFoundError("Tệp đã được di chuyển hoặc xóa.")
        digest = sha256_file(path)
        result = scanner(path)
        if result.returncode != 0:
            # Code 2 can also indicate an interrupted scan; report risk, never clearance.
            return ("threat" if result.returncode == 2 else "error"), (result.stdout or "")+"\n"+(result.stderr or "")
        if sha256_file(path) != digest:
            raise ValueError("Tệp thay đổi trong lúc kiểm tra; hãy quét lại.")
    return "clean", ""
