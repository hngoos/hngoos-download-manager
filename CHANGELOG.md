# Changelog

## Unreleased

## [0.1.3] — 2026-11-08

- Draw preferences text, icons, choices and checkboxes on one shared background, replacing the scene together after appearance or language changes.
- Retain displayed artwork until its replacement frame is ready and coalesce pending pointer actions to avoid replaying obsolete selections.
- Preserve native text editing, folder selection and page navigation on the shared preferences surface.
- Add regression coverage for rapid language and appearance changes, image lifetime and settings synchronization.
- Keep keyboard navigation compatible with the Tk versions bundled with supported Python releases on Windows and macOS.

## [0.1.2] — 2026-11-07

- Buffer Windows appearance and page transitions until Tk has completed layout and drawing, preventing partially cleared controls and stale backgrounds.
- Keep nested presentation changes in one paint transaction and restore drawing after a failed transition.
- Add native painting regression checks and an opt-in screen capture test.

## [0.1.1] — 2026-11-07

- Avoid blank native surfaces when toggling preferences or switching between light and dark appearance on Windows.
- Remove Windows download history and settings on uninstall so reinstalling starts with an empty journal; keep downloaded files and preserve history during upgrades.
- Prevent standalone media downloads from probing unconfigured JavaScript runtimes through inaccessible Windows PATH junctions.
- Restart partial downloads when their URL changes, preventing mixed bytes from unrelated resources with identical ETags and sizes.
- Preserve available audio when selecting video streams across source containers; reject incompatible WebM audio instead of producing a silent file or a failed merge.
- Keep preference selections and proxy button widths synchronized when switching language or appearance.

## [0.1.0] — 2026-11-07

First public release of the current Hngoos Download Manager application.

- Native Windows and macOS application with rounded light/dark themes and Vietnamese/English interfaces.
- Parallel HTTP downloads with up to 32 connections, adaptive host limits, retries and resumable transfers.
- Video and audio downloads with format and quality choices based on the available source streams.
- Persistent download journal, Stop/Remove actions, progress and speed indicators, and missing-file status.
- Local file inspection and Windows Defender scanning with separate transfer and scan progress.
- Browser download capture through the bundled Chromium extension and in-app installation guide.
- One preferences page for downloads, system, appearance, language, browsers and proxy settings.
- In-app update checks with publisher-signed metadata and SHA-256 verification.

[0.1.3]: https://github.com/hngoos/hngoos-download-manager/releases/tag/v0.1.3
[0.1.2]: https://github.com/hngoos/hngoos-download-manager/releases/tag/v0.1.2
[0.1.1]: https://github.com/hngoos/hngoos-download-manager/releases/tag/v0.1.1
[0.1.0]: https://github.com/hngoos/hngoos-download-manager/releases/tag/v0.1.0
