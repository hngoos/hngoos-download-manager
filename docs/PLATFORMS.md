# Platforms and installation

## Windows

The stable desktop installer supports Windows 10/11 x64. Run the EXE or use
the command in the README. `install.ps1` downloads version 0.1.2, checks its
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

## macOS

Choose the DMG matching your processor from [Releases](https://github.com/hngoos/hngoos-download-manager/releases/latest):

- `HDM-0.1.2-macOS-arm64.dmg`: Apple Silicon (M-series).
- `HDM-0.1.2-macOS-x64.dmg`: Intel.

Open the image and drag HDM into Applications. Open the copied application,
then register the browser extension from its Browser tab. The native messaging
bridge and runtime are inside the app bundle; keep the bundle intact.

Both macOS editions are previews tested on macOS 15. They have ad-hoc bundle
signatures, but are not signed with Developer ID or notarized by Apple. If
macOS blocks an application you intentionally downloaded, review the application
under System Settings → Privacy & Security before choosing Open Anyway.

## Linux

Linux packages currently support x64 desktops with glibc 2.35 or later.
Python and the application runtime are bundled.

### Ubuntu and Debian

Download `HDM-0.1.2-Linux-x64.deb` from Releases:

```sh
sudo apt install ./HDM-0.1.2-Linux-x64.deb
```

Open HDM from the application menu, or run `hdm`. The package installs into
`/opt/hdm`; remove it using your package manager.

### AppImage

Download `HDM-0.1.2-Linux-x64.AppImage` into a permanent location:

```sh
chmod +x HDM-0.1.2-Linux-x64.AppImage
./HDM-0.1.2-Linux-x64.AppImage
```

If FUSE is unavailable, use the runtime's extraction mode:

```sh
APPIMAGE_EXTRACT_AND_RUN=1 ./HDM-0.1.2-Linux-x64.AppImage
```

The browser's native host launcher points to the original AppImage file rather
than its temporary mount. If you move the AppImage, open HDM again and register
the extension again in the Browser tab.

## Optional installation from source

On macOS/Linux, Python 3.11+, Tkinter and venv are required only for the source
installer, not for the DMG, DEB or AppImage:

```sh
curl -fsSL https://raw.githubusercontent.com/hngoos/hngoos-download-manager/main/install.sh -o /tmp/hdm-install.sh
sh /tmp/hdm-install.sh
```

The installer uses a per-user virtual environment, creates an application
launcher, and installs the `~/.local/bin/hdm` command. Rerun it to update the
source edition. Add `~/.local/bin` to PATH if necessary.

Ubuntu/Debian source requirements:

```sh
sudo apt-get install python3 python3-venv python3-tk
```

For macOS with Homebrew:

```sh
brew install python@3.13 python-tk@3.13
HDM_PYTHON="$(brew --prefix python@3.13)/bin/python3.13" sh /tmp/hdm-install.sh
```

For development, `sh install.sh /absolute/path/to/checkout` installs a local
checkout. `HDM_INSTALL_DIR` can select an absolute runtime directory.

### Download history and staging

| System | Local application data |
| --- | --- |
| Windows | `%LOCALAPPDATA%\HDM` |
| macOS | `~/Library/Application Support/HDM` |
| Linux | `$XDG_DATA_HOME/hdm`, defaulting to `~/.local/share/hdm` |

Existing legacy databases are preserved. `HDM_DATA_DIR` overrides this location.
Removing a native application package does not remove your download history or
files saved elsewhere. Back up history before deleting the data directory.

### Features and platform differences

| Capability | Windows | macOS / Linux preview |
| --- | --- | --- |
| HTTP download, pause/resume, mirrors and batch imports | Available | Available |
| Local video/audio tools, spreadsheets and PDF redaction | Included | Included in native packages |
| Chromium native messaging | Available | User-level manifests for Chrome, Edge, Brave and Chromium |
| Browser session cookie transfer | DPAPI encryption | Unavailable; manually selected cookie files remain supported |
| Defender / Authenticode / shutdown countdown | Available | Unavailable |
| In-app signed binary installer update | Windows installer | Install a newer package from Releases |
| Torrent, tray and website capture | Included | Dependencies bundled in native packages; browser runtime and desktop tray support still required |

For the optional source edition only, install additional extras into its
virtual environment. For example:

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

### Native package verification

The [desktop packaging workflow](https://github.com/hngoos/hngoos-download-manager/actions/workflows/desktop-preview.yml)
builds on macOS 15 ARM64, macOS 15 Intel, and Ubuntu 22.04 x64. It tests source
installation and the packaged UI. Before an artifact is uploaded, the DMG is
mounted or the Linux package is extracted; the installed UI must open and the
native host must answer a framed ping. The AppImage's persistent native
launcher is tested after extraction. Published installers are available in
Releases without a GitHub account.

## Browser extension

1. Download `HDM-Browser-Extension.zip` from Releases and extract it to a
   permanent folder.
2. Open `chrome://extensions`, `edge://extensions`, or `brave://extensions`.
3. Enable **Developer mode**, select **Load unpacked**, and choose the folder
   containing `manifest.json`.
4. Copy the extension ID into HDM's Browser tab and register the connection.
5. Open the extension options and choose **Test connection**.

Install HDM before connecting the extension. Keep the extracted folder; moving
it may change the extension ID. Chrome Web Store publication is pending, so
manual ZIP installation is the current distribution method.

## Mobile

**Coming soon.** Android and iOS applications are planned for later development.
There is no APK, IPA or mobile web application to install yet.
