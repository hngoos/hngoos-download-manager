# Changelog

## 0.1.12 — 2026-11-06

- Include the rounded toolbar, Info menu, category filters and live speed/bandwidth controls.
- Classify active media by selected output and completed media by its actual file type, including audio-only sources.

## 0.1.11 — 2026-11-06

- Include the rounded category toolbar, icon-only Info and live transfer meter from 0.1.10.
- Keep active media in Music or Video even when its extractor reports a title without a file extension.

## 0.1.10 — 2026-11-06

- Filter downloads by All, File, App, Video, Music, Image, Archive or Other without changing history.
- Use an icon-only Info control; Appearance and Language are inside its menu.
- Display live download/upload rates and select HIGH, MEDIUM or LOW bandwidth at the bottom left.
- Use locally bundled Morphicons assets and consistent rounded panels, buttons and text fields in both themes.
- Preserve native text editing, keyboard shortcuts, inline download details and per-file safety checks.

## 0.1.9 — 2026-11-06

- Include the single-bar Enter workflow, inline details and per-file Check Safety from 0.1.8.
- Verify interrupted parallel downloads independently of worker scheduling order on macOS.

## 0.1.8 — 2026-11-06

- Use a single URL bar: press Enter to reveal link, filename, destination and source-specific advanced options inline.
- Read filenames from server headers and media titles when available, without starting a download.
- Add Check Safety beside each completed file: local checks, Windows Defender and optional VirusTotal multi-engine results.
- Require explicit consent for new VirusTotal file submissions; keep API keys in session memory and show unknown/pending/error states.
- Preserve the Info menu, Chromium extension setup and Windows update runtime fix.

## 0.1.7 — 2026-11-06

- Simplify the main window to a URL bar and rounded download queue, with speed and bandwidth controls below.
- Recognize the source before showing file or media-specific confirmation options.
- Move language, preferences, import/export, browser setup, support and update actions into the Info menu.
- Download the Chromium extension inside HDM and verify its publisher signature, size and SHA-256.
- Present only Windows, macOS, Linux and Mobile in the README download section.
- Include the Windows update runtime fix from 0.1.6.

## 0.1.6 — 2026-11-06

- Fix the missing Python DLL error after an in-app Windows update by launching the installer with an independent runtime environment.
- Make setup reset inherited PyInstaller state before opening HDM, including updates started from older versions.
- Verify the old failure and both repaired handoff paths using real onefile executables and an isolated Inno Setup harness.

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
