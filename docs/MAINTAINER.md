# Maintainer guide

The public `hngoos/hngoos-download-manager` repository contains the current
application source, browser extension, tests, documentation, and development
tools. Publish reviewed source snapshots without copying local build data or
private development history. The application license is defined in LICENSE.

## Repository contents

- `src/hngoos_dm`: desktop application and native messaging bridge.
- `browser-extension`: Chromium extension, pinned dependencies, and tests.
- `tests`: local and browser integration tests.
- `scripts`: build, packaging, signing, and release tools.
- `.github`: continuous integration, security checks, and issue templates.
- `docs`: feature details, usage, architecture, privacy, and release notes.

HDM is a desktop application with a native messaging bridge. There is no
separate hosted server or proprietary library service to publish.

## Release process

1. Run the checks in [the Development Guide](DEVELOPMENT.md).
2. Run `scripts/build.ps1` on Windows, then compile `scripts/installer.iss`
   with Inno Setup 6.
3. Check the packaged application using `--smoke-test` and
   `--self-test-report <report.json>`.
4. Provide the release key only to the signing process through
   `HNGOOS_RELEASE_SIGNING_KEY`, then run `scripts/sign-release.py`.
5. Run `scripts/publish-release.py --publish` to publish verified packages.

Release assets include the Windows EXE, macOS arm64/x64 DMGs, and `HDM-Browser-Extension.zip`. The extension ZIP contains runtime
files with `manifest.json` at its root. License notices stay inside the packages.
The signed manifest and SHA-256 table cover every installer and the extension.
Update metadata is embedded in the release body. Automatic source archives
include the source files at the release tag.

Run `scripts/build-desktop.py` on macOS to build native packages. The
desktop workflow verifies the packaged UI and native messaging protocol before
uploading its artifacts. Download successful Windows and native build artifacts
into `dist/`, then sign and publish together. The tag-triggered Release packages
workflow also collects all target builds; publication remains an explicit
maintainer step. Never claim Apple notarization or Windows Authenticode signing
from the Ed25519 update signature or macOS ad-hoc bundle signature.

Use a new version for future binary changes. The existing `--replace` option
is for an explicitly requested refresh: it stages and verifies new assets,
backs up the old release locally, and attempts restoration if promotion fails.

Never commit signing keys, credentials, cookies, private download URLs,
databases, virtual environments, caches, local backups, or generated binaries.
Keep encrypted signing-key backups and development history outside public Git.
