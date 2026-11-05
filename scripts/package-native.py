"""Create and verify native installers from the desktop build on the target OS."""

import argparse
import hashlib
import json
import os
import platform
import shutil
import struct
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

from hngoos_dm import __version__

ROOT = Path(__file__).resolve().parents[1]
ICON = ROOT/'browser-extension/assets/icons/hdm-128.png'
TOOLS = {
    'appimagetool-x86_64.AppImage': (
        'https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage',
        '62aebc77c2149e96b593b94da9bbd1881e0984a56399ff6d7a03b7ddd7c9ce68'),
    'runtime-x86_64': (
        'https://github.com/AppImage/type2-runtime/releases/download/continuous/runtime-x86_64',
        '617aa77314d57c8b8e4fae9c3f0b35af7b30d5529cb69e98f64f92510ed98a46'),
}


def fetch_tool(name):
    url, expected = TOOLS[name]
    path = ROOT/'tools/native-packaging'/name
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        with urllib.request.urlopen(url, timeout=60) as response:
            data = response.read(32*1024*1024+1)
        if len(data) > 32*1024*1024 or hashlib.sha256(data).hexdigest() != expected:
            raise ValueError('Packaging tool does not match its pinned SHA-256: '+name)
        path.write_bytes(data)
    path.chmod(0o755)
    return path


def command(*args, **kwargs):
    return subprocess.run([str(arg) for arg in args], check=True, **kwargs)


def desktop_entry(executable):
    return ('[Desktop Entry]\nType=Application\nName=HDM\n'
            'Comment=Download, organize and process your files\n'
            f'Exec={executable}\nIcon=hdm\nTerminal=false\nCategories=Network;FileTransfer;\n')


def package_linux():
    if platform.machine() not in {'x86_64', 'amd64'}:
        raise ValueError('Linux installer packaging currently targets x86_64.')
    build = ROOT/'build/native-packages'
    package = build/'deb'
    package.mkdir(parents=True, exist_ok=False)
    shutil.copytree(ROOT/'dist/HDM', package/'opt/hdm', symlinks=True)
    (package/'usr/bin').mkdir(parents=True)
    (package/'usr/bin/hdm').symlink_to('/opt/hdm/HDM')
    (package/'usr/share/applications').mkdir(parents=True)
    (package/'usr/share/applications/com.hngoos.hdm.desktop').write_text(desktop_entry('/opt/hdm/HDM'))
    icons = package/'usr/share/icons/hicolor/128x128/apps'
    icons.mkdir(parents=True)
    shutil.copy2(ICON, icons/'hdm.png')
    control = package/'DEBIAN'
    control.mkdir()
    size = sum(p.stat().st_size for p in (package/'opt').rglob('*') if p.is_file())//1024
    (control/'control').write_text(
        f'Package: hngoos-download-manager\nVersion: {__version__}\nArchitecture: amd64\n'
        f'Maintainer: hngoos <noreply@users.noreply.github.com>\nInstalled-Size: {size}\n'
        'Section: net\nPriority: optional\n'
        'Depends: libc6 (>= 2.35), libx11-6, libxext6, libxrender1, libxft2, libfontconfig1, libgl1, libopengl0\n'
        'Homepage: https://github.com/hngoos/hngoos-download-manager\n'
        'Description: HDM desktop download manager\n'
        ' Resumable downloads, batch imports, local media tools and file checks.\n')
    deb = ROOT/f'dist/HDM-{__version__}-Linux-x64.deb'
    command('dpkg-deb', '--root-owner-group', '--build', package, deb)

    appdir = build/'HDM.AppDir'
    appdir.mkdir()
    shutil.copytree(ROOT/'dist/HDM', appdir/'usr/lib/hdm', symlinks=True)
    shutil.copy2(ICON, appdir/'hdm.png')
    notices = appdir/'usr/share/licenses/hdm'
    notices.mkdir(parents=True)
    shutil.copy2(ROOT/'docs/licenses/appimage-runtime.txt', notices/'appimage-runtime.txt')
    (appdir/'hdm.desktop').write_text(desktop_entry('HDM'))
    launcher = appdir/'AppRun'
    launcher.write_text('#!/bin/sh\nset -eu\n'
                        'hdm_appdir="${APPDIR:-$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)}"\n'
                        'exec "$hdm_appdir/usr/lib/hdm/HDM" "$@"\n')
    launcher.chmod(0o755)
    appimage = ROOT/f'dist/HDM-{__version__}-Linux-x64.AppImage'
    tool = fetch_tool('appimagetool-x86_64.AppImage')
    runtime = fetch_tool('runtime-x86_64')
    command(tool, '--appimage-extract-and-run', '--no-appstream', '--runtime-file', runtime, appdir, appimage,
            env={**os.environ, 'ARCH': 'x86_64'})
    appimage.chmod(0o755)
    return [deb, appimage]


def package_macos():
    arch = 'arm64' if platform.machine() == 'arm64' else 'x64'
    image_root = ROOT/'build/native-packages/dmg'
    image_root.mkdir(parents=True, exist_ok=False)
    shutil.copytree(ROOT/'dist/HDM.app', image_root/'HDM.app', symlinks=True)
    (image_root/'Applications').symlink_to('/Applications')
    image = ROOT/f'dist/HDM-{__version__}-macOS-{arch}.dmg'
    command('hdiutil', 'create', '-volname', 'HDM', '-srcfolder', image_root, '-ov', '-format', 'UDZO', image)
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
    if sys.platform == 'linux':
        args = ['xvfb-run', '-a', *args]
    command(*args, timeout=90, env={**os.environ, **(environment or {})})


def verify_packages(packages):
    for package in packages:
        with tempfile.TemporaryDirectory(prefix='hdm-package-check-') as temporary:
            folder = Path(temporary)
            if package.suffix == '.deb':
                command('dpkg-deb', '--info', package)
                command('dpkg-deb', '--extract', package, folder/'extracted')
                binary = folder/'extracted/opt/hdm/HDM'
                smoke(binary, folder)
                ping_bridge(binary.with_name('HDMBridge'), folder)
            elif package.suffix == '.AppImage':
                command(package, '--appimage-extract', cwd=folder, stdout=subprocess.DEVNULL)
                extracted = folder/'squashfs-root'
                environment = {'APPDIR': str(extracted), 'APPIMAGE': str(package)}
                smoke(extracted/'AppRun', folder, environment)
                # Test the persistent native launcher after extraction has finished.
                from unittest.mock import patch

                from hngoos_dm.browser import register
                with patch.dict(os.environ, environment), patch('hngoos_dm.browser.host_directories',
                                                               return_value=[folder/'hosts']):
                    manifest = register('a'*32, extracted/'usr/lib/hdm/HDMBridge', folder/'data')
                launcher = Path(json.loads(manifest.read_text())['path'])
                ping_bridge(launcher, folder)
            else:
                volume = folder/'volume'
                command('hdiutil', 'attach', '-readonly', '-nobrowse', '-mountpoint', volume, package)
                try:
                    smoke(volume/'HDM.app/Contents/MacOS/HDM', folder)
                    ping_bridge(volume/'HDM.app/Contents/Helpers/HDMBridge', folder)
                finally:
                    command('hdiutil', 'detach', volume)
        print('Verified installed UI and native host:', package.name, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    packages = package_macos() if sys.platform == 'darwin' else package_linux()
    if args.verify:
        verify_packages(packages)
    for package in packages:
        print('Native installer:', package.name, flush=True)
