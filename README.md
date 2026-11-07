<p align="center">
  <img src="docs/assets/hdm-wordmark-square.svg" width="740" alt="Hngoos Download Manager (HDM) — Easy &amp; fast">
</p>

<p align="center">
  <a href="#windows"><img src="docs/assets/install-windows.svg" width="49%" alt="Download HDM for Windows 10/11 x64"></a><a href="#macos"><img src="docs/assets/install-macos.svg" width="49%" alt="Download HDM for macOS"></a>
</p>

Available for **Windows and macOS**. Chromium browser integration is configured inside HDM.

## Features

- **Fast downloads** — up to 32 connections, shared chunk scheduling, pause/resume,
  automatic retries, verified mirrors and expired-link recovery.
- **Built-in safety checks** — inspect file content, names, macros and archives,
  verify checksums and quarantine risky files. Optional Windows Defender scanning.
- **One download screen** — paste a link and choose original files,
  video or MP3/M4A from supported sources, with details revealed after Enter.
- **Everyday essentials** — batch imports, scheduling, bandwidth limits,
  background operation, optional launch at sign-in and in-app updates.

## Download

<a id="windows"></a>

<details>
<summary><strong>Windows</strong></summary>

### Download

[Windows 10/11 x64 installer](https://github.com/hngoos/hngoos-download-manager/releases/download/v0.1.0/HDM-Setup-0.1.0.exe)

Or install from **Command Prompt (CMD)**:

```cmd
curl.exe -fL https://raw.githubusercontent.com/hngoos/hngoos-download-manager/main/install.ps1 -o "%TEMP%\HDM-install.ps1" && powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%TEMP%\HDM-install.ps1"
```

### Installation

1. Run the downloaded `.exe` and follow the setup wizard, or run the CMD command above.
2. Open **HDM** from the Start menu.
3. Paste a link, choose the available options, then click **Download** or press **Enter**.

For browser integration, click the HDM logo → **Browser**, then select your browser.
The extension ZIP is included with HDM. Follow the installation guide inside the
app, then enable download capture in the extension.

The CMD installer verifies the package before installing it for your account.

</details>

<a id="macos"></a>

<details>
<summary><strong>macOS</strong></summary>

### Download

- [Apple Silicon (M-series)](https://github.com/hngoos/hngoos-download-manager/releases/download/v0.1.0/HDM-0.1.0-macOS-arm64.dmg)
- [Intel](https://github.com/hngoos/hngoos-download-manager/releases/download/v0.1.0/HDM-0.1.0-macOS-x64.dmg)

Or download from **Terminal** (automatically selects Apple Silicon or Intel):

```sh
arch=$(uname -m); [ "$arch" = "x86_64" ] && arch=x64
curl -fL "https://github.com/hngoos/hngoos-download-manager/releases/download/v0.1.0/HDM-0.1.0-macOS-$arch.dmg" -o HDM.dmg
```

### Installation

1. Open the downloaded `.dmg`.
2. Drag **HDM** to **Applications**.
3. Launch **HDM** from Applications.

Requires macOS 15. See [platform support](docs/PLATFORMS.md#macos) for signing requirements.

</details>

## Contact

<p align="center">
  <a href="https://www.facebook.com/hngoos"><img src="docs/assets/contact-facebook.svg" alt="HDM on Facebook"></a>
  <a href="https://www.instagram.com/hngoos/"><img src="docs/assets/contact-instagram.svg" alt="HDM on Instagram"></a>
  <a href="mailto:1hngoos@gmail.com"><img src="docs/assets/contact-gmail.svg" alt="Email HDM at 1hngoos@gmail.com"></a>
</p>
