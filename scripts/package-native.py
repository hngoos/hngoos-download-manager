"""Create and verify native installers from the desktop build on the target OS."""

import argparse
import json
import os
import platform
import shutil
import struct
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from hngoos_dm import __version__

ROOT = Path(__file__).resolve().parents[1]
def command(*args, **kwargs):
    return subprocess.run([str(arg) for arg in args], check=True, **kwargs)


def package_macos():
    arch = 'arm64' if platform.machine() == 'arm64' else 'x64'
    image_root = ROOT/'build/native-packages/dmg'
    image_root.mkdir(parents=True, exist_ok=False)
    shutil.copytree(ROOT/'dist/HDM.app', image_root/'HDM.app', symlinks=True)
    shutil.copytree(ROOT/'dist/extension', image_root/'extension')
    (image_root/'Applications').symlink_to('/Applications')
    image = ROOT/f'dist/HDM-{__version__}-macOS-{arch}.dmg'
    for attempt in range(3):
        try:
            result = command('hdiutil', 'create', '-volname', 'HDM', '-srcfolder', image_root,
                             '-ov', '-format', 'UDZO', image, stderr=subprocess.PIPE, text=True)
        except subprocess.CalledProcessError as error:
            detail = error.stderr or ''
            if detail:
                print(detail, file=sys.stderr, end='' if detail.endswith('\n') else '\n')
            # DiskImages can briefly remain busy after earlier package checks.
            # Retry only this known create error; verification is always fatal.
            busy = any(line.strip() == 'hdiutil: create failed - Resource busy' for line in detail.splitlines())
            if not busy or attempt == 2:
                raise
            print('DiskImages is busy; retrying DMG creation.', file=sys.stderr, flush=True)
            time.sleep(2**(attempt+1))
        else:
            if result.stderr:
                print(result.stderr, file=sys.stderr, end='' if result.stderr.endswith('\n') else '\n')
            break
    command('hdiutil', 'verify', image)
    return [image]


def ping_bridge(executable, folder, arguments=(), environment=None):
    data = json.dumps({'action': 'ping'}).encode()
    env = {**os.environ, 'HDM_DATA_DIR': str(folder/'native-data'), **(environment or {})}
    result = command(executable, *arguments, input=struct.pack('<I', len(data))+data,
                     capture_output=True, timeout=90, env=env)
    if len(result.stdout) < 4:
        raise RuntimeError('Native host did not send a framed response')
    length = struct.unpack('<I', result.stdout[:4])[0]
    response = json.loads(result.stdout[4:4+length])
    if response != {'ok': True, 'protocol': 1}:
        raise RuntimeError('Unexpected native protocol response')


def smoke(executable, folder, environment=None):
    args = [str(executable), '--smoke-test', '--data-dir', str(folder/'smoke-data')]
    command(*args, timeout=90, env={**os.environ, **(environment or {})})


def verify_packages(packages):
    for package in packages:
        with tempfile.TemporaryDirectory(prefix='hdm-package-check-') as temporary:
            folder = Path(temporary)
            volume = folder/'volume'
            command('hdiutil', 'attach', '-readonly', '-nobrowse', '-mountpoint', volume, package)
            try:
                extension = volume/'HDM.app/Contents/Resources/extension'
                manifest = json.loads((extension/'manifest.json').read_text(encoding='utf-8'))
                assert manifest['manifest_version'] == 3 and (extension/'background.js').is_file()
                assert not (volume/'HDM-Browser-Extension.zip').exists()
                smoke(volume/'HDM.app/Contents/MacOS/HDM', folder)
                ping_bridge(volume/'HDM.app/Contents/Helpers/HDMBridge', folder)
            finally:
                command('hdiutil', 'detach', volume)
        print('Verified installed UI and native host:', package.name, flush=True)


if __name__ == '__main__':
    if sys.platform != 'darwin':
        raise SystemExit('Native DMG packaging requires macOS. Use build.ps1 on Windows.')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    packages = package_macos()
    if args.verify:
        verify_packages(packages)
    for package in packages:
        print('Native installer:', package.name, flush=True)
