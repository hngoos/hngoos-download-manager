# Privacy policy

[Home](../README.md) · [User guide](USAGE.md) · [Security](SECURITY.md)

Applies to **hngoos-download-manager (HDM) v0.1.0** and its Chromium extension. Source changes last updated: **7 November 2026**.

## Accounts and bug reports

HDM opens directly without an HDM account or sign-in. It does not request your email or store
authentication tokens for an HDM account.

Report a bug opens [a new GitHub Issue](https://github.com/hngoos/hngoos-download-manager/issues/new?labels=bug)
in your default browser. GitHub handles sign-in and submission. You choose the report text and
attachments on GitHub; HDM does not automatically send logs, files, screenshots or download history.
Submitted reports are public and associated with your GitHub account.

## Data stored on your device

HDM stores download history, source URLs, filenames, destinations, progress, and settings in the current account's local data directory. Download URLs can contain private access tokens; treat this history as sensitive data. See [application data](USAGE.md#application-data) for Windows and macOS locations.

The extension stores settings, site exceptions, and hidden-element selectors in local browser storage. Detected media URLs are held temporarily per tab, up to 30 candidates. Entries older than 30 minutes are excluded when the list is read; closing the tab or navigating to a new page clears its list.

HDM has no developer-operated history collection or advertising service. The application and extension do not send usage analytics to an HDM server. Download data is not uploaded to this GitHub repository.

## Clipboard and launch at sign-in

The current source does not monitor or automatically read the clipboard. Paste a URL yourself.
Pasted URLs remain in the app until you inspect a source or confirm a download; accepted download
URLs are saved as part of local history.

Launch at sign-in is opt-in and affects only your operating-system account. Disable it in the same
settings. HDM uses the Windows current-user Run entry, or a macOS LaunchAgent.

Automatic Defender scans are enabled by default on Windows. HDM does not upload files to a developer
server; Defender's own cloud protection or sample-submission settings remain under Windows control.

## Connections to other services

| Activity | Data involved |
| --- | --- |
| File and video downloads | Requests go to the websites and content servers you choose. Those servers receive your IP address and necessary protocol information. Browser-originated video requests may include the source website's origin as Referer, without the page path or query. |
| Application and downloader updates | Requests go to GitHub for release information and assets. |
| Optional content filtering | Lists are fetched directly from EasyList, EasyPrivacy, ABPVN, and uBlock badware sources after you grant access. |
| Manual safety checks | Windows Defender scans files locally. HDM does not upload the file to a third-party scanning service. |
| Subtitle lookup | Requests go to OpenSubtitles when you use the feature with the credentials you provide. |
| Torrents | Connections go to peers and torrent network services. Peers can see your IP address. |

These services have their own privacy policies. Local media conversion and PDF redaction do not require sending the file to an external conversion service.

Manual Windows Defender results and check timestamps may be saved in the local download
history. Windows controls Defender cloud protection and sample submission settings.

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

**Cookies are not read by default.** With explicit session access enabled, cookies are sent only when the video URL and source page share an origin. Queued session data is encrypted using Windows DPAPI. Automatic session transfer is unavailable on macOS; it rejects cookie-bearing native requests rather than persist them as plaintext. During a download, yt-dlp uses a temporary plaintext cookie file; HDM removes it during normal cleanup. Forced termination may leave temporary data. Cookie files you export and select yourself remain under your control.

Invoice capture is enabled separately for each supported seller hostname. A captured invoice can contain customer information. Static HTML is passed to the local application and rendered locally, without an external PDF service. HTML is removed from the inbox after successful export. You control the resulting PDFs and where they are shared.

## Remove data or revoke access

You can revoke permissions in the browser's extension settings, clear extension data, or remove the extension.

To remove application history and staging data, close HDM and remove its data directory at `%LOCALAPPDATA%\HDM` on Windows or `~/Library/Application Support/HDM` on macOS. An upgraded installation may continue to use a legacy data location. Back up data you want to keep first. The macOS source runtime lives in the data folder's `runtime` subdirectory. Removing application data does not delete downloaded files or exported PDFs saved elsewhere.

## Contact

Contact [1hngoos@gmail.com](mailto:1hngoos@gmail.com) or use the [HDM issue tracker](https://github.com/hngoos/hngoos-download-manager/issues). Do not post cookies, credentials, customer invoices, access tokens, or private download histories in public issues. Security reports should follow the [security policy](SECURITY.md#report-a-vulnerability).
