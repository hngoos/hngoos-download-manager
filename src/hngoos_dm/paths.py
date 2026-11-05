"""Shared data location for HDM and its browser bridge."""

import os
from pathlib import Path


def data_directory():
    override = os.environ.get("HDM_DATA_DIR") or os.environ.get("HNGOOS_DATA_DIR")
    if override:
        return Path(override).expanduser()
    parent = Path(os.environ["LOCALAPPDATA"]) if os.environ.get("LOCALAPPDATA") else Path.home()
    current = parent/"HDM"
    legacy = parent/"HngoosDM"
    # Preserve absolute staging paths and the existing process lock for earlier installations.
    if not current.exists() and (legacy/"downloads.sqlite3").is_file():
        return legacy
    return current
