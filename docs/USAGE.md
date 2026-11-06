# User guide

[Home](../README.md) · [Features](FEATURES.md) · [Privacy](PRIVACY.md)

HDM focuses on one **Download** screen: a URL bar above your download list.
Use the circular **Info → Appearance** menu for light/dark mode. **Info → Language** selects VI/EN;
both choices are saved. Filter the list using **All · File · App · Video · Music · Image · Archive · Other**.
The bottom-left meter shows live download/upload rates; click **HIGH / MEDIUM / LOW** to change
the shared HTTP bandwidth limit. **Info** also contains preferences, import/export,
browser integration, support, updates and About.

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
2. Press **Enter** in the URL bar. Source details appear directly underneath:
   file link, filename and destination. The server's filename or media title is
   used when available; you can edit it.
3. Choose a folder and optionally a filename. **32** connections is the default.
   Supported media offers **MP4**, **MP3** or **M4A**; video also offers resolution,
   playlist and subtitle options. Direct files have no media options.
4. Open **Advanced options** for connection count, checksums/mirrors or media
   format, quality, subtitles and cookies, depending on the source.
5. Click **Download** beneath the details to start. **Cancel** dismisses the
   details without creating a task. Clipboard recognition never makes a request.
6. Select a row to pause/resume or open its destination folder. The list shows
   progress, speed, live/requested HTTP connections and safety-check status.

**Advanced options** contains expected checksums, verified mirrors, exported
cookies and a media Format ID field, depending on the source. Leaving Format ID empty lets HDM select
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
- **Scheduling and browser partials:** open **Info → Preferences → Tools**.
- **Lists and reports:** open **Info → Import / Export**.

## Safety

HTTP files and every published media output receive local content/name checks.
Executable content, disguised files, macro documents, archive risks and checksum
mismatches are quarantined with `.chuakiemtra` rather than exposed with a runnable name.

Windows Defender scanning is enabled by default on Windows. **Safety** reports
whether its scan completed, was unavailable, or required review. Preliminary
checks do not certify a file as malware-free. Files are never uploaded automatically to a reputation service. Optional hash
lookups and VirusTotal submissions are separate actions.
Defender's own cloud/sample settings are controlled by Windows.

Open **Info → Preferences → Safety** to inspect a local file, configure Defender/high-security
mode or view quarantine logs. Restoring a quarantined download requires the
risk acknowledgement. For a playlist with multiple quarantined files, inspect
the individual files in the destination folder.

## Check Safety after download

Each completed or quarantined file has a **Check Safety** button on its row.
Click it to compute a fresh SHA-256, run local content/name/archive checks and,
on Windows, request a Defender scan. Missing antivirus, errors and pending scans
are shown explicitly. The scan does not execute the downloaded file.

For multi-engine checks, enter your personal VirusTotal API key in the masked
field and select **Check with VirusTotal**. The key stays in memory for this app
session and is not included in history or exports. You can obtain it from your
[VirusTotal account](https://www.virustotal.com/gui/my-apikey).

The first request sends only SHA-256. Existing reports show detection counts,
engine names, findings and the report date. If no report exists, select
**Submit file for a new scan** and explicitly confirm sending the entire file.
VirusTotal may share submitted samples with security partners; do not submit
confidential documents. Files up to 650 MB are supported, subject to your account's
access and quota. Use **Get scan results** if an analysis is still queued.

Neither an unknown file, a pending scan nor zero detections guarantees safety.
No live VirusTotal scan is available without your own API key. **Open VirusTotal**
provides a browser fallback; it never selects or uploads a file automatically.

## Start with your operating system

Enable **Info → Preferences → General → Start HDM at sign-in**. This is optional and affects
only your account. Disable it in the same settings. Tray-on-close and HTTP
shutdown-after-completion options are under **Info → Preferences → Tools**.

## Browser extension

The optional extension supports Chromium browsers. Open **Info → Browser extension**
in the installed HDM app, download its ZIP, extract it to a permanent folder and open
`chrome://extensions` (or your browser's equivalent).

1. Enable **Developer mode → Load unpacked** and select the folder with `manifest.json`.
2. Copy its Extension ID into **HDM → Info → Browser extension**, then register the connection.
3. Check the connection from the extension's options. If asked, select the installed `HDMBridge.exe`.

Use the context menu, popup or video button to send a URL. Optional download
handoff requires the separate downloads permission; unsupported requests remain
in the browser. Session transfer is explicit and encrypted with Windows DPAPI;
on macOS/Linux, choose an exported cookie file under Advanced options instead.
Keep cookie files private. See [Privacy](PRIVACY.md) for storage and cleanup details.
