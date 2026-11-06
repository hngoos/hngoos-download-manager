# Feature reference

[Home](../README.md) · [User guide](USAGE.md) · [Privacy](PRIVACY.md) · [Security](SECURITY_MODEL.md)

This reference describes **HDM v0.1.11**. It separates implemented behavior from conditions that depend on servers, websites, accounts, or hardware. The release does not complete every planned capability. The stable binary release targets Windows; the current source also offers [macOS/Linux desktop previews](PLATFORMS.md), with platform-specific features and optional dependencies listed there.

## One download screen

The main window contains a URL bar above the download list, with current speed and bandwidth
presets at the bottom left. Category filters sit beside an icon-only Info button at the top right.
Appearance and Language are inside Info. Filters change the visible list without deleting history.
The Info menu also offers import/export, preferences, browser extension installation, support,
bug reporting, Discord, in-app updates, About and Quit.

Clipboard recognition is local and waits for a click, preserving a URL already being edited.
Press Enter to recognize the source and reveal details beneath the URL bar. Direct files show
filename and destination; Advanced options adds checksums/mirrors or media format, quality,
playlist and subtitles as applicable. Click Download in the details to start. HTML source pages go to
the media extractor after confirmation rather than being saved as a supposed video.
Spotify music is DRM-protected and cannot be downloaded directly as MP3.

Both HTTP and media tasks appear in the same history. Media pause/resume is supported where the
extractor and retained source allow it; one media task runs at a time. Media sources do not report
HTTP worker counts as 32: fragment concurrency is capped at 32 and depends on their protocols.

Launch at sign-in is opt-in on Windows, macOS and Linux and does not require administrator access.

Completed files offer **Check Safety** directly on their row: local checks, Windows Defender,
and optional VirusTotal multi-engine reports with the user's session-only API key. Hash lookups
do not upload contents. A new cloud scan requires a separate upload action and explicit consent.
Unknown, pending, unavailable and failed checks are never reported as clean.

## Downloads and recovery

| Capability | Implemented behavior | Conditions and limits |
| --- | --- | --- |
| Parallel HTTP/HTTPS | 1–32 connections (32 by default), live/peak connection tracking, chunk scheduling, and a two-file queue | Parallel assembly requires byte ranges and a strong ETag. Otherwise HDM uses a single response or restarts safely. |
| Pause and resume | Persisted progress across application restarts | Completed and partial chunks can be reused only with an unchanged strong ETag and length. |
| Expired links | Replace a paused job's URL and retain verified chunks | The new source must match the required content validators and size. |
| Multiple mirrors | Use sources with an independently supplied SHA-256; reject failing or wrong-size mirrors | ETags from different servers are not treated as proof of identical bytes. |
| Mirror recovery | If the final hash fails, retain primary-source chunks and retry mirror-sourced chunks | HDM does not yet identify the individual corrupt chunk within the mirror group. |
| Browser partial files | Verify the entire contiguous prefix before adopting a `.crdownload` or `.part` file; preserve the original | Requires a direct URL, range support, and a strong ETag. Verification uses additional bandwidth. |
| Move destination | Pause at a read boundary, move partial data, and resume | Requires an accessible destination and sufficient free space. |
| Host limits | Reduce connections after 429/503 responses, persist limits, and gradually restore connections after sustained success | This is adaptive throttling, not a guarantee against a website's rate limits. |
| Scheduling and bandwidth | Local-time scheduling; Maximum, Moderate (4 MB/s), and Light (512 KB/s) HTTP presets | HDM must be running. The bandwidth budget is shared across HTTP jobs. |

Before downloading, HDM checks available disk space for chunks and assembly. New HTTP jobs stage locally and deliver the completed file to the destination. A transfer between volumes uses a temporary destination file and checks its SHA-256 before publishing the final name. Sync software may still observe that temporary file.

## Video and audio

- **yt-dlp integration:** maximum video height from 360p to 2160p, available-format inspection, MP3/M4A extraction, playlists, and Vietnamese/English subtitle options.
- **Format preference:** prefer MP4/H.264 when suitable formats exist. A height cap does not create a quality the source does not provide, and HDM does not silently select a format above that cap.
- **Cancellation and staging:** stop a task; keep incomplete media in local staging and deliver finished outputs after successful processing.
- **Detected streams:** collect bounded HLS/DASH candidates by URL or response MIME type on sites with granted access. Some obvious advertising patterns are excluded; identifying every preroll is not supported.
- **Session access:** explicitly enable the browser session option and grant cookie access for the relevant site. Cookies are only read when the video URL and source page have the same origin. Stored session data uses Windows DPAPI; yt-dlp receives a temporary cookie file during the task.
- **Referrer:** browser-originated video requests may send the source website's origin as Referer, without the page path or query string. This may not satisfy sources that require a full page referrer.
- **Downloader updates:** accept an official yt-dlp release only when the GitHub asset provides the required SHA-256 digest.

Website support follows extractor availability and the permissions of the current account. Private Facebook/Instagram content, closed groups, stories, every advertised quality, and broad website coverage have not been accepted against real accounts. TikTok photo slideshows do not yet have a dedicated workflow. DRM and access-control bypass are unsupported.

## Lists and website capture

- Paste link–filename columns or import CSV, TXT, and XLSX, including cell hyperlinks.
- Preview entries, edit rows, rename multiple entries, remove rows, and generate numbered names.
- Add batch identifiers and row numbers to jobs, and export per-row CSV reports without source URLs, tokens, or raw network errors.
- Optionally categorize downloads by file type.
- Capture lists of pages as PDF or PNG, including the source URL and capture time, through an isolated Edge/Chromium session.

The batch dialog is intended for up to 500 rows per import. Website capture needs a compatible installed browser/runtime and does not automatically reuse your normal browser's signed-in profile.

## Retained processing libraries

The following library APIs remain included for development and compatibility. HDM 0.1.11 keeps the
main desktop workflow focused on downloads and no longer exposes the separate conversion, PDF
redaction or website-capture dialogs in its menus.

### Local media processing

| Tool | Behavior |
| --- | --- |
| Convert | MP4 conversion through FFmpeg; try Windows Media Foundation, then fall back to software encoding when unavailable |
| Trim | Stream-copy cuts or re-encoding for frame-accurate cuts |
| Join | Reorder inputs; normalize video to the largest source canvas with even dimensions, 30 fps, and AAC audio |
| Extract audio | MP3 or M4A output |
| Compress | Two-pass encoding with an audio/container allowance; keep the result only when smaller than the source and within the target size |

Originals are preserved and failed outputs are removed. Hardware acceleration depends on the installed GPU and driver; broad hardware acceptance and DVD menu handling remain outside the verified scope.

## File inspection and PDF library

**Preliminary inspection** covers disguised Windows executables, risky or double extensions, bidirectional filename characters, Office macros, risky shortcuts, and suspicious archive paths or entries.

- ZIP inspection includes nested ZIPs, traversal and symlink checks, ambiguous Windows names, and resource budgets. Unreadable encrypted contents are reported as uninspected.
- RAR/7z inspection uses bundled 7-Zip with time and output limits, including supported password-protected contents. Nested RAR/7z files require separate inspection.
- Flagged files receive a `.chuakiemtra` suffix. Restoring them through HDM requires an explicit risk acknowledgement.
- Checksums support MD5, SHA-1, SHA-256, and SHA-512. Hash lookups can open VirusTotal, MetaDefender, or Kaspersky without automatically uploading the file.
- Windows Defender and Authenticode checks are available. High-security mode additionally flags programs without a valid signature; a valid signature is not proof that a file is safe.
- Guidance for selected installer brands links to official sources and compares signer information. This is not comprehensive impersonation detection.
- Folder watching inspects new or modified files after they stabilize. It does not retrospectively scan every old file.
- ZIP extraction validates paths and resource limits, marks extracted files as internet-originated when supported, and can run automatically after an eligible HTTP download.

**PDF redaction** renders a new PDF from blacked-out page images. The exported document does not carry the original text layer, objects, or attachments; searchable text is lost. Review the exported pages before sharing them.

A locally calculated hash does not establish that a file is clean. Quarantine by filename is not isolation, and HDM is not a replacement for antimalware software.

## Chromium browser integration

One Manifest V3 package targets **Chrome, Cốc Cốc, Edge, Brave, and Opera**, based on Chromium 120 or later. It currently installs manually from ZIP; it is not published on the Chrome Web Store.

- Context-menu link/video downloads and a trusted-click video button outside the video frame.
- Native messaging to `HDMBridge.exe`, using a durable local inbox; no local HTTP listener.
- Optional download handoff: pause the browser download, wait for source verification and durable native acceptance, then cancel the original. If handoff fails, resume the browser download.
- Cookies, POST requests, blob URLs, and sources that cannot be verified are not covered by generic download handoff.

Real Chromium tests cover extension loading, native EXE delivery, download handoff and fallback, manifest detection, element selection/reset, and known-ad popup handling. Each vendor's browser version, save-dialog policy, and enterprise settings can affect behavior; a single save prompt is not guaranteed on every configuration.

### Experimental content filtering

Filter sources are EasyList, EasyPrivacy, ABPVN, and uBlock badware, fetched directly from upstream. The 12-hour update schedule requires the browser to be running and optional host access to be granted.

The four modes are Off, Minimal safety, Ad blocking, and Strong. Per-site exceptions retain malware rules. Supported translations include compatible network rules for domains, paths, resource types, and site scopes. Unsupported syntax is skipped rather than guessed; the current budget is 4,500 rules.

Known-domain popup/overlay handling, an explicit element picker, and per-site reset are implemented conservatively. Statistics depend on browser permissions and API availability. This is not a complete ABP/uBlock engine, and it does not block advertising inserted inside YouTube videos. Sensitive-site exclusions reduce interference but cannot guarantee compatibility with every banking or payment page.

## Invoice capture and other utilities

- **Invoices — experimental:** opt in per supported seller hostname. Capture static print HTML up to 90 KB, render without scripts or outgoing page requests, and organize PDFs by platform/date/order ID. Source and time are included. External images, stylesheets, frames, or print windows on another hostname may be missing. Fixture tests passed; real seller accounts and all invoice layouts have not been accepted. Inbox HTML is deleted after successful PDF export.
- **Torrents:** select individual files, exclude risky extensions by default, save checkpoints, reopen paused tasks, and stop sharing when completion is detected. A local-network transfer/restart/hash check is verified; large public torrents have not been accepted. Torrent data does not yet use the completed-output staging workflow used by HTTP and media.
- **Cloud links:** resolve supported public Drive/Dropbox/OneDrive and MediaFire links without bypassing access controls or quotas.
- **Subtitles:** use OpenSubtitles hash lookup with credentials you provide, without relying on filename-only guesses. Live service acceptance with real credentials remains outstanding.
- **Desktop operation:** optional tray minimization, one active instance per database, sleep prevention during work, and optional shutdown after HTTP history completes, with a 60-second cancellable countdown.
- **Appearance:** dark Vietnamese interface, local Morphicons/Lucide assets, and animations that respect Windows reduced-motion settings. Full English UI localization remains incomplete.

## Updates and local data

Use **Check for update** on the Download screen or in About to check and download a new release inside HDM. Updates require an Ed25519-signed manifest, verified against the pinned publisher key, followed by package size and SHA-256 checks. Choose **Install update** to open the verified local package with your operating system; Windows exits HDM for setup, while macOS/Linux use their system installer or AppImage folder. Active transfers must be paused or finished first. This manifest signature is separate from Authenticode; the current Windows installer does not have an Authenticode certificate.

The top-right appearance switch and Info → Language change the theme and VI/EN language immediately. HDM remembers both choices. Tool-specific dialogs and diagnostics may retain their original language.

New installations use `%LOCALAPPDATA%\HDM`; existing installations may retain the legacy `%LOCALAPPDATA%\HngoosDM` location. Download history can contain signed URLs or private tokens. HTTP and media staging can require substantial temporary space. Cookie files are removed on normal task completion; a forced termination may leave temporary data behind.

See the [privacy policy](PRIVACY.md) for data handling and the [user guide](USAGE.md) for operation.
