# Changelog

## 0.1.5 — 2026-11-06

- Focus the main window on downloading, with an icon-only brand and top-right information/settings.
- Recognize clipboard links locally and wait for confirmation; route files, cloud links, video/audio and magnets.
- Default to 32 HTTP connections, show actual connection counts, and retain validated partial chunks on retries.
- Track media downloads in the shared history and check every published media output.
- Add automatic Windows Defender scanning with explicit unavailable/error states and opt-in launch at sign-in.

## 0.1.4 — 2026-11-06

- Improve light-theme text, buttons, selected rows, icons and dialog backgrounds.
- Keep readable colors when switching themes or opening tools after a theme change.

## 0.1.3 — 2026-11-06

- Add persistent light/dark and VI/EN switches at the top right of the desktop app.
- Add a visible in-app update check, cancellable package download, and verified installer handoff.
- Pin Linux packaging tools to fixed upstream releases with verified SHA-256 hashes.
- Simplify release notes and organize each download section into download and installation steps.

## 0.1.2 — 2026-11-06

- Apply the approved monochrome HDM logo to desktop windows, dialogs, the sidebar,
  system tray, Windows installers, macOS/Linux packages and Chromium extension.
- Generate platform icons from one shared SVG source, preserving the supplied H.

## 0.1.1 — 2026-11-06

- Add macOS DMGs for Apple Silicon and Intel, plus Linux x64 DEB and AppImage installers.
- Keep the native browser bridge inside the macOS app bundle and use persistent AppImage host launchers.
- Provide direct extension ZIP downloads with Developer mode / Load unpacked instructions.
- Include command-line installation and clear platform-specific feature availability.
- Inspect disguised Linux/macOS binaries and executable scripts during preliminary file checks.

## [0.1.0]

- Resumable parallel downloads, verified mirrors, expired-link replacement,
  destination changes, adaptive connection limits, scheduling, and bandwidth presets.
- Editable batch imports, bulk filenames, and per-row reports.
- Chromium browser integration, native messaging, optional download handoff,
  session permissions, and HLS/DASH detection.
- Local video/audio downloads, trimming, joining, conversion, and compression.
- File inspection, quarantine, checksums, bounded archive inspection, and PDF redaction.
- Website capture, torrent checkpoints, optional tray operation, and signed update metadata.
- Experimental invoice capture and content filtering.

Current conditions and limits are documented in [FEATURES](docs/FEATURES.md).

[0.1.0]: https://github.com/hngoos/hngoos-download-manager/releases/tag/v0.1.0
