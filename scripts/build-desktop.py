"""Build native macOS packages on macOS; Windows uses build.ps1."""

import platform
import shutil
import subprocess
import sys
from pathlib import Path

from hngoos_dm import __version__

root = Path(__file__).resolve().parents[1]
if sys.platform != 'darwin':
    raise SystemExit('This build targets macOS. Use scripts/build.ps1 on Windows.')


def run(*args):
    subprocess.run([sys.executable, *args], cwd=root, check=True)


run('scripts/fetch-js-runtime.py')
run('scripts/collect-notices.py')
run('scripts/package-extension.py')
options = ['--noconfirm', '--clean', '--paths', 'src',
           '--add-data', f'{root / "src/hngoos_dm/assets"}:hngoos_dm/assets',
           '--collect-submodules', 'yt_dlp', '--collect-data', 'yt_dlp', '--collect-all', 'yt_dlp_ejs',
           '--collect-submodules', 'openpyxl', '--collect-data', 'openpyxl', '--collect-all', 'imageio_ffmpeg',
           '--collect-all', 'pypdfium2', '--exclude-module', 'playwright',
           '--copy-metadata', 'yt-dlp', '--copy-metadata', 'imageio-ffmpeg',
           '--copy-metadata', 'pypdfium2', '--copy-metadata', 'libtorrent']
icon = root/'src/hngoos_dm/assets/branding/hdm.icns'
mac_options = ['--osx-bundle-identifier', 'com.hngoos.hdm', '--icon', str(icon)]
run('-m', 'PyInstaller', *options, *mac_options, '--onedir', '--windowed', '--name', 'HDM', 'src/hngoos_dm/launcher.py')
run('-m', 'PyInstaller', '--noconfirm', '--clean', '--onefile', '--console', '--name', 'HDMBridge',
    '--paths', 'src', 'src/hngoos_dm/bridge_launcher.py')

name = f'HDM-{__version__}-macOS-{platform.machine()}-preview'
staging = root/'build'/name
# A distinct staging folder prevents accidentally reusing another platform's files.
staging.mkdir(parents=True, exist_ok=False)
helpers = root/'dist/HDM.app/Contents/Helpers'
helpers.mkdir(exist_ok=True)
shutil.copy2(root/'dist/HDMBridge', helpers/'HDMBridge')
resources = root/'dist/HDM.app/Contents/Resources'
shutil.copytree(root/'dist/extension', resources/'extension')
shutil.copytree(root/'dist/third-party-notices', resources/'third-party-notices')
for item in ('LICENSE', 'THIRD_PARTY_NOTICES.txt'):
    shutil.copy2(root/item, resources/item)
subprocess.run(['codesign', '--force', '--deep', '--sign', '-', str(root/'dist/HDM.app')], check=True)
subprocess.run(['codesign', '--verify', '--deep', '--strict', str(root/'dist/HDM.app')], check=True)
shutil.copytree(root/'dist/HDM.app', staging/'HDM.app', symlinks=True)
shutil.copytree(root/'dist/extension', staging/'extension')
for item in ('LICENSE', 'THIRD_PARTY_NOTICES.txt'):
    shutil.copy2(root/item, staging/item)
shutil.copytree(root/'dist/third-party-notices', staging/'third-party-notices')
shutil.copy2(root/'README.md', staging/'README.md')
archive = str(root/'dist'/(name+'.zip'))
# ditto preserves bundle symlinks, executable modes and macOS metadata.
subprocess.run(['ditto', '-c', '-k', '--sequesterRsrc', '--keepParent', str(staging), archive], check=True)
print('Preview package:', archive)
run('scripts/package-native.py', '--verify')
