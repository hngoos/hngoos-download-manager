# Development guide

HDM targets Windows 10/11, 64-bit. Development requires Python 3.11+ with
Tkinter and Node.js 22+. Core portable tests also run on Linux. Source access
is governed by LICENSE; public visibility does not grant an open-source license.

## Set up

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[media,processing,excel,pdf,web,tray,torrent,updates,dev,build]"
npm ci --prefix browser-extension --ignore-scripts
.\.venv\Scripts\python.exe scripts/fetch-archive-tools.py
.\.venv\Scripts\python.exe -m hngoos_dm
```

Optional feature dependencies are declared in `pyproject.toml`. The HTTP core
can run without the media, PDF, browser capture, or torrent extras.

## Check changes

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
node --test browser-extension/test/*.test.js
.\.venv\Scripts\python.exe -m hngoos_dm --smoke-test
```

HTTP tests use local fixture servers and synthetic data. Add meaningful
regression coverage for changes to data integrity, concurrency, and security.
Review interface changes at the default and minimum window sizes.

### Browser integration

```powershell
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --onefile --console --name HDMBridge --paths src src/hngoos_dm/bridge_launcher.py
$env:HNGOOS_BROWSER_TESTS = '1'
$env:HNGOOS_BRIDGE_EXE = (Resolve-Path dist/HDMBridge.exe).Path
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_browser_integration.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_invoices.py -v
```

Browser tests use temporary profiles. The Windows native-host test temporarily
registers a Chromium host under the current account and restores the previous
setting. Do not run two copies of that test concurrently.

## Build

```powershell
.\scripts\build.ps1
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" scripts/installer.iss
```

The build uses a separate `.venv-build` environment. Outputs are written to
`build/` and `dist/`; the extension ZIP includes runtime files only. Check the
EXE with `--smoke-test` and `--self-test-report <report.json>` before release.
See MAINTAINER.md for signing and publishing.

## Submit a change

Keep each change focused, describe the resulting behavior, and include the
checks you ran. Update documentation when permissions, data handling, or
supported workflows change. Report vulnerabilities privately using SECURITY.md.

Do not commit credentials, cookie files, signing keys, private URLs, personal
files, download databases, local backups, dependency directories, or binaries.
Keep dependency notices and license obligations with redistributed components.
