# Privacy policy

[Home](../README.md) · [User guide](USAGE.md) · [Security](SECURITY_MODEL.md)

Applies to **hngoos-download-manager (HDM) v0.1.7** and its Chromium extension. Last updated: **6 November 2026**.

## Data stored on your device

HDM stores download history, source URLs, filenames, destinations, progress, and settings in the current account's local data directory. Download URLs can contain private access tokens; treat this history as sensitive data. macOS/Linux previews use the platform data locations described in [platform support](PLATFORMS.md).

The extension stores settings, site exceptions, and hidden-element selectors in local browser storage. Detected media URLs are held temporarily per tab, up to 30 candidates. Entries older than 30 minutes are excluded when the list is read; closing the tab or navigating to a new page clears its list.

HDM has no developer-operated history collection or advertising service. The application and extension do not send usage analytics to an HDM server. Download data is not uploaded to this GitHub repository.

## Clipboard and launch at sign-in

Clipboard link detection is enabled by default and can be disabled in **About → Settings**.
HDM reads clipboard text once per second while running and accepts a single HTTP/HTTPS or magnet link.
Recognition stays on your device: no network request or download starts until you click Download.
An existing URL is preserved; a separate action lets you use a newly copied link.
Clipboard text that is not a valid link is not stored in the download database. Recognized links are
kept in memory until confirmed; accepted download URLs are saved as part of local history.

Launch at sign-in is opt-in and affects only your operating-system account. Disable it in the same
settings. HDM uses the Windows current-user Run entry, a macOS LaunchAgent, or a Linux autostart entry.

Automatic Defender scans are enabled by default on Windows. HDM does not upload files to a developer
server; Defender's own cloud protection or sample-submission settings remain under Windows control.

## Connections to other services

| Activity | Data involved |
| --- | --- |
| File and video downloads | Requests go to the websites and content servers you choose. Those servers receive your IP address and necessary protocol information. Browser-originated video requests may include the source website's origin as Referer, without the page path or query. |
| Application and downloader updates | Requests go to GitHub for release information and assets. |
| Optional content filtering | Lists are fetched directly from EasyList, EasyPrivacy, ABPVN, and uBlock badware sources after you grant access. |
| Hash lookups | VirusTotal, MetaDefender, or Kaspersky opens with the file's SHA-256. HDM does not automatically upload the file's contents. |
| Subtitle lookup | Requests go to OpenSubtitles when you use the feature with the credentials you provide. |
| Torrents | Connections go to peers and torrent network services. Peers can see your IP address. |

These services have their own privacy policies. Local media conversion and PDF redaction do not require sending the file to an external conversion service.

## Chromium extension permissions

| Permission | Purpose |
| --- | --- |
| Native messaging | Send requests you choose to the HDM application on the same computer. |
| Context menus, active tab, scripting | Provide download actions, video controls, element selection, and authorized invoice capture. |
| Storage, alarms | Store settings and schedule filter updates. |
| Declarative net request | Apply selected network-blocking rules when filtering is enabled and website access is granted. |
| Web request, web navigation | Recognize HLS/DASH responses on authorized sites, manage per-tab lists, and handle known-domain advertising popups. Media detection does not store request/response headers or page content. |
| Website access — optional | Requested when you enable relevant site integration or global filtering. |
| Cookies — optional | Use the signed-in session for an explicitly selected video, when the setting and relevant site permission are enabled. |
| Downloads — optional | Hand new downloads to HDM and leave them in the browser if acceptance fails. |

## Session cookies and invoices

**Cookies are not read by default.** With explicit session access enabled, cookies are sent only when the video URL and source page share an origin. Queued session data is encrypted using Windows DPAPI. Automatic session transfer is unavailable on macOS/Linux; those platforms reject cookie-bearing native requests rather than persist them as plaintext. During a download, yt-dlp uses a temporary plaintext cookie file; HDM removes it during normal cleanup. Forced termination may leave temporary data. Cookie files you export and select yourself remain under your control.

Invoice capture is enabled separately for each supported seller hostname. A captured invoice can contain customer information. Static HTML is passed to the local application and rendered locally, without an external PDF service. HTML is removed from the inbox after successful export. You control the resulting PDFs and where they are shared.

## Remove data or revoke access

You can revoke permissions in the browser's extension settings, clear extension data, or remove the extension.

To remove application history and staging data, close HDM and remove its data directory at `%LOCALAPPDATA%\HDM` on Windows, `~/Library/Application Support/HDM` on macOS, or `$XDG_DATA_HOME/hdm` (default `~/.local/share/hdm`) on Linux. An upgraded installation may continue to use a legacy data location. Back up data you want to keep first. The macOS/Linux source runtime lives in the data folder's `runtime` subdirectory. Removing application data does not delete downloaded files or exported PDFs saved elsewhere.

## Contact

Contact the maintainer through [hngoos on GitHub](https://github.com/hngoos) or the [HDM issue tracker](https://github.com/hngoos/hngoos-download-manager/issues). Do not post cookies, credentials, customer invoices, access tokens, or private download histories in public issues. Security reports should follow the [vulnerability reporting guide](VULNERABILITY_REPORTING.md).
