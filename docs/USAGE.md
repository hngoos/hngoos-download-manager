# User guide

HDM supports Windows and macOS. Download official packages from
[GitHub Releases](https://github.com/hngoos/hngoos-download-manager/releases/latest).

## Installation

| Platform | Requirements | Install |
| --- | --- | --- |
| Windows | Windows 10/11, x64 | Run the EXE and complete setup. |
| macOS | macOS 15 or later, Apple Silicon or Intel | Open the matching DMG and drag HDM to Applications. |

The packages include the application runtime and native messaging bridge.
Python and Node.js are not required to install these packages.

Windows setup installs to `%LOCALAPPDATA%\Programs\HDM` without requiring
administrator access. The current Windows installer has no Authenticode
certificate. macOS packages have ad-hoc signatures and are not notarized;
if macOS blocks a package you chose to download, review it in **System
Settings → Privacy & Security** before choosing **Open Anyway**.

## Download files

1. Paste a link into **URL**. HDM does not read your clipboard automatically.
2. Set the destination in **Save as**, or use its folder icon.
3. For supported media, choose from the formats and quality levels returned
   by the source. The options card stays hidden for ordinary files.
4. Click **Download** or press **Enter**. **Cancel** clears the current input.
5. Follow the transfer in the download journal. **Stop** pauses an active task.

Media filenames can be edited without changing their extension; select a
different output format through the format choices. An unavailable quality
cannot be created from the source. Converting audio to a higher bitrate does
not improve the original recording.

HTTP downloads use up to 32 connections with no application speed limit by
default. Server restrictions, byte-range support, your connection, and disk
performance determine the actual speed. Sources without a strong validator
use a single response or restart safely. Changing a paused download's URL
starts fresh ranges; ETags from different URLs do not prove identical content.

Website support depends on the downloader and access allowed by the source.
Private or restricted content may require permission or may be unavailable.
DRM-protected Spotify tracks cannot be downloaded directly as MP3.

## Download journal

| Item | Behavior |
| --- | --- |
| Filename | Opens the folder containing the downloaded file. |
| Status | Shows progress, **Done**, or **File deleted** if the output was removed elsewhere. |
| Speed | Shows the current transfer rate. |
| Check | Scans a completed file with Windows Defender on Windows. |
| Stop / Remove | Stops an active transfer, or removes an inactive journal entry while keeping its files. |

The journal persists between sessions. Removing a file outside HDM does not
remove its history. Only the journal scrolls; the surrounding interface stays
fixed.

Safety checks run separately from transfer completion. After a scan, the row
shows its result. An unavailable or failed scanner is never reported as safe.
Files flagged by local inspection may receive a `.chuakiemtra` suffix to
reduce accidental opening. HDM does not automatically execute downloads.

Windows Defender is unavailable on macOS. The current Check action does not
upload files to VirusTotal. See the
[security policy](https://github.com/hngoos/hngoos-download-manager/blob/main/docs/SECURITY.md)
for protection limits.

## Preferences

Click the logo to open Preferences; click it again to return to downloads.

- **Appearance and language:** light/dark and Vietnamese/English, applied immediately.
- **Download:** save folder, retries, browser handoff, local checks, and file organization.
- **System:** launch at sign-in, update settings, tray behavior, and supported power options.
- **Browser:** installation guides for detected browsers; unavailable browsers are dimmed.
- **Network:** No proxy by default; an address field appears for manual configuration.
- **Contact:** project information and contact links.

**Report** opens the GitHub issue form in your browser. Reports and attachments
are chosen and submitted on GitHub. HDM does not submit them automatically.

## Browser integration

The Manifest V3 extension supports Chrome, Edge, Brave, Cốc Cốc, Opera,
Opera GX, and Vivaldi on Windows and macOS. Safari is not supported.

1. Open Preferences and select an installed browser.
2. Open the extensions-page link in the guide and enable **Developer mode**.
3. Extract the included `HDM-Browser-Extension.zip` to a permanent folder.
4. Select **Load unpacked** in the browser and choose the folder containing `manifest.json`.
5. Click **Connect HDM** in the guide and select the same folder.
6. Enable download capture in the extension settings and accept the permission prompt.

The ZIP is beside the installed Windows executable. On macOS it is in the
DMG and in `HDM.app/Contents/Resources`. Keep the extracted folder in place.
Manual installation is required once per browser profile until store
distribution is available.

For downloads that stay in the browser, check that the extension is enabled,
connected, and allowed to capture downloads in both HDM and the extension.
Unsupported requests or a failed handoff remain with the browser. Generic
handoff does not cover every POST request, blob URL, or authenticated source.

Optional extension tools include media detection, content filtering, element
selection, and invoice capture. Website access is requested for relevant
features. Browser-session transfer is opt-in and uses Windows DPAPI; macOS
requires manually selected cookie files instead. See the
[privacy policy](https://github.com/hngoos/hngoos-download-manager/blob/main/docs/PRIVACY.md)
for permissions and data handling.

## Updates

Open **Check for update** in Preferences. The card shows the installed version;
press its check icon to request the latest release information. When an update
is available, download it inside HDM and choose Install.

HDM verifies publisher-signed metadata, package size, and SHA-256 before handing
the package to the operating system. Pause or complete active tasks before
installation. Windows closes HDM for setup; macOS installs through the system.
Source commits on `main` are not available through this check until published.

## Application data

| Platform | Default location |
| --- | --- |
| Windows | `%LOCALAPPDATA%\HDM` |
| macOS | `~/Library/Application Support/HDM` |

Existing installations may retain the legacy Windows location
`%LOCALAPPDATA%\HngoosDM`. `HDM_DATA_DIR` overrides the data directory.
History may contain private URLs. Close HDM before backing up or removing its
data. The Windows uninstaller removes HDM's history and settings, including
legacy databases. Installing an update over the existing app preserves them.
Downloaded files and staging files are kept.
