<p align="center">
  <img src="docs/assets/hdm-logo.svg" width="112" height="112" alt="Hngoos Download Manager (HDM) logo">
</p>

<h1 align="center">Hngoos Download Manager</h1>

<p align="center">
  <a href="https://www.facebook.com/hngoos"><img src="https://img.shields.io/badge/Facebook-hngoos-0866ff?style=flat-square&amp;logo=facebook&amp;logoColor=white" alt="HDM on Facebook"></a>
  <a href="https://www.instagram.com/hngoos/"><img src="https://img.shields.io/badge/Instagram-hngoos-e4405f?style=flat-square&amp;logo=instagram&amp;logoColor=white" alt="HDM on Instagram"></a>
  <a href="mailto:1hngoos@gmail.com"><img src="https://img.shields.io/badge/Gmail-1hngoos%40gmail.com-EA4335?style=flat-square&amp;logo=gmail&amp;logoColor=white" alt="Email HDM at 1hngoos@gmail.com"></a>
</p>

> Download, organize, and process your files in one desktop app.

Hngoos Download Manager (HDM) brings resumable downloads, batch imports, video and audio tools, and file
checks into a single workspace. Download history and processing stay on your
computer.

<p align="center">
  <a href="https://github.com/hngoos/hngoos-download-manager/releases/download/v0.1.1/HDM-Setup-0.1.1.exe"><img src="docs/assets/install-windows.svg" width="190" height="72" alt="Download HDM for Windows 10/11 x64"></a>
  <a href="#macos"><img src="docs/assets/install-macos.svg" width="190" height="72" alt="Download HDM for macOS"></a>
  <a href="https://github.com/hngoos/hngoos-download-manager/releases/download/v0.1.1/HDM-0.1.1-Linux-x64.AppImage"><img src="docs/assets/install-linux.svg" width="190" height="72" alt="Download HDM for Linux"></a>
</p>
<p align="center">
  <a href="#mobile"><img src="docs/assets/install-mobile.svg" width="190" height="72" alt="Mobile: coming soon"></a>
  <a href="https://github.com/hngoos/hngoos-download-manager/releases/download/v0.1.1/HDM-Browser-Extension.zip"><img src="docs/assets/install-browser.svg" width="190" height="72" alt="Download the HDM browser extension ZIP"></a>
</p>

## Features

- **Resumable downloads** — use up to 32 connections, pause and continue supported
  transfers, retry network failures, and adapt to server connection limits.
- **Flexible sources** — use mirrors, refresh expired URLs after verification,
  and change the destination while a download is in progress.
- **Batch workflows** — paste link–filename columns or import CSV, TXT and XLSX;
  preview names, keep row order, and export a completion report.
- **Video and audio** — choose available formats, download playlists, extract
  audio, and trim, join, convert or compress files locally.
- **File checks** — verify checksums, inspect suspicious names and archive
  entries, and flag risky downloads before opening them.
- **Document tools** — redact PDF regions and capture web pages as PDF or images
  when the required browser runtime is available.
- **Daily conveniences** — schedule downloads, select bandwidth presets, organize
  files by type, and keep transfer history on your computer.

Features depend on the source website, installed tools and platform.
See [platform support](docs/PLATFORMS.md) and the [feature guide](docs/FEATURES.md)
for details. HDM does not bypass DRM or website access controls.

## Download and quick start

<a id="windows"></a>

<details>
<summary><strong>Windows</strong></summary>

1. [Download the installer](https://github.com/hngoos/hngoos-download-manager/releases/download/v0.1.1/HDM-Setup-0.1.1.exe).
2. Run `HDM-Setup-0.1.1.exe` and complete the setup.
3. Open HDM, paste a link, choose a save folder, and start downloading.

Or install from **Command Prompt (CMD)**:

```cmd
curl.exe -fL https://raw.githubusercontent.com/hngoos/hngoos-download-manager/main/install.ps1 -o "%TEMP%\HDM-install.ps1" && powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%TEMP%\HDM-install.ps1"
```

The script verifies the installer's size and SHA-256 before installing for your
account. No administrator privileges are required. The execution-policy option
applies to this PowerShell process. [More installation options](docs/PLATFORMS.md#windows).

</details>

<a id="macos"></a>

<details>
<summary><strong>macOS</strong></summary>

Download the DMG for your Mac:

- [Apple Silicon (M-series)](https://github.com/hngoos/hngoos-download-manager/releases/download/v0.1.1/HDM-0.1.1-macOS-arm64.dmg)
- [Intel](https://github.com/hngoos/hngoos-download-manager/releases/download/v0.1.1/HDM-0.1.1-macOS-x64.dmg)

Open the DMG, drag **HDM** to **Applications**, then open it from there.
These desktop previews are tested on macOS 15 and include the application runtime.

</details>

<a id="linux"></a>

<details>
<summary><strong>Linux</strong></summary>

For Ubuntu/Debian x64, [download the DEB](https://github.com/hngoos/hngoos-download-manager/releases/download/v0.1.1/HDM-0.1.1-Linux-x64.deb), then install:

```sh
sudo apt install ./HDM-0.1.1-Linux-x64.deb
```

For other compatible x64 desktops, [download the AppImage](https://github.com/hngoos/hngoos-download-manager/releases/download/v0.1.1/HDM-0.1.1-Linux-x64.AppImage):

```sh
chmod +x HDM-0.1.1-Linux-x64.AppImage
./HDM-0.1.1-Linux-x64.AppImage
```

The Linux previews require glibc 2.35 or later. Python is bundled.
[Platform support and optional source installation](docs/PLATFORMS.md).

</details>

<a id="browser-extension"></a>

<details>
<summary><strong>Browser extension</strong></summary>

1. [Download the extension ZIP](https://github.com/hngoos/hngoos-download-manager/releases/download/v0.1.1/HDM-Browser-Extension.zip) and extract it to a permanent folder.
2. Open your browser's extensions page: `chrome://extensions`, `edge://extensions`,
   or `brave://extensions`.
3. Enable **Developer mode**, click **Load unpacked**, and choose the extracted
   folder containing `manifest.json`.
4. Copy the extension ID. Open HDM → **Browser (Trình duyệt)**, paste the ID, and register the
   connection. In the extension's options, click **Test connection (Kiểm tra kết nối)**.

Install the HDM desktop app first. Keep the extracted folder after installation.
The ZIP is loaded manually; Chrome Web Store publication is pending.

</details>

<a id="mobile"></a>

<details>
<summary><strong>Mobile — Coming soon</strong></summary>

**Coming soon.** Android and iOS applications are planned for a future release.

</details>

## Help and resources

- [User guide](docs/USAGE.md)
- [Report a problem or suggest a feature](https://github.com/hngoos/hngoos-download-manager/issues)
- [Privacy](docs/PRIVACY.md) · [Security](SECURITY.md) · [Contributing](CONTRIBUTING.md) · [Development](docs/DEVELOPMENT.md)
