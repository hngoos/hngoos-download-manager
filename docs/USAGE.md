# User guide

[Home](../README.md) · [Features](FEATURES.md) · [Privacy](PRIVACY.md)

## Install

Download the Windows EXE or the macOS DMG for your processor from [Download](../README.md#download).
Windows setup installs HDM for your account at `%LOCALAPPDATA%\Programs\HDM`.
On macOS, drag HDM to Applications. Python and Node.js are not required for these packages.

## Download

1. Paste a link into **URL**. HDM does not read the clipboard automatically.
2. Choose the destination with the folder icon beside **Save as**.
3. For supported video, audio or images, the options card shows choices available for that source.
   Edit the base filename if needed; change the format through its format choices.
4. Click **Download** or press **Enter** in the URL field. **Cancel** clears the current input.
5. Follow progress and speed in the journal. **Stop** interrupts an active transfer.

HTTP transfers use up to 32 connections with no app-imposed speed limit by default.
Actual concurrency and speed depend on range support, server restrictions, your network and disk.
Media formats and quality depend on the source. MP3 conversion does not improve the source recording.
DRM-protected sources, including protected Spotify tracks, cannot be downloaded as MP3.

## Download journal

Completed transfers show **Done**. If a downloaded file is deleted outside HDM, its journal entry
remains and shows **File deleted**. Click the filename to open its containing folder.
**Remove** removes the journal entry without deleting the downloaded file.

On Windows, **Check** scans a completed file with Windows Defender and displays the result in the same row.
A transfer may be complete while its automatic scan is still running. If scanning fails or is unavailable,
HDM reports that condition rather than claiming the file is safe. macOS does not have Windows Defender.

## Preferences

Click the HDM logo to open Preferences; click it again to return to downloads.
Appearance and language take effect immediately. Download and system preferences include
retry behavior, browser capture, local safety checks, the save folder, startup and update settings.
Network defaults to **No proxy**; manual proxy fields appear only when selected.

Use **Report** to open the GitHub bug-report page. **Check for update** opens an in-app card.
Update downloads are verified against publisher-signed metadata, package size and SHA-256 before installation.

## Browser integration

1. In Preferences, select an installed browser. Uninstalled browser logos are dimmed.
2. Open the extensions-page link in step 1 of the guide, then enable Developer mode.
3. Extract the included `HDM-Browser-Extension.zip` to a permanent folder; the guide shows its location.
4. Choose **Load unpacked** in the browser and select the folder containing `manifest.json`.
5. Click **Connect HDM** in the guide and select the same extracted folder.
6. In the extension settings, enable download capture and accept the browser permission prompt.

The extension ZIP is beside the installed Windows executable; on macOS it is included in the
DMG and inside `HDM.app/Contents/Resources`. Keep the extracted folder after installation.
Browser takeover requires the extension to be installed, connected and enabled.

## Safety and privacy

HDM performs local content/name checks and may quarantine risky files with `.chuakiemtra`.
Safety results describe the checks performed; they cannot certify a file as malware-free.
The current safety action uses Windows Defender and does not upload files to VirusTotal.
See [Privacy](PRIVACY.md) and [platform support](PLATFORMS.md) for details.
