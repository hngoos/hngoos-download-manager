# Development Guide

Help improve HDM by reporting bugs, suggesting features, improving documentation,
or submitting focused changes. This guide covers the desktop app, browser
extension and development tools.

[Report a bug](https://github.com/hngoos/hngoos-download-manager/issues/new?template=bug_report.yml) · [Suggest a feature](https://github.com/hngoos/hngoos-download-manager/issues/new?template=feature_request.yml) · [Report a vulnerability](../SECURITY.md)

## Before you start

- Search existing issues and pull requests to avoid duplicate work.
- For a substantial code contribution, discuss the proposed change in an issue
  before starting. Small fixes can go directly to a pull request.
- Read the [license](../LICENSE). HDM is proprietary software with publicly
  inspectable source. This guide does not grant additional rights to modify,
  redistribute or relicense the software.
- Report security vulnerabilities privately using the [security policy](../SECURITY.md).

## Prerequisites

| Tool | Requirement |
| --- | --- |
| Git | To clone the repository and manage changes |
| Python | 3.11 or later, with Tkinter and virtual-environment support |
| Node.js | 22 or later, with npm |
| Chromium browser | For manual extension testing |

Windows is the primary release platform. macOS and Linux editions are previews;
see [platform support](../docs/PLATFORMS.md) for available features and dependencies.

## Get the source

```sh
git clone https://github.com/hngoos/hngoos-download-manager.git
cd hngoos-download-manager
git switch -c fix/describe-your-change
```

## Set up your environment

Run commands from the repository root. Use an isolated virtual environment
so development dependencies do not change your system Python installation.

<details open>
<summary><strong>Windows / PowerShell</strong></summary>

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[media,processing,excel,pdf,web,tray,torrent,updates,dev,build]"
npm ci --prefix browser-extension --ignore-scripts
.\.venv\Scripts\python.exe scripts/fetch-archive-tools.py
.\.venv\Scripts\python.exe -m hngoos_dm
```

The archive-tool script downloads and verifies the Windows tools used for
RAR/7z inspection. Windows installer builds also require Inno Setup 6.

</details>

<details>
<summary><strong>macOS / Linux</strong></summary>

Install Python with Tkinter and venv support for your platform. See
[platform prerequisites](../docs/PLATFORMS.md#optional-installation-from-source).

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[media,processing,excel,pdf,web,tray,torrent,updates,dev,build]"
npm ci --prefix browser-extension --ignore-scripts
.venv/bin/python -m hngoos_dm
```

Optional native dependencies depend on the operating system and architecture.
RAR/7z inspection requires `7z` or `7zz` on PATH. Browser-session transfer using
Windows DPAPI is unavailable on these platforms.

</details>

Optional extras are declared in [pyproject.toml](../pyproject.toml). For work on the
HTTP core, `pip install -e ".[dev]"` is enough; install the extras needed by the
features you are changing.

## Find your way around

| Path | Contents |
| --- | --- |
| [`src/hngoos_dm/`](../src/hngoos_dm) | Desktop app, download engine and native messaging bridge |
| [`browser-extension/`](../browser-extension) | Chromium extension and JavaScript tests |
| [`tests/`](../tests) | Python unit and integration tests |
| [`scripts/`](../scripts) | Build, package and release tools |
| [`docs/`](../docs) | User guides, platform support and technical references |
| [`.github/`](../.github) | CI workflows and contribution templates |

## Check your changes

With the Windows environment above:

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
npm test --prefix browser-extension
.\.venv\Scripts\python.exe -m hngoos_dm --smoke-test
```

On macOS/Linux, replace `.\.venv\Scripts\python.exe` with `.venv/bin/python`.
The UI smoke test needs a graphical desktop, or a virtual display on Linux.
Tests that require optional dependencies or browser integration may be skipped
unless those dependencies are installed and the relevant test mode is enabled.

Use local fixtures and synthetic data. Add regression coverage for changes to
data integrity, concurrency and security. Review UI changes at the default and
minimum window sizes. Documentation-only changes need a formatting and link
check rather than a full application build.

### Browser extension

Load `browser-extension/` through **Developer mode → Load unpacked** in your
Chromium browser. Register its extension ID in HDM's **Browser** tab, then use
**Test connection** in the extension options. Keep the extension folder in a
stable location. The packaged user ZIP contains runtime files only.

For Windows integration tests with a real browser and native bridge:

```powershell
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --onefile --console --name HDMBridge --paths src src/hngoos_dm/bridge_launcher.py
$env:HNGOOS_BROWSER_TESTS = '1'
$env:HNGOOS_BRIDGE_EXE = (Resolve-Path dist/HDMBridge.exe).Path
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_browser_integration.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_invoices.py -v
```

These tests use temporary browser profiles. The Windows native-host test
temporarily registers a Chromium host for the current account and restores the
previous setting. Run one copy at a time.

## Build a package

<details>
<summary><strong>Windows installer and extension ZIP</strong></summary>

```powershell
.\scripts\build.ps1
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" scripts/installer.iss
```

The build uses a separate `.venv-build` environment. Outputs go to `build/`
and `dist/`. Check the packaged EXE with `--smoke-test` and
`--self-test-report <report.json>` before release.

</details>

<details>
<summary><strong>macOS / Linux packages</strong></summary>

Build on the target operating system with the optional build dependencies
installed:

```sh
.venv/bin/python scripts/build-desktop.py
```

The workflow builds macOS DMGs and Linux DEB/AppImage packages, then checks the
packaged UI and native messaging bridge. See [platform support](../docs/PLATFORMS.md)
for the tested operating systems and packaging requirements.

</details>

Publisher signing and release publication are covered by the
[maintainer guide](MAINTAINER.md). Never include signing keys in a contribution.

## Submit a pull request

1. Keep the change focused and use a descriptive commit message.
2. Push your branch to a repository where you have permission, then open a
   pull request targeting HDM's `main` branch.
3. Explain the problem and resulting behavior. Include the checks you ran and
   screenshots for UI changes.
4. Update documentation when permissions, data handling, dependencies or
   supported workflows change. Address review feedback and check CI results.

Do not commit credentials, cookie files, private URLs, personal files, download
history databases, signing keys, local backups, dependency directories or built
binaries. Preserve the notices and license obligations of bundled components.

For non-sensitive project questions, use
[GitHub Issues](https://github.com/hngoos/hngoos-download-manager/issues) or email
[1hngoos@gmail.com](mailto:1hngoos@gmail.com). Keep reports specific and discussions
respectful.
