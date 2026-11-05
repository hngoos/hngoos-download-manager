# User guide

[Home](../README.md) · [Feature reference](FEATURES.md) · [Privacy](PRIVACY.md) · [Security](SECURITY.md)

This guide covers **HDM v0.1.1** on Windows 10/11 x64, with macOS and Linux desktop previews. The current application and extension interface is in Vietnamese; menu labels below include the wording you will see on screen.

## Install HDM

For macOS DMGs and Linux DEB/AppImage installation, see [platform installation](PLATFORMS.md). The steps below describe the Windows EXE.

1. Download [HDM-Setup-0.1.1.exe](https://github.com/hngoos/hngoos-download-manager/releases/download/v0.1.1/HDM-Setup-0.1.1.exe).
2. Run the installer. By default it installs for the current account at `%LOCALAPPDATA%\Programs\HDM`.
3. Open **HDM**. The runtime, browser bridge, media dependencies, and component notices are included; Python and Node.js are not required.

The extension is optional and installed separately. The current installer is not Authenticode-signed. Verify its source and checksum rather than disabling Windows protection.

## Verify a package

Compare this command's result with the SHA-256 for the same filename in the [release notes](https://github.com/hngoos/hngoos-download-manager/releases/tag/v0.1.1):

```powershell
Get-FileHash .\HDM-Setup-0.1.1.exe -Algorithm SHA256
```

The in-app updater additionally checks Ed25519-signed metadata against its pinned publisher key before checking the installer bytes. A matching checksum alone is not a publisher signature.

## Download a file

1. Paste an HTTP/HTTPS URL into **Đường dẫn** (URL).
2. Optionally enter a filename, choose **Lưu tại** (Save to), and select the connection count.
3. Select **Thêm lượt tải** (Add download).
4. Use **Tạm dừng / Tiếp tục** (Pause / Resume), or right-click the entry for actions available in its current state.

Expected checksums and mirrors are under **Tùy chọn nâng cao** (Advanced options). The overview shows active jobs, completed files, and combined HTTP speed. Bandwidth presets are **Tối đa** (Maximum), **Vừa** (Moderate, 4 MB/s), and **Nhẹ** (Light, 512 KB/s).

New HTTP jobs download into `%LOCALAPPDATA%\HDM\staging` before delivery. When moving between volumes, HDM copies through a temporary destination file and verifies SHA-256 before the final filename appears. A sync client may see the temporary file. Video tasks also stage locally; torrents use their own task directories.

### Resume, replace a link, or move a download

Resume across application restarts requires the source to retain a matching strong ETag and size. If a link expires, pause the job and use its context-menu replacement action. HDM keeps old chunks only when the new source can be verified as the same content.

Changing the save folder during a download pauses reads, moves partial data, and resumes. Keep both locations accessible until the move finishes.

Mirror downloads require a SHA-256 from an independent, trusted source. If final verification fails, HDM retries mirror-origin chunks from the primary source and preserves chunks already taken from that primary source.

### Adopt a browser partial file

Stop the browser's download first. Open **Công cụ → Tiếp quản tệp trình duyệt tải dở** (Tools → Adopt partial browser download), select the partial file, and provide its direct URL. HDM preserves the original and verifies the complete existing prefix before reuse. The source must support ranges and a strong ETag.

## Import a list

Open **Nhập danh sách…** (Import list). Paste link–filename columns from Excel/Google Sheets, or open CSV, TXT, or XLSX, including cell hyperlinks.

```text
https://example.com/report.pdf | Monthly report.pdf
https://example.com/photo.jpg  | Product photo 001.jpg
```

Select **Xem trước** (Preview), then double-click a row to edit it. Select multiple rows to rename or remove them. Entries without names receive numbered filenames. Keep imports within 500 rows and check the preview before starting.

Start the batch when the names and order are correct. Use the batch-report command in **Công cụ** (Tools) to export per-row status without source URLs or tokens.

Website capture tools can save a list of pages as PDF/PNG with the source and capture time. They use an isolated browser session, not your normal signed-in profile; an installed Edge or configured Playwright Chromium runtime is required.

## Download video or audio

Open **Video & nhạc** (Video & audio), paste the original page URL, inspect formats when needed, select the maximum video height or MP3/M4A, and start the task. Playlist and subtitle options depend on what the website exposes. Use the stop control to cancel.

The height setting is a cap, not a promise of source quality. HDM prefers H.264/MP4 when suitable formats are available. DRM-protected content and access-control bypass are unsupported.

### Use a signed-in session explicitly

Enable **Dùng phiên đăng nhập** (Use signed-in session) in the extension only when needed, and grant cookie access for that website. Cookies are read only when the requested video URL and the source page share an origin. HDM stores the queued session using Windows DPAPI and creates a temporary cookie file for yt-dlp while the task runs.

The temporary cookie file is removed during normal cleanup. Forced termination may leave temporary data; files you export and select yourself remain under your control. See [Privacy](PRIVACY.md#session-cookies-and-invoices).

### Process media locally

Use **Công cụ → Cắt / ghép video, nhạc…** (Tools → Cut / join video and audio), or the appropriate downloaded-file context menu.

- Choose stream-copy cuts for speed or re-encode for frame-accurate cuts.
- Arrange join inputs with Up / Down controls. Video inputs are normalized to the largest source canvas and a common format.
- Convert to MP4, extract MP3/M4A, or compress to a target size.

Compression uses two passes and preserves the source. HDM discards results that are not smaller or exceed the target; try a larger target when the requested size is too low.

## Browser setup

Supported browsers are **Chrome, Cốc Cốc, Edge, Brave, and Opera**, based on Chromium 120 or later. The extension currently installs from ZIP; it is not on the Chrome Web Store.

1. Install the HDM desktop application.
2. Download [HDM-Browser-Extension.zip](https://github.com/hngoos/hngoos-download-manager/releases/latest/download/HDM-Browser-Extension.zip) and extract it to a permanent folder.
3. Open the browser's extensions page, such as `chrome://extensions` or `edge://extensions`.
4. Enable **Developer mode → Load unpacked**. Select the extracted folder containing `manifest.json`. Alternatively, use the installed application's `browser-extension` folder.
5. Copy the **Extension ID**, open **Trình duyệt** (Browser) in HDM, and register the native host for that ID. Registration affects the current Windows account.
6. Open the extension's **Options** page and select **Kiểm tra kết nối** (Check connection).

If prompted to choose the bridge, select the installed `HDMBridge.exe`. Keep the extension folder in place. After an update, reload the extension; check the ID again if you moved the folder or changed browser profiles.

### Send links, videos, and detected streams

Use the context menu or extension popup to send a link/page. The video button appears outside the video frame. Grant access to the relevant site when requested.

For HLS/DASH detection, play the video on an authorized page, then open or reopen the popup and choose a detected stream. An empty list can mean missing website access, no manifest request yet, an excluded advertising pattern, or a source the detector does not support. Try the original page URL in HDM as well.

### Optional download handoff

Enable **Tự chuyển lượt tải HTTP/HTTPS sang HDM** (Automatically send HTTP/HTTPS downloads to HDM) and grant the separate downloads permission.

HDM takes ownership only after the native host verifies the source and saves the request. If acceptance fails, the browser resumes. Requests that depend on cookies, POST, blob URLs, or unverified sources continue in the browser. Save-dialog timing depends on the browser and configuration.

### Optional filtering

Grant network access from the popup to fetch and apply filter lists. Select Off, Minimal safety, Ad blocking, or Strong. Allow a site when filtering interferes; malware rules remain active.

The element picker works when ad blocking is enabled and the page is eligible. Select a nonessential element and confirm; press **Escape** to cancel. Use **Về mặc định cho trang này** (Reset this site) to remove its hidden-element settings and explicit exception. Request statistics may be unavailable when the browser does not permit access.

## Inspect files and redact PDFs

Use **An toàn** (Safety) to inspect a file, compare hashes, request Defender/Authenticode checks, or open a SHA-256 lookup service. Enter an archive password when supported inspection requires it. A reported inspection limit is not a clean result.

Flagged files receive `.chuakiemtra`. Restore only after reviewing the findings and checking the risk acknowledgement. A valid signature or a hash lookup does not guarantee safety.

For PDFs, select the redaction tool under **Công cụ** (Tools), draw over sensitive regions, and export a new file. The output is rasterized and loses searchable text. Open the exported PDF and review every page before sharing it.

## Invoice capture — experimental

On a supported Shopee, Lazada, or TikTok Shop seller hostname, open the popup and enable **Tự lưu phiếu khi in** (Save invoices when printing). The normal print action continues; HDM receives static print HTML and exports it locally.

Files are organized under `%LOCALAPPDATA%\HDM\invoices\<platform>\<date>`, with order IDs in their names. Open them through **Công cụ → Mở thư mục phiếu giao hàng** (Tools → Open invoice folder).

Each capture is limited to 90 KB. The PDF renderer does not execute scripts or load external resources. URL-based images/barcodes, external stylesheets, frames, and print windows on another hostname may be absent. Review the PDF and use the browser's **Save as PDF** when capture is incomplete. Live seller accounts and every invoice format have not been accepted. Inbox HTML is removed after successful PDF creation; interrupted tasks can be retried when HDM reopens.

## Torrents and background work

Open a torrent/magnet task, select the files you want, and start it. HDM saves checkpoints periodically, on pause, and on close. Use **Công cụ → Mở lại torrent đã lưu** (Tools → Reopen saved torrent) to reopen a task in the paused state. Sharing stops when completion is detected.

Tray operation, sleep prevention during active work, and shutdown after HTTP jobs finish are available as options. Shutdown includes a 60-second countdown and cancellation. Scheduled downloads require HDM to remain running.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Native host unavailable | Install HDM, register the exact current extension ID, and select the installed bridge executable. |
| Video not detected | Grant site access, start playback, reopen the popup, or try the original page URL. |
| Resume starts over | The source may lack ranges, a strong ETag, or matching content validators. |
| Target compression size rejected | Increase the target; the original file is preserved. |
| Incomplete invoice PDF | Review resource limitations and use the browser's Save as PDF. |
| A quarantined file cannot open | Review inspection findings before considering restoration; do not remove the suffix just to bypass the check. |

For ordinary bugs, open an [issue](https://github.com/hngoos/hngoos-download-manager/issues) with the HDM version, Windows/browser versions, reproducible steps, and a non-sensitive sample URL or file. Report security vulnerabilities privately using the [security policy](SECURITY.md).
