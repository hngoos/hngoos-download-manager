# User guide

[Home](../README.md) · [Features](FEATURES.md) · [Privacy](PRIVACY.md)

HDM v0.1.6 focuses on one **Download** screen. Use the top-right switches for
light/dark appearance and VI/EN; both choices are saved. The information button
opens **About**, settings, safety tools and browser integration.

## Install and update

Download the package for your system from [Download](../README.md#download).
On Windows, run the EXE. It installs for your account at
`%LOCALAPPDATA%\Programs\HDM`; Python and Node.js are not required.
See [platform installation](PLATFORMS.md) for macOS and Linux.

Select **Check for update** in HDM. Download and verification happen inside the
app. Pause or finish active tasks before selecting **Install update**, which
opens the local system installer. The updater checks Ed25519-signed metadata,
package size and SHA-256. This does not replace Windows Authenticode or macOS
notarization; current packages do not have those publisher certificates.

## Download

1. Copy a link. HDM detects it locally and fills an empty URL field. If you are
   editing another URL, select **Use new link** to replace it. You can also paste manually.
2. Choose a folder and optionally a filename. **32** HTTP connections is the default.
3. Choose **Auto** to recognize the source, **Original** for a direct file, or
   **MP4**, **MP3** or **M4A** for supported media. Video links reveal resolution,
   playlist and subtitle options. Availability depends on the source.
4. Select **Add download**. Clipboard recognition alone never starts a network request.
5. Select a row to pause/resume or open its destination folder. The list shows
   progress, speed, live/requested HTTP connections and safety-check status.

**Advanced options** contains expected checksums, verified mirrors, exported
cookies and media format inspection. Leaving Format ID empty lets HDM select
and combine suitable video/audio streams; choosing a specific ID selects that stream.
MP3/M4A extraction uses available source audio; converting to 320 kbps cannot
improve the original recording's quality.

HTTP and media downloads share history. One media task runs at a time. Media
resume depends on the extractor and source, and may repeat extraction or
processing. Fragment concurrency is capped at 32 where the source supports it;
progressive media is not guaranteed to use 32 HTTP connections.

Direct file links, supported cloud shares, video pages and magnets use the same
URL field. Torrent links open a file-selection dialog. Unsupported or signed-in
sources may fail with an explanation. DRM-protected music, including Spotify
tracks, cannot be downloaded directly as MP3; HDM does not replace it with another
recording or bypass access controls.

## Recover and organize

- **Pause/resume:** completed and partial HTTP chunks are reused only when a
  strong ETag and source length prove the file has not changed. Unverifiable
  data is downloaded again.
- **Expired links:** pause the HTTP job, then right-click **Replace download link**.
- **Move an active HTTP job:** right-click **Move active download**. Keep both
  destinations accessible until the move finishes.
- **Batch import:** paste link/filename columns or load TXT, CSV or XLSX. Preview
  names and order before starting. Keep each import within 500 rows.
- **Bandwidth:** choose Maximum, Medium or Light. These presets share the HTTP
  bandwidth budget; media and torrent transfers have their own source protocols.
- **Scheduling, browser partials and reports:** open **About → Tools**.

## Safety

HTTP files and every published media output receive local content/name checks.
Executable content, disguised files, macro documents, archive risks and checksum
mismatches are quarantined with `.chuakiemtra` rather than exposed with a runnable name.

Windows Defender scanning is enabled by default on Windows. **Safety** reports
whether its scan completed, was unavailable, or required review. Preliminary
checks do not certify a file as malware-free. No files are uploaded by HDM to a
reputation service; optional hash lookups open the selected service with SHA-256.
Defender's own cloud/sample settings are controlled by Windows.

Open **About → Safety** to inspect a local file, configure Defender/high-security
mode or view quarantine logs. Restoring a quarantined download requires the
risk acknowledgement. For a playlist with multiple quarantined files, inspect
the individual files in the destination folder.

## Start with your operating system

Enable **About → Settings → Start HDM at sign-in**. This is optional and affects
only your account. Disable it in the same settings. Tray-on-close and HTTP
shutdown-after-completion options are under **About → Tools**.

## Browser extension

The optional extension supports Chromium browsers. Download its ZIP from
[Download](../README.md#browser), extract it to a permanent folder and open
`chrome://extensions` (or your browser's equivalent).

1. Enable **Developer mode → Load unpacked** and select the folder with `manifest.json`.
2. Copy its Extension ID into **HDM → About → Browser**, then register the connection.
3. Check the connection from the extension's options. If asked, select the installed `HDMBridge.exe`.

Use the context menu, popup or video button to send a URL. Optional download
handoff requires the separate downloads permission; unsupported requests remain
in the browser. Session transfer is explicit and encrypted with Windows DPAPI;
on macOS/Linux, choose an exported cookie file under Advanced options instead.
Keep cookie files private. See [Privacy](PRIVACY.md) for storage and cleanup details.
