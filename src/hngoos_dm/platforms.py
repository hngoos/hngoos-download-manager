"""Small desktop integration helpers with no shell interpolation."""

import os
import subprocess
import sys
from pathlib import Path


def platform_label():
    return {"win32": "Windows", "darwin": "macOS"}.get(sys.platform, "Linux")


def open_path(path):
    target = str(Path(path).resolve())
    if os.name == "nt":
        os.startfile(target)
    else:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", target],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
