# Platforms and installation

## Windows

The stable desktop installer supports Windows 10/11 x64. Run the EXE or use
the command in the README. `install.ps1` downloads version 0.1.0, checks its
published size and pinned SHA-256, and runs the per-user installer silently.
Administrator privileges are not required.

PowerShell options:

```powershell
.\install.ps1 -Interactive
.\install.ps1 -DownloadOnly
```

If Scoop is already installed, the repository provides a directly installable
manifest; HDM has not been submitted to the community bucket or WinGet catalog:

```powershell
scoop install https://raw.githubusercontent.com/hngoos/hngoos-download-manager/main/scoop/hdm.json
```

Native messaging registration still requires the extension's actual ID in HDM's
Browser tab.

## macOS and Linux preview

The same desktop application can be installed from source in an isolated,
per-user Python environment. Python 3.11 or newer, Tkinter, and venv must be
available. These previews do not yet have signed macOS installers or native
Linux distribution packages.

```sh
curl -fsSL https://raw.githubusercontent.com/hngoos/hngoos-download-manager/main/install.sh -o /tmp/hdm-install.sh
sh /tmp/hdm-install.sh
```

Open **HDM** from your applications menu. The command is also available at
`~/.local/bin/hdm`; add `~/.local/bin` to PATH if necessary. Run the installer
again to update the preview to the current main branch. This preview source
installation does not use the signed Windows binary update channel.

Linux requirements on Ubuntu/Debian:

```sh
sudo apt-get install python3 python3-venv python3-tk
```

For macOS, install a Python distribution with matching Tkinter support. For
example, when Homebrew is already configured:

```sh
brew install python@3.13 python-tk@3.13
HDM_PYTHON="$(brew --prefix python@3.13)/bin/python3.13" sh /tmp/hdm-install.sh
```

The installer accepts an optional local checkout path for development:

```sh
sh install.sh /absolute/path/to/hngoos-download-manager
```

`HDM_INSTALL_DIR` selects an absolute runtime directory. The installer creates
managed launchers and a Linux desktop entry or macOS application launcher.
Download data is separate from the runtime:

| System | New download history and staging |
| --- | --- |
| Windows | `%LOCALAPPDATA%\HDM` |
| macOS | `~/Library/Application Support/HDM` |
| Linux | `$XDG_DATA_HOME/hdm`, defaulting to `~/.local/share/hdm` |

Existing databases in the legacy location are retained. `HDM_DATA_DIR` can
override the metadata directory.

### Features and platform differences

| Capability | Windows | macOS / Linux preview |
| --- | --- | --- |
| HTTP download, pause/resume, mirrors and batch imports | Available | Available |
| Local video/audio tools, spreadsheets and PDF redaction | Included in installer | Included by install.sh |
| Chromium native messaging | Available | User-level manifests for Chrome, Edge, Brave and Chromium |
| Browser session cookie transfer | DPAPI encryption | Unavailable; manually selected cookie files remain supported |
| Defender / Authenticode / shutdown countdown | Available | Unavailable |
| In-app signed binary installer update | Windows installer | Rerun install.sh |
| Torrent, tray and website capture | Included | Optional Python dependencies and system runtimes |

To enable optional preview features, install the corresponding extras into
the runtime environment. For example:

```sh
"$HOME/.local/share/hdm/runtime/bin/python" -m pip install 'hngoos-download-manager[torrent,tray,web] @ https://github.com/hngoos/hngoos-download-manager/archive/refs/heads/main.zip'
"$HOME/.local/share/hdm/runtime/bin/python" -m playwright install chromium
```

On macOS replace the runtime path with
`$HOME/Library/Application Support/HDM/runtime/bin/python`. Dependency availability
depends on the Python version, OS version and architecture. Linux tray support
also depends on the desktop environment. RAR/7z inspection needs `7z` or `7zz`
on PATH; an unavailable inspection tool is reported instead of treating content
as safe.

### Native preview builds

The **macOS and Linux desktop preview** workflow builds on macOS 15 (arm64)
and Ubuntu 22.04 (x64), tests the source installer, runs unit tests and opens
the packaged UI in a smoke test. Successful runs provide downloadable ZIP
and tar.gz artifacts in GitHub Actions. These are unsigned development builds,
expire according to the artifact retention policy, and may require GitHub sign-in.

- macOS: extract the ZIP and open `HDM.app`. Keep `HDMBridge` beside the app
  for browser registration. Use source installation if you prefer to avoid an
  unsigned preview bundle.
- Linux: extract the tar.gz and run `HDM/HDM`. Keep its `_internal` directory
  and `HDMBridge` alongside the executable.

## Browser extension

The Chromium Manifest V3 extension connects a desktop browser to the installed
HDM application; it does not run the desktop download engine inside a browser.
Chrome Web Store publication is pending. The README will link to the approved
listing when available. A standalone browser application is not released.

## Mobile

**Coming soon.** Android and iOS applications are planned for later development.
There is no APK, IPA or mobile web application to install yet.
