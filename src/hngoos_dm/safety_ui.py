"""Safety scans run directly from download rows via Windows Defender."""

import os
from contextlib import contextmanager
from pathlib import Path

from .safety import sha256_file


def file_identity(path):
    state = Path(path).stat()
    return state.st_dev, state.st_ino, state.st_size, state.st_mtime_ns


@contextmanager
def unchanged_file(path):
    """Deny writes during Windows scans instead of hashing large files twice."""
    if os.name != "nt":
        digest = sha256_file(path)
        yield
        if sha256_file(path) != digest:
            raise ValueError("Tệp thay đổi trong lúc kiểm tra; hãy quét lại.")
        return
    import ctypes
    import msvcrt
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                                  wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.CreateFileW(str(Path(path).resolve()), 0x80000000, 1, None, 3, 0x80, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        descriptor = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
    except Exception:
        kernel.CloseHandle(handle)
        raise
    with os.fdopen(descriptor, "rb") as locked:
        snapshot = os.fstat(locked.fileno())
        def identity(value):
            return value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns
        if identity(Path(path).stat()) != identity(snapshot):
            raise ValueError("Tệp thay đổi trong lúc kiểm tra; hãy quét lại.")
        yield
        if identity(Path(path).stat()) != identity(snapshot):
            raise ValueError("Tệp thay đổi trong lúc kiểm tra; hãy quét lại.")


def scan_files(paths, scanner):
    """Scan every output; a failure or changed file must never become a clean result."""
    threats, errors, details = [], [], []
    for path in paths:
        try:
            if not Path(path).is_file():
                raise FileNotFoundError("Tệp đã được di chuyển hoặc xóa.")
            with unchanged_file(path):
                result = scanner(path)
        except (OSError, ValueError) as error:
            errors.append(str(path))
            details.append(str(path)+":\n"+str(error))
            continue
        if result.returncode != 0:
            # Code 2 can also indicate an interrupted scan; report risk, never clearance.
            (threats if result.returncode == 2 else errors).append(str(path))
            details.append(str(path)+":\n"+(result.stdout or "")+"\n"+(result.stderr or ""))
    return "threat" if threats else "error" if errors else "clean", "\n".join(details), threats
