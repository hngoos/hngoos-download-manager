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

The current Windows release is **v0.1.7**.

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

[Download the Windows installer](https://github.com/hngoos/hngoos-download-manager/releases/download/v0.1.7/HDM-Setup-0.1.7.exe)

Or install from Command Prompt (CMD):

```cmd
curl.exe -fL https://raw.githubusercontent.com/hngoos/hngoos-download-manager/main/install.ps1 -o "%TEMP%\HDM-install.ps1" && powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%TEMP%\HDM-install.ps1"
```

The command verifies the published package size and SHA-256 before starting setup.

#### Portable

[Download the Windows portable ZIP](https://github.com/hngoos/hngoos-download-manager/releases/download/v0.1.7/HDM-0.1.7-Windows-x64-Portable.zip)

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
when platform testing is complete; v0.1.7 does not contain a macOS installer.

### Browser extension

Click the HDM logo to open Preferences, then select your installed browser.
Follow the four-step guide inside the app to load the included `extension`
folder. HDM connects automatically; no extra connection button or separate
extension download is needed. Use the extension popup to turn download capture
on or off, download the current page/video, or show the video download button.

Supported browsers: Chrome, Edge, Brave, Cốc Cốc, Opera, Opera GX, and Vivaldi.
The extension currently requires manual installation through Developer mode.

## What is new in v0.1.7

- Capture progressive MP4, M4A and other supported media responses alongside HLS/DASH,
  tied to the active browser document with common ad/tracking/fragment filtering.
- Select individual items from supported collections in a paged window. Each item
  has independent progress and retry; completed items are preserved.
- Warn about duplicate sources with matching output choices. Missing or changed
  completed files can be downloaded again.
- Preserve the browser source origin during direct-file probes, retries and resume.
- Use verified changed-file portable updates where an exact base is available,
  with full ZIP fallback and a standalone worker. Failed startup restores the
  previous runtime without replacing Data.

The v0.1.6 portable updater still uses its existing manual update procedure;
transactional update initiation is included from v0.1.7 onward. Automatic runtime
rollback applies to portable mode. A power loss during a runtime swap may require
`.hdm-update/worker.exe --portable-update-recover <portable-folder>`.

The Windows installer is 54.2 MB, with approximately 161.7 MB after installation.
The portable ZIP is 75.7 MB. Windows packages are not Authenticode-signed; update
metadata is verified with the pinned Ed25519 publisher key.

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
