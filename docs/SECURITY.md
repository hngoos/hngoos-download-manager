# Security

## Report a vulnerability

Send security reports to [1hngoos@gmail.com](mailto:1hngoos@gmail.com) or use
[GitHub private vulnerability reporting](https://github.com/hngoos/hngoos-download-manager/security/advisories/new).
Include the affected version, reproduction steps, and a minimal example without
personal data. Keep exploit details, credentials, and private URLs out of public
issues. Ordinary bugs belong in the
[issue tracker](https://github.com/hngoos/hngoos-download-manager/issues/new?labels=bug).

## Protection boundaries

| Component | Safeguards | Limits |
| --- | --- | --- |
| HTTP downloads | Default TLS verification; range, ETag, length, and optional expected-checksum checks. | Plain HTTP is unencrypted; a computed hash alone does not establish trust. |
| Partial data | Strong validators for reuse on the same URL; fresh ranges after URL changes. | Servers without suitable validators may require a complete restart. |
| Mirrors | Independently supplied SHA-256 and verified final content. | ETags from different resources do not prove identical bytes. |
| File inspection | Filename, executable, macro, archive-path, and resource-limit checks. | Local inspection is not a complete malware-analysis engine. |
| Windows Defender | Local scans of completed files; separate transfer and scan state. | Defender must be available and enabled; it is not available on macOS. |
| Native messaging | Allowed browser origins, bounded messages, validated actions and URLs, no accepted shell commands. | A compromised local account remains outside this boundary. |
| Browser sessions | Explicit permission, same-origin checks, Windows DPAPI for queued session data. | Processes under the same account may decrypt it; automatic transfer is unavailable on macOS. |
| Updates | Pinned Ed25519 public key, manifest signature, package size, and SHA-256 verification. | Update signatures do not provide OS code-signing certificates or reputation. |

HDM runs with the permissions of the current user. It accepts user-selected
URLs, including local-network sources, and does not automatically execute
downloaded files. Network and media subprocesses use argument lists rather
than shell command strings.

Flagged outputs may receive a `.chuakiemtra` suffix. This reduces accidental
opening but does not isolate the file. Windows Mark of the Web is applied
where supported; some filesystems and network volumes cannot retain it.
Archive inspection cannot fully inspect every encrypted or nested format.

The current Windows installer has no Authenticode certificate. macOS packages
use ad-hoc signatures and are not Developer ID signed or notarized by Apple.
Safety results describe performed checks and cannot guarantee harmlessness.

## Local data

History and staging are not fully encrypted. Download URLs may contain access
tokens. Windows session data received from the extension is encrypted with
DPAPI, then decrypted into a temporary file only for the corresponding media
task. Normal cleanup removes it; a forced termination may leave temporary data.
SQLite WAL files and backups may retain earlier records.

Do not attach complete application data directories to public reports. See
[Privacy](PRIVACY.md) for service connections and
[User guide](USAGE.md#application-data) for data locations.

## Automated checks

CI scans Git history for secrets, audits Python and JavaScript dependencies,
and runs CodeQL for both languages. Workflow actions are pinned to commits;
Dependabot tracks updates. Runtime and native-library dependencies require
ongoing maintenance beyond advisory scans.

Tests cover local transfer integrity, interrupted downloads, update tampering,
file handling, browser handoff, and safety failure paths. These checks do not
establish support for every website, archive, account, or hardware configuration.
