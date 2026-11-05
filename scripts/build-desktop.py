"""Build native macOS/Linux preview packages on the target operating system."""

import platform
import shutil
import subprocess
import sys
from pathlib import Path

from hngoos_dm import __version__

root = Path(__file__).resolve().parents[1]
if sys.platform not in {'darwin', 'linux'}:
    raise SystemExit('Use scripts/build.ps1 to build Windows installers.')


def run(*args):
    subprocess.run([sys.executable, *args], cwd=root, check=True)


run('scripts/collect-notices.py')
options = ['--noconfirm', '--clean', '--paths', 'src', '--collect-data', 'hngoos_dm',
           '--collect-all', 'yt_dlp', '--collect-all', 'openpyxl', '--collect-all', 'imageio_ffmpeg',
           '--collect-all', 'pypdfium2', '--collect-all', 'playwright',
           '--copy-metadata', 'yt-dlp', '--copy-metadata', 'imageio-ffmpeg',
           '--copy-metadata', 'pypdfium2', '--copy-metadata', 'libtorrent']
mac_options = []
if sys.platform == 'darwin':
    from PIL import Image
    icon = root/'build/HDM.icns'
    icon.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(root/'browser-extension/assets/icons/hdm-128.png') as image:
        image.resize((1024, 1024)).save(icon)
    mac_options = ['--osx-bundle-identifier', 'com.hngoos.hdm', '--icon', str(icon)]
run('-m', 'PyInstaller', *options, *mac_options, '--onedir', '--windowed', '--name', 'HDM', 'src/hngoos_dm/launcher.py')
run('-m', 'PyInstaller', '--noconfirm', '--clean', '--onefile', '--console', '--name', 'HDMBridge',
    '--paths', 'src', 'src/hngoos_dm/bridge_launcher.py')

label = 'macOS' if sys.platform == 'darwin' else 'Linux'
name = f'HDM-{__version__}-{label}-{platform.machine()}-preview'
staging = root/'build'/name
# A distinct staging folder prevents accidentally reusing another platform's files.
staging.mkdir(parents=True, exist_ok=False)
if sys.platform == 'darwin':
    helpers = root/'dist/HDM.app/Contents/Helpers'
    helpers.mkdir(exist_ok=True)
    shutil.copy2(root/'dist/HDMBridge', helpers/'HDMBridge')
    resources = root/'dist/HDM.app/Contents/Resources'
    shutil.copytree(root/'dist/third-party-notices', resources/'third-party-notices')
    for item in ('LICENSE', 'THIRD_PARTY_NOTICES.md'):
        shutil.copy2(root/item, resources/item)
    subprocess.run(['codesign', '--force', '--deep', '--sign', '-', str(root/'dist/HDM.app')], check=True)
    subprocess.run(['codesign', '--verify', '--deep', '--strict', str(root/'dist/HDM.app')], check=True)
    shutil.copytree(root/'dist/HDM.app', staging/'HDM.app', symlinks=True)
else:
    shutil.copy2(root/'dist/HDMBridge', root/'dist/HDM/HDMBridge')
    shutil.copytree(root/'dist/third-party-notices', root/'dist/HDM/third-party-notices')
    for item in ('LICENSE', 'THIRD_PARTY_NOTICES.md'):
        shutil.copy2(root/item, root/'dist/HDM'/item)
    shutil.copytree(root/'dist/HDM', staging/'HDM', symlinks=True)
for item in ('LICENSE', 'THIRD_PARTY_NOTICES.md'):
    shutil.copy2(root/item, staging/item)
shutil.copytree(root/'dist/third-party-notices', staging/'third-party-notices')
shutil.copy2(root/'docs/PLATFORMS.md', staging/'INSTALL.md')
if sys.platform == 'darwin':
    archive = str(root/'dist'/(name+'.zip'))
    # ditto preserves bundle symlinks, executable modes and macOS metadata.
    subprocess.run(['ditto', '-c', '-k', '--sequesterRsrc', '--keepParent', str(staging), archive], check=True)
else:
    archive = shutil.make_archive(str(root/'dist'/name), 'gztar', staging.parent, staging.name)
print('Preview package:', archive)
run('scripts/package-native.py', '--verify')
