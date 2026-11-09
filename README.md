<p align="center">
  <img src="docs/assets/hdm-wordmark-square.svg" width="740" alt="Hngoos Download Manager">
</p>

Hngoos Download Manager (HDM) is a desktop application for Windows and macOS.
Download files with parallel connections, choose available video and audio
formats, and manage transfers in one place.

<p align="center">
  <a href="#windows"><img src="docs/assets/install-windows.svg" width="49%" alt="Download for Windows"></a><a href="#macos"><img src="docs/assets/install-macos.svg" width="49%" alt="Download for macOS"></a>
</p>

## Features

- **Parallel downloads:** up to 32 HTTP connections, pause and resume,
  automatic retries, and recovery from interrupted transfers.
- **Video and audio:** format and quality choices from supported sources,
  with MP3 and M4A audio conversion.
- **File checks:** checksum verification, local content inspection, and
  Windows Defender scanning on Windows.
- **Download history:** progress, transfer speed, scan results, and a record
  of completed or missing files.
- **Browser integration:** send supported downloads from Chromium browsers
  to HDM through the included extension.
- **Personal preferences:** light and dark themes, Vietnamese and English,
  proxy settings, optional launch at sign-in, and verified in-app updates.
- **Compact layout:** text and icons scale with the window down to readable
  minimums at 800 × 500; only the download
  history scrolls.

## Download

The current release is **v0.1.0**.

### Windows

**Windows 10/11 | x64**

#### Download

[Download the Windows installer](https://github.com/hngoos/hngoos-download-manager/releases/download/v0.1.0/HDM-Setup-0.1.0.exe)

Or install from Command Prompt (CMD):

```cmd
curl.exe -fL https://raw.githubusercontent.com/hngoos/hngoos-download-manager/main/install.ps1 -o "%TEMP%\HDM-install.ps1" && powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%TEMP%\HDM-install.ps1"
```

The command verifies the published package size and SHA-256 before starting setup.

#### Installation

1. Run the installer and complete setup. Installation is per user.
2. Open **HDM** from the Start menu.
3. Paste a URL, review the filename, and click **Download** or press **Enter**.

Click the HDM logo to change the download folder in Preferences.

### macOS

**macOS 15 or later | Apple Silicon and Intel**

#### Download

- [Download for Apple Silicon](https://github.com/hngoos/hngoos-download-manager/releases/download/v0.1.0/HDM-0.1.0-macOS-arm64.dmg)
- [Download for Intel](https://github.com/hngoos/hngoos-download-manager/releases/download/v0.1.0/HDM-0.1.0-macOS-x64.dmg)

Or download the matching package from Terminal:

```sh
hdm_arch=$(uname -m)
[ "$hdm_arch" = "x86_64" ] && hdm_arch=x64
curl -fL "https://github.com/hngoos/hngoos-download-manager/releases/download/v0.1.0/HDM-0.1.0-macOS-$hdm_arch.dmg" -o HDM.dmg
```

#### Installation

1. Open the downloaded `.dmg`.
2. Drag **HDM** to **Applications**.
3. Open **HDM** from Applications.

The current macOS packages use ad-hoc signatures and are not notarized by Apple.
If macOS blocks the app, review it in **System Settings → Privacy & Security**.

### Browser extension

Click the HDM logo to open Preferences, then select your installed browser.
Follow the three-step guide inside the app to load the included `extension`
folder. HDM connects automatically; no extra connection button or separate
extension download is needed. Use the extension popup to turn download capture
on or off, download the current page/video, or show the video download button.

Supported browsers: Chrome, Edge, Brave, Cốc Cốc, Opera, Opera GX, and Vivaldi.
The extension currently requires manual installation through Developer mode.

## Build from source

Use Python 3.11 or later with Tkinter, Node.js 22 or later, and Inno Setup 6
for Windows installers. Build on the target operating system.

```sh
python -m pip install -e ".[media,processing,excel,pdf,web,tray,torrent,updates,dev,build]"
npm ci --prefix browser-extension --ignore-scripts
python -m unittest discover -s tests -v
node --test browser-extension/test/*.test.js
python -m ruff check .
```

Windows codec builds require a MinGW-w64 environment with GCC, Make, NASM,
CMake, Ninja, Meson and pkgconf (the CI workflow uses MSYS2 MINGW64).
Prepare the pinned sources with `python scripts/prepare-ffmpeg.py`, then run
`bash scripts/build-ffmpeg.sh` in that environment. The build retains software
AV1 decoding and H.264/MP3/AAC processing, and creates a separate archive of
the corresponding codec sources for redistribution.

Then run `scripts/build.ps1` in PowerShell and compile
`scripts/installer.iss` with Inno Setup. On macOS, run
`python scripts/build-desktop.py`. Build outputs are written to `dist/`.

Website capture uses an installed Chromium browser with a temporary profile.
YouTube JavaScript support uses bundled QuickJS-NG; Playwright and its Node
runtime are only needed by development tooling and browser tests.

Source code is in `src/hngoos_dm/`; the browser extension is in
`browser-extension/`. Local environments, caches, reports, and generated
packages are excluded from the repository. Third-party license notices
accompany binary distributions.

## Contact

<p align="left">
  <a href="https://www.facebook.com/hngoos"><img src="docs/assets/contact-facebook.svg" width="40" height="40" alt="Facebook"></a>
  <a href="https://www.instagram.com/hngoos/"><img src="docs/assets/contact-instagram.svg" width="40" height="40" alt="Instagram"></a>
  <a href="mailto:1hngoos@gmail.com"><img src="docs/assets/contact-gmail.svg" width="40" height="40" alt="Email 1hngoos@gmail.com"></a>
  <a href="https://github.com/hngoos"><img src="docs/assets/contact-github.svg" width="40" height="40" alt="GitHub hngoos"></a>
</p>

[Report a bug](https://github.com/hngoos/hngoos-download-manager/issues/new?labels=bug) · [License](LICENSE)
