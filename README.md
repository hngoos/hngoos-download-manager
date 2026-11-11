<p align="center">
  <img src="docs/assets/hdm-wordmark-square.svg" width="740" alt="Hngoos Download Manager">
</p>

Hngoos Download Manager (HDM) is a desktop application for Windows and macOS.
Download files with parallel connections, choose available video and audio
formats, and manage transfers in one place.

<p align="center">
  <a href="#windows"><img src="docs/assets/install-windows.svg" width="49%" alt="Download for Windows"></a><img src="docs/assets/install-macos.svg" width="49%" alt="macOS downloads temporarily unavailable">
</p>

## Features

- **Parallel downloads:** up to 32 HTTP connections, pause and resume,
  automatic retries, and recovery from interrupted transfers.
- **Video and audio:** format and quality choices from supported sources,
  with MP3, M4A, and PCM WAV audio conversion.
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

The current Windows release is **v0.1.6**.

HDM supports interrupted-download recovery, verifies saved HTTP ranges,
and keeps large download histories responsive. Windows Defender scans run in a
shared background queue; missing files no longer show an overlapping safety result. Supported audio exports include MP3, M4A, WAV, AAC,
FLAC, AIFF, WMA, and AC3. Video containers include MP4, WebM, MKV, MOV, and M4V,
where compatible with the source. Available resolutions come from the source;
changing the container does not increase video quality.
TikTok photo posts download their source images in order without converting them to video.

### Windows

**Windows 10/11 | x64**

#### Download

[Download the Windows installer](https://github.com/hngoos/hngoos-download-manager/releases/download/v0.1.6/HDM-Setup-0.1.6.exe)

Or install from Command Prompt (CMD):

```cmd
curl.exe -fL https://raw.githubusercontent.com/hngoos/hngoos-download-manager/main/install.ps1 -o "%TEMP%\HDM-install.ps1" && powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%TEMP%\HDM-install.ps1"
```

The command verifies the published package size and SHA-256 before starting setup.

#### Portable

[Download the Windows portable ZIP](https://github.com/hngoos/hngoos-download-manager/releases/download/v0.1.6/HDM-0.1.6-Windows-x64-Portable.zip)

Extract the entire HDM folder into a writable location, then run HDM.exe.
Settings, history and default downloads stay in Data beside the app. Close HDM
before moving it. For updates, extract the new runtime to a fresh folder and move
your existing Data folder into it; keep your Data folder.

Portable mode does not automatically register startup or browser native messaging.
Opening a browser setup guide explicitly registers that copy as the browser's
native host. Repeat setup after moving it; a browser uses one registered HDM copy
at a time. Saved website sessions may need authentication again on another PC.


#### Installation

1. Run the installer and complete setup. Installation is per user.
2. Open **HDM** from the Start menu.
3. Paste a URL, review the filename, and click **Download** or press **Enter**.

Click the HDM logo to change the download folder in Preferences.

### macOS

**Downloads are temporarily unavailable.**

The current release is available for Windows only. macOS packages will return
when platform testing is complete; v0.1.6 does not contain a macOS installer.

### Browser extension

Click the HDM logo to open Preferences, then select your installed browser.
Follow the four-step guide inside the app to load the included `extension`
folder. HDM connects automatically; no extra connection button or separate
extension download is needed. Use the extension popup to turn download capture
on or off, download the current page/video, or show the video download button.

Supported browsers: Chrome, Edge, Brave, Cốc Cốc, Opera, Opera GX, and Vivaldi.
The extension currently requires manual installation through Developer mode.

## What is new in v0.1.6

- Windows x64 portable ZIP with configuration, history and default downloads in
  a local Data folder. Moving the closed app preserves owned paths, paused media
  transfers, torrent history and saved file selections.
- Portable update checks download a verified ZIP instead of running the installer.
- Fewer redundant durable checkpoint writes at HTTP range completion.
- Fix audio export failures caused by long temporary filenames on Windows.
- macOS downloads are temporarily unavailable while platform validation is pending.

## Repository scope

This repository distributes the current HDM releases for Windows and macOS.
Download current installers from [Releases](https://github.com/hngoos/hngoos-download-manager/releases).

The application and extension source files visible here are a historical v0.1.4
snapshot. They do not reproduce the current release binaries. Current development,
platform builds and application tests are maintained in a private repository.
Public Actions validate distribution metadata and verify the publisher signature,
size and SHA-256 of released packages. Historical-source build workflows are
manual only and do not validate the current private source.

## Contact

<p align="left">
  <a href="https://www.facebook.com/hngoos"><img src="docs/assets/contact-facebook.svg" width="40" height="40" alt="Facebook"></a>
  <a href="https://www.instagram.com/hngoos/"><img src="docs/assets/contact-instagram.svg" width="40" height="40" alt="Instagram"></a>
  <a href="mailto:1hngoos@gmail.com"><img src="docs/assets/contact-gmail.svg" width="40" height="40" alt="Email 1hngoos@gmail.com"></a>
  <a href="https://github.com/hngoos"><img src="docs/assets/contact-github.svg" width="40" height="40" alt="GitHub hngoos"></a>
</p>

[Report a bug](https://github.com/hngoos/hngoos-download-manager/issues/new?labels=bug) · [License](LICENSE)
