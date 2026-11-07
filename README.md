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

## Download

The latest published release is **v0.1.0**. The `main` branch may contain
changes listed under [Unreleased](CHANGELOG.md#unreleased).

### Windows

**Windows 10/11 · x64**

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
3. Paste a URL, choose where to save it, and click **Download** or press **Enter**.

### macOS

**macOS 15 or later · Apple Silicon and Intel**

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
See the [installation guide](docs/USAGE.md#installation) for details.

### Browser extension

Click the HDM logo to open Preferences, then select your installed browser.
Follow the guide inside the app to install the included extension ZIP and
enable download capture. No separate extension download is needed.

Supported browsers: Chrome, Edge, Brave, Cốc Cốc, Opera, Opera GX, and Vivaldi.
The extension currently requires manual installation through Developer mode.

## Contact

<p align="center">
  <a href="https://www.facebook.com/hngoos"><img src="docs/assets/contact-facebook.svg" alt="Facebook"></a>
  <a href="https://www.instagram.com/hngoos/"><img src="docs/assets/contact-instagram.svg" alt="Instagram"></a>
  <a href="mailto:1hngoos@gmail.com"><img src="docs/assets/contact-gmail.svg" alt="Email 1hngoos@gmail.com"></a>
</p>

[Report a bug](https://github.com/hngoos/hngoos-download-manager/issues/new?labels=bug) · [User guide](docs/USAGE.md) · [Privacy](docs/PRIVACY.md) · [Development](docs/DEVELOPMENT.md) · [License](LICENSE)
