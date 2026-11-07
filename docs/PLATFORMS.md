# Platforms and installation

HDM supports **Windows and macOS**. Browser integration uses the Chromium extension.

## Windows

Download the EXE for Windows 10/11 x64 from [Releases](https://github.com/hngoos/hngoos-download-manager/releases/latest).
Run it and follow the setup wizard. Installation is per user and does not require administrator privileges.

The CMD command in the [README](../README.md) downloads version 0.1.0,
verifies its published size and pinned SHA-256, then starts the installer.

```powershell
./install.ps1 -Interactive
./install.ps1 -DownloadOnly
```

## macOS

Choose the DMG for your processor from [Releases](https://github.com/hngoos/hngoos-download-manager/releases/latest):

- Apple Silicon: `HDM-0.1.0-macOS-arm64.dmg`.
- Intel: `HDM-0.1.0-macOS-x64.dmg`.

Open the DMG, drag HDM into Applications, then launch it. The native messaging
bridge and runtime are bundled; keep the app bundle intact.

The current macOS packages target macOS 15. They use ad-hoc bundle signatures
and are not signed with Developer ID or notarized by Apple. If macOS blocks
an application you intentionally downloaded, review it in System Settings →
Privacy & Security before choosing Open Anyway.

## Browser extension

1. Click the HDM logo to open Preferences, then select your browser under **Browser**.
   Installed browsers appear in color; unavailable browsers are dimmed.
2. Open the extensions-page link in the guide and enable **Developer mode**.
3. Extract the bundled `HDM-Browser-Extension.zip` to a permanent folder. The guide shows its location.
4. Click **Load unpacked** and select the extracted folder containing `manifest.json`.
5. Click **Connect HDM** in the guide and select the same folder.
6. In the extension settings, click **Enable download capture** and accept the permission prompt.

Supported browsers on Windows and macOS: Chrome, Edge, Brave, Cốc Cốc, Opera,
Opera GX and Vivaldi. Safari uses a different extension format and is not supported.

Chrome Web Store publication is pending. Until it is published, loading the unpacked
extension is required once per browser profile. Keep the prepared folder in place.
HDM does not change browser policies or install extensions without browser consent.

If a download stays in the browser, check that the extension is enabled, download
capture permission was granted, and Preferences → Download → browser capture is on.
If HDM cannot accept a request, the original browser download is preserved.

## Optional installation from source

On macOS, Python 3.11+, Tkinter and venv are required for the source installer.
They are bundled in the DMG and are not needed to use it.

```sh
brew install python@3.13 python-tk@3.13
curl -fsSL https://raw.githubusercontent.com/hngoos/hngoos-download-manager/main/install.sh -o /tmp/hdm-install.sh
HDM_PYTHON="$(brew --prefix python@3.13)/bin/python3.13" sh /tmp/hdm-install.sh
```

For a local checkout, run `sh install.sh /absolute/path/to/checkout`.
`HDM_INSTALL_DIR` selects an absolute runtime directory.

## Application data

| System | Local application data |
| --- | --- |
| Windows | `%LOCALAPPDATA%/HDM` |
| macOS | `~/Library/Application Support/HDM` |

`HDM_DATA_DIR` overrides this location. Uninstalling the app does not remove
history or files saved elsewhere.

## Platform differences

| Capability | Windows | macOS |
| --- | --- | --- |
| Parallel HTTP downloads, pause/resume, mirrors and history | Available | Available |
| Chromium extension and native messaging | Available | Available |
| Browser session transfer | Opt-in, encrypted with DPAPI | Manually selected cookie files |
| Windows Defender scanning | Available | Unavailable |
| In-app package updates | Verified EXE installer | Verified DMG, installed through macOS |

## Native package verification

The packaging workflows build on Windows and macOS 15 (Apple Silicon and Intel).
The macOS workflow checks source installation, the packaged UI and native host
before uploading DMG artifacts. A macOS build cannot be verified by a Windows-only
local test run.
