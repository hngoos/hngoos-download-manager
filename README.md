<p align="center">
  <img src="docs/assets/hdm-wordmark-monochrome.svg" width="740" alt="Hngoos Download Manager (HDM) — Easy &amp; fast">
</p>

> Download, organize, and process your files in one desktop app.

Hngoos Download Manager (HDM) brings resumable downloads, batch imports, video and audio tools, and file
checks into a single workspace. Download history and processing stay on your
computer.

<p align="center">
  <a href="https://github.com/hngoos/hngoos-download-manager/releases/download/v0.1.1/HDM-Setup-0.1.1.exe"><img src="docs/assets/install-windows.svg" width="20%" alt="Download HDM for Windows 10/11 x64"></a><a href="#macos"><img src="docs/assets/install-macos.svg" width="20%" alt="Download HDM for macOS"></a><a href="https://github.com/hngoos/hngoos-download-manager/releases/download/v0.1.1/HDM-0.1.1-Linux-x64.AppImage"><img src="docs/assets/install-linux.svg" width="20%" alt="Download HDM for Linux"></a><a href="https://github.com/hngoos/hngoos-download-manager/releases/download/v0.1.1/HDM-Browser-Extension.zip"><img src="docs/assets/install-browser.svg" width="20%" alt="Download the HDM browser extension ZIP"></a><a href="#mobile"><img src="docs/assets/install-mobile.svg" width="20%" alt="Mobile: coming soon"></a>
</p>

## Features

- **Resumable downloads** — use up to 32 connections, pause and resume supported
  downloads, and automatically retry after network errors.
- **Mirrors and recovery** — use verified mirrors, replace expired links, and
  change the save location during a download.
- **Batch downloads** — paste links and filenames or import CSV, TXT and XLSX
  files. Preview names, preserve row order, and export completion reports.
- **Video and audio tools** — choose available formats, download playlists,
  extract audio, and trim, merge, convert or compress files locally.
- **File safety checks** — verify checksums and check filenames and archive
  contents for signs of risk.
- **PDF and web capture** — redact PDF content and save web pages as PDFs or
  images with a compatible browser runtime.
- **Scheduling and organization** — schedule downloads, limit bandwidth,
  organize files by type, and keep download history on your computer.

Availability depends on the source website, installed tools and operating system.
See [platform support](docs/PLATFORMS.md) and the [feature guide](docs/FEATURES.md).
HDM does not bypass DRM or website access controls.

## Download

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

The script checks the installer's size and SHA-256, then installs HDM for your
account without administrator privileges. [More installation options](docs/PLATFORMS.md#windows).

</details>

<a id="macos"></a>

<details>
<summary><strong>macOS</strong></summary>

Download the DMG for your Mac:

- [Apple Silicon (M-series)](https://github.com/hngoos/hngoos-download-manager/releases/download/v0.1.1/HDM-0.1.1-macOS-arm64.dmg)
- [Intel](https://github.com/hngoos/hngoos-download-manager/releases/download/v0.1.1/HDM-0.1.1-macOS-x64.dmg)

Open the DMG, drag **HDM** to **Applications**, then launch HDM from Applications.
These preview builds are tested on macOS 15. Python is included.

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
4. Copy the extension ID. In HDM, open **Browser (Trình duyệt)**, paste the ID,
   and register the connection.
5. Open the extension options and click **Test connection (Kiểm tra kết nối)**.

Install the HDM desktop app first. Keep the extracted folder after installation.
The ZIP is loaded manually; Chrome Web Store publication is pending.

</details>

<a id="mobile"></a>

<details>
<summary><strong>Mobile</strong></summary>

**Coming soon.** Android and iOS applications are planned for a future release.

</details>

## Contact

<p align="center">
  <a href="https://www.facebook.com/hngoos"><img src="docs/assets/contact-facebook.svg" alt="HDM on Facebook"></a>
  <a href="https://www.instagram.com/hngoos/"><img src="docs/assets/contact-instagram.svg" alt="HDM on Instagram"></a>
  <a href="mailto:1hngoos@gmail.com"><img src="docs/assets/contact-gmail.svg" alt="Email HDM at 1hngoos@gmail.com"></a>
</p>
