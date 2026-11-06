<p align="center">
  <img src="docs/assets/hdm-wordmark-square.svg" width="740" alt="Hngoos Download Manager (HDM) — Easy &amp; fast">
</p>

<p align="center">
  <a href="https://github.com/hngoos/hngoos-download-manager/releases/download/v0.1.2/HDM-Setup-0.1.2.exe"><img src="docs/assets/install-windows.svg" width="20%" alt="Download HDM for Windows 10/11 x64"></a><a href="#macos"><img src="docs/assets/install-macos.svg" width="20%" alt="Download HDM for macOS"></a><a href="https://github.com/hngoos/hngoos-download-manager/releases/download/v0.1.2/HDM-0.1.2-Linux-x64.AppImage"><img src="docs/assets/install-linux.svg" width="20%" alt="Download HDM for Linux"></a><a href="https://github.com/hngoos/hngoos-download-manager/releases/download/v0.1.2/HDM-Browser-Extension.zip"><img src="docs/assets/install-browser.svg" width="20%" alt="Download the HDM browser extension ZIP"></a><a href="#mobile"><img src="docs/assets/install-mobile.svg" width="20%" alt="Mobile: coming soon"></a>
</p>

## Features

- **Resumable downloads** — download in parallel, pause, resume, and retry automatically.
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

## Download

<a id="windows"></a>

<details>
<summary><strong>Windows</strong></summary>

### Download

[Windows 10/11 x64 installer](https://github.com/hngoos/hngoos-download-manager/releases/download/v0.1.2/HDM-Setup-0.1.2.exe)

Or install from **Command Prompt (CMD)**:

```cmd
curl.exe -fL https://raw.githubusercontent.com/hngoos/hngoos-download-manager/main/install.ps1 -o "%TEMP%\HDM-install.ps1" && powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%TEMP%\HDM-install.ps1"
```

### Installation

1. Run the downloaded `.exe` and follow the setup wizard, or run the CMD command above.
2. Open **HDM** from the Start menu.
3. Paste a link, choose a folder, and start downloading.

The CMD installer verifies the package before installing it for your account.

</details>

<a id="macos"></a>

<details>
<summary><strong>macOS</strong></summary>

### Download

- [Apple Silicon (M-series)](https://github.com/hngoos/hngoos-download-manager/releases/download/v0.1.2/HDM-0.1.2-macOS-arm64.dmg)
- [Intel](https://github.com/hngoos/hngoos-download-manager/releases/download/v0.1.2/HDM-0.1.2-macOS-x64.dmg)

Or download from **Terminal** (automatically selects Apple Silicon or Intel):

```sh
arch=$(uname -m); [ "$arch" = "x86_64" ] && arch=x64
curl -fL "https://github.com/hngoos/hngoos-download-manager/releases/download/v0.1.2/HDM-0.1.2-macOS-$arch.dmg" -o HDM.dmg
```

### Installation

1. Open the downloaded `.dmg`.
2. Drag **HDM** to **Applications**.
3. Launch **HDM** from Applications.

Requires macOS 15. See [platform support](docs/PLATFORMS.md#macos) for signing requirements.

</details>

<a id="linux"></a>

<details>
<summary><strong>Linux</strong></summary>

### Download

[DEB — Ubuntu/Debian x64](https://github.com/hngoos/hngoos-download-manager/releases/download/v0.1.2/HDM-0.1.2-Linux-x64.deb) ·
[AppImage — Linux x64](https://github.com/hngoos/hngoos-download-manager/releases/download/v0.1.2/HDM-0.1.2-Linux-x64.AppImage)

Or download the DEB from **Terminal**:

```sh
curl -fLO https://github.com/hngoos/hngoos-download-manager/releases/download/v0.1.2/HDM-0.1.2-Linux-x64.deb
```

### Installation

For Ubuntu/Debian, install the downloaded DEB and launch **HDM** from your applications:

```sh
sudo apt install ./HDM-0.1.2-Linux-x64.deb
```

For AppImage, make the downloaded file executable and run it:

```sh
chmod +x HDM-0.1.2-Linux-x64.AppImage
./HDM-0.1.2-Linux-x64.AppImage
```

Requires glibc 2.35 or later. [Platform support](docs/PLATFORMS.md#linux).

</details>

<a id="browser-extension"></a>

<details>
<summary><strong>Browser extension</strong></summary>

### Download

[Chromium browser extension ZIP](https://github.com/hngoos/hngoos-download-manager/releases/download/v0.1.2/HDM-Browser-Extension.zip)

### Installation

1. Install the HDM desktop app, then extract the ZIP to a permanent folder.
2. Open your browser's extensions page: `chrome://extensions`, `edge://extensions`,
   or `brave://extensions`.
3. Enable **Developer mode**, click **Load unpacked**, and choose the extracted
   folder containing `manifest.json`.
4. Copy the extension ID. In HDM, open **Browser (Trình duyệt)**, paste the ID,
   and register the connection.
5. Open the extension options and click **Test connection (Kiểm tra kết nối)**.

Keep the extracted folder after installation.

</details>

<a id="mobile"></a>

<details>
<summary><strong>Mobile</strong></summary>

### Download

Coming soon for Android and iOS.

### Installation

Instructions will be available when the mobile apps are released.

</details>

## Contact

<p align="center">
  <a href="https://www.facebook.com/hngoos"><img src="docs/assets/contact-facebook.svg" alt="HDM on Facebook"></a>
  <a href="https://www.instagram.com/hngoos/"><img src="docs/assets/contact-instagram.svg" alt="HDM on Instagram"></a>
  <a href="mailto:1hngoos@gmail.com"><img src="docs/assets/contact-gmail.svg" alt="Email HDM at 1hngoos@gmail.com"></a>
</p>
