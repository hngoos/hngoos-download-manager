# Development

Technical reference for building, testing, and maintaining HDM on Windows and
macOS. Source availability does not grant rights beyond the [license](../LICENSE).

## Requirements

- Python 3.11 or later with Tkinter and virtual-environment support.
- Node.js 22 or later with npm for extension tests and icon tooling.
- Inno Setup 6 for Windows installers.
- A graphical desktop for native UI checks.

Install optional dependencies for the features being developed. The complete
environment below includes media, PDF, browser, torrent, and packaging tools.

### Windows

Run from the repository root in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[media,processing,excel,pdf,web,tray,torrent,updates,dev,build]"
npm ci --prefix browser-extension --ignore-scripts
.\.venv\Scripts\python.exe scripts/fetch-archive-tools.py
.\.venv\Scripts\python.exe -m hngoos_dm
```

The archive script downloads and verifies the Windows tools for RAR/7z inspection.

### macOS

Python installations without Tkinter can use Homebrew's matching packages:

```sh
brew install python@3.13 python-tk@3.13
python3.13 -m venv .venv
.venv/bin/python -m pip install -e ".[media,processing,excel,pdf,web,tray,torrent,updates,dev,build]"
npm ci --prefix browser-extension --ignore-scripts
.venv/bin/python -m hngoos_dm
```

RAR/7z inspection requires `7z` or `7zz` on PATH. Windows Defender and DPAPI
are Windows-specific. For source installation through the helper, run
`sh install.sh /absolute/path/to/checkout`; `HDM_PYTHON` selects the interpreter
and `HDM_INSTALL_DIR` selects an absolute runtime directory.

## Repository layout

| Path | Responsibility |
| --- | --- |
| `src/hngoos_dm/` | Native application, transfer engine, file handling, and browser bridge. |
| `browser-extension/` | Chromium extension, dependency lockfile, and JavaScript tests. |
| `tests/` | Python unit tests and integration tests. |
| `scripts/` | Development launcher, asset generation, build, signing, and packaging. |
| `.github/` | CI, dependency maintenance, and issue templates. |
| `docs/` | User, privacy, security, development, and release documentation. |
| `scoop/` | Windows package manifest for the published installer. |

Runtime assets and their editable source artwork are tracked where required
by build tools. Local environments, downloaded dependencies, databases,
caches, reports, and build products are excluded by `.gitignore`.

## Native development session

```powershell
.\.venv\Scripts\python.exe scripts/dev-native.py
```

On macOS, use `.venv/bin/python`. The launcher opens a desktop app with
separate data in `tools/native-live-data`. UI edits refresh automatically;
F5 refreshes manually. Active HTTP transfers retain their manager. Open
dialogs defer refresh; backend changes require restarting the session.

## Architecture

`app.py` owns Tkinter state and routes work through background tasks. Workers
report back through a queue; they do not manipulate Tkinter widgets. `engine.py`
schedules transfers, while `store.py` persists jobs and chunks in SQLite with
WAL and per-operation connections. An OS-held lock prevents two instances
from using the same application database.

The HTTP engine validates byte ranges, lengths, and strong ETags before
reusing partial data for the same URL. A replacement URL invalidates old
ranges. Mirrors require an independently supplied SHA-256. Local staging and
verified delivery keep incomplete outputs separate from completed files.

The extension communicates with the native host over framed stdio messages.
The bridge validates requests and writes a durable inbox consumed by the app;
it does not expose a local HTTP server. Download handoff keeps the browser's
original transfer available when native acceptance fails.

Media extraction uses yt-dlp; processing uses FFmpeg subprocesses. Optional
processing and import libraries remain covered by tests even where the main
download interface does not expose a separate tool. These modules are not
temporary or generated files.

See [Security](SECURITY.md) for trust boundaries and [Privacy](PRIVACY.md) for
stored data, permissions, and external services.

## Validation

```powershell
.\.venv\Scripts\python.exe -m ruff check src tests scripts
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
npm test --prefix browser-extension
.\.venv\Scripts\python.exe -m hngoos_dm --smoke-test
```

Use `.venv/bin/python` on macOS. Tests with platform requirements may be
skipped outside their supported environment. UI checks require a display.
Use synthetic files and local servers for regression tests.

### Browser integration tests

On Windows:

```powershell
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --onefile --console --name HDMBridge --paths src src/hngoos_dm/bridge_launcher.py
$env:HNGOOS_BROWSER_TESTS = '1'
$env:HNGOOS_BRIDGE_EXE = (Resolve-Path dist/HDMBridge.exe).Path
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_browser_integration.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_invoices.py -v
Remove-Item Env:HNGOOS_BROWSER_TESTS
Remove-Item Env:HNGOOS_BRIDGE_EXE
```

These tests use temporary profiles. The Windows native-host test temporarily
registers a host for the current account and restores the previous setting.
Run one copy at a time.

## Build

### Windows installer

```powershell
.\scripts\build.ps1
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" scripts/installer.iss
```

The build uses `.venv-build`. Outputs are written to `build/` and `dist/`.
Validate the packaged EXE using `--smoke-test` and
`--self-test-report <report.json>`.

### macOS packages

Build on the target architecture:

```sh
.venv/bin/python scripts/build-desktop.py
```

The macOS workflow builds Intel and Apple Silicon packages, validates their
UI and native messaging bridge, and uploads DMG artifacts.

### Assets and extension

The approved logo source is `docs/assets/hdm-logo-square.svg`. Regenerate its
desktop and extension assets with `scripts/build-branding.py` after installing
Playwright Chromium. `scripts/build-icons.mjs` generates the Morphicons bundle;
`scripts/package-extension.py` creates the runtime-only extension ZIP.
Preserve the [third-party notices](../THIRD_PARTY_NOTICES.md).

Browser-store distribution requires a publisher account, reviewed privacy
declarations, and an assigned extension ID registered in the native host.
Unpacked profile IDs must not be assumed to match a store ID. The extension
is currently distributed for manual installation.

## Release

1. Update the version and release notes under `docs/releases/`.
2. Run validation, then build and check all Windows and macOS packages.
3. Collect the verified artifacts in `dist/`.
4. Provide `HNGOOS_RELEASE_SIGNING_KEY` only to the signing process and run
   `scripts/sign-release.py`.
5. Review the generated metadata, then run `scripts/publish-release.py --publish`.

Use a new version for binary changes. Publishing an existing version requires
the explicit replacement workflow; ordinary source updates do not replace a
release. Ed25519 update signatures are separate from Windows Authenticode and
Apple Developer ID/notarization.

Do not commit credentials, signing keys, cookies, private URLs, personal files,
download databases, dependency directories, or generated installers.
