#!/bin/sh
# Install the HDM desktop preview into a per-user virtual environment.
set -eu
case "$(uname -s)" in
    Darwin) hdm_parent="$HOME/Library/Application Support/HDM" ;;
    *) printf '%s\n' 'HDM supports Windows and macOS. Use install.ps1 on Windows.' >&2; exit 1 ;;
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
import shlex
import shutil
import sys
from importlib.resources import files
from pathlib import Path

from hngoos_dm import __version__

branding = files('hngoos_dm')/'assets'/'branding'
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
    (bundle/'Resources').mkdir(exist_ok=True)
    with (branding/'hdm.icns').open('rb') as source, (bundle/'Resources/hdm.icns').open('wb') as output:
        shutil.copyfileobj(source, output)
    import plistlib
    (bundle/'Info.plist').write_bytes(plistlib.dumps({
        'CFBundleName': 'HDM', 'CFBundleIdentifier': 'com.hngoos.hdm',
        'CFBundleExecutable': 'HDM', 'CFBundlePackageType': 'APPL',
        'CFBundleShortVersionString': __version__, 'CFBundleIconFile': 'hdm.icns',
    }))
print(f'HDM installed. Open HDM from your applications menu, or run {binary/"hdm"}.')
print('For terminal access, add ~/.local/bin to PATH if it is not already included.')
PY
