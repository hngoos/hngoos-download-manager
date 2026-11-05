"""Shared data location for HDM and its browser bridge."""

import os
import sys
from pathlib import Path


def data_directory():
    override = os.environ.get("HDM_DATA_DIR") or os.environ.get("HNGOOS_DATA_DIR")
    if override:
        return Path(override).expanduser()
    # Respect existing databases before using the platform's standard data folder.
    parent = Path(os.environ["LOCALAPPDATA"]) if os.environ.get("LOCALAPPDATA") else Path.home()
    current = parent/"HDM"
    legacy = parent/"HngoosDM"
    # Preserve absolute staging paths and the existing process lock for earlier installations.
    if not current.exists() and (legacy/"downloads.sqlite3").is_file():
        return legacy
    if sys.platform == "win32" or os.environ.get("LOCALAPPDATA") or (current/"downloads.sqlite3").is_file():
        return current
    if sys.platform == "darwin":
        return Path.home()/"Library/Application Support/HDM"
    xdg = Path(os.environ.get("XDG_DATA_HOME", "")).expanduser()
    if not xdg.is_absolute():
        xdg = Path.home()/".local/share"
    return xdg/"hdm"
