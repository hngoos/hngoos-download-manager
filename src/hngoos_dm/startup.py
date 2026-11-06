"""Opt-in, per-user launch at sign-in, with no administrator privileges."""

import os
import plistlib
import subprocess
import sys
from pathlib import Path


def launch_command():
    if os.environ.get("APPIMAGE"):
        return [str(Path(os.environ["APPIMAGE"]).resolve())]
    if getattr(sys, "frozen", False):
        return [sys.executable]
    executable = Path(sys.executable)
    if sys.platform == "win32" and executable.with_name("pythonw.exe").is_file():
        executable = executable.with_name("pythonw.exe")
    return [str(executable), "-m", "hngoos_dm"]


def startup_file():
    if sys.platform == "darwin":
        return Path.home()/"Library/LaunchAgents/com.hngoos.hdm.plist"
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home()/".config")/"autostart/hdm.desktop"


def set_enabled(enabled):
    command = launch_command()
    if sys.platform == "win32":
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run") as key:
            if enabled:
                winreg.SetValueEx(key, "HDM", 0, winreg.REG_SZ, subprocess.list2cmdline(command))
            else:
                try:
                    winreg.DeleteValue(key, "HDM")
                except FileNotFoundError:
                    pass
        return
    path = startup_file()
    if not enabled:
        path.unlink(missing_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    if sys.platform == "darwin":
        path.write_bytes(plistlib.dumps({"Label": "com.hngoos.hdm", "ProgramArguments": command,
                                        "RunAtLoad": True, "ProcessType": "Interactive"}))
    else:
        def quote(value):
            for char in ('\\', '"', '`', '$'):
                value = value.replace(char, "\\"+char)
            return '"'+value.replace("%", "%%")+'"'
        path.write_text("[Desktop Entry]\nType=Application\nName=HDM\nExec="
                        +" ".join(map(quote, command))+"\nTerminal=false\nX-GNOME-Autostart-enabled=true\n",
                        encoding="utf-8")
