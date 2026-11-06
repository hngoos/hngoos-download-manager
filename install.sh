#!/bin/sh
# Install the HDM desktop preview into a per-user virtual environment.
set -eu
case "$(uname -s)" in
    Darwin) hdm_parent="$HOME/Library/Application Support/HDM" ;;
    Linux) hdm_parent="${XDG_DATA_HOME:-$HOME/.local/share}/hdm" ;;
    *) printf '%s\n' 'Use install.ps1 on Windows.' >&2; exit 1 ;;
esac
hdm_python="${HDM_PYTHON:-python3}"
hdm_root="${HDM_INSTALL_DIR:-$hdm_parent/runtime}"
hdm_source="${1:-https://github.com/hngoos/hngoos-download-manager/archive/refs/heads/main.zip}"
case "$hdm_root" in /*) ;; *) printf '%s\n' 'HDM_INSTALL_DIR must be an absolute path.' >&2; exit 1 ;; esac
"$hdm_python" -c 'import sys, tkinter, venv; assert sys.version_info >= (3, 11), "Python 3.11+ is required"' || {
    printf '%s\n' 'Install Python 3.11+ with Tkinter and venv before running this installer.' >&2
    exit 1
}
printf '%s\n' "Installing HDM desktop preview in $hdm_root"
"$hdm_python" -m venv "$hdm_root"
"$hdm_root/bin/python" -m pip install --upgrade pip
# No administrator privileges; optional torrent, tray and browser automation remain opt-in.
case "$hdm_source" in
    https://*) hdm_requirement="hngoos-download-manager[media,processing,pdf,excel,updates] @ $hdm_source" ;;
    *) hdm_requirement="$hdm_source"'[media,processing,pdf,excel,updates]' ;;
esac
"$hdm_root/bin/python" -m pip install --upgrade "$hdm_requirement"
"$hdm_root/bin/python" -c 'from hngoos_dm.app import App; from hngoos_dm.engine import DownloadManager'
"$hdm_root/bin/python" - "$hdm_root" <<'PY'
import os
import shlex
import sys
from pathlib import Path

runtime = Path(sys.argv[1]).resolve()
binary = Path.home()/'.local/bin'
binary.mkdir(parents=True, exist_ok=True)
for name in ('hdm', 'hdm-bridge'):
    path = binary/name
    if path.exists() and 'HDM managed launcher' not in path.read_text(errors='replace'):
        raise SystemExit(f'Refusing to overwrite {path}; choose another command location.')
    path.write_text('#!/bin/sh\n# HDM managed launcher\nexec '+shlex.quote(str(runtime/'bin'/name))+' "$@"\n')
    path.chmod(0o755)
if sys.platform == 'darwin':
    bundle = Path.home()/'Applications/HDM.app/Contents'
    (bundle/'MacOS').mkdir(parents=True, exist_ok=True)
    launcher = bundle/'MacOS/HDM'
    launcher.write_text('#!/bin/sh\nexec '+shlex.quote(str(runtime/'bin/hdm'))+' "$@"\n')
    launcher.chmod(0o755)
    import plistlib
    (bundle/'Info.plist').write_bytes(plistlib.dumps({
        'CFBundleName': 'HDM', 'CFBundleIdentifier': 'com.hngoos.hdm',
        'CFBundleExecutable': 'HDM', 'CFBundlePackageType': 'APPL',
        'CFBundleShortVersionString': '0.1.2',
    }))
else:
    directory = Path(os.environ.get('XDG_DATA_HOME') or Path.home()/'.local/share')/'applications'
    directory.mkdir(parents=True, exist_ok=True)
    # Desktop entry quoting differs from shell quoting, including literal percent signs.
    command = str(runtime/'bin/hdm').replace('\\', '\\\\').replace('"', '\\"').replace('`', '\\`').replace('$', '\\$').replace('%', '%%')
    (directory/'com.hngoos.hdm.desktop').write_text(
        '[Desktop Entry]\nType=Application\nName=HDM\nComment=Download, organize and process files\n'
        f'Exec="{command}"\nTerminal=false\nCategories=Network;FileTransfer;\n')
print(f'HDM installed. Open HDM from your applications menu, or run {binary/"hdm"}.')
print('For terminal access, add ~/.local/bin to PATH if it is not already included.')
PY
