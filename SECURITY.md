# Security policy

## Supported versions

| Version | Policy |
| --- | --- |
| v0.1.1 / `main` | Receives security fixes |
| Earlier releases | Upgrade to the latest release |

## Report a vulnerability privately

Use [Report a vulnerability](https://github.com/hngoos/hngoos-download-manager/security/advisories/new)
to submit a private report. Include the affected version, reproducible steps
using synthetic data, the impact, and any known mitigation. Do not publish
working exploits in public issues.

Do not include passwords, cookies, access tokens, signing keys, download
history databases, or personal files. If a suspicious sample is needed,
describe it first and use a harmless synthetic example. Do not attach live
malware to the repository.

HDM is maintained by an individual. There is no guaranteed response time or
bug bounty program.

## Protection boundaries

| Component | Protection | Limitations |
| --- | --- | --- |
| HTTP/HTTPS | TLS verification by default; range, ETag and size checks before assembling downloads; expected-checksum verification | HTTP is unencrypted. A locally computed checksum does not establish that a file's source is safe. |
| Mirrors | An independently obtained SHA-256 is required; a mismatch triggers a retry from the primary source | ETags are not trusted across different servers. |
| Browser extension | Optional cookie and host permissions; same-origin checks before reading cookies; trusted events required for page buttons | Websites and the extension do not provide a sandbox for the desktop application. |
| Native host | A 128 KiB limit on stdio messages; URL and cookie-domain validation; no shell commands accepted | The browser and operating system enforce allowed origins. This does not protect a compromised local account. |
| Browser sessions | Windows DPAPI encrypts session data stored in the inbox | Processes running under the same Windows account may be able to decrypt it. Extension session transfer is unavailable on macOS/Linux. |
| ZIP inspection | Checks for path traversal, symbolic links, ambiguous Windows names, executables, macros, nested archives and resource limits | This is not a complete malware analysis engine. RAR/7z inspection does not have equivalent coverage. |
| PDF processing | Pixel limits before rendering; redacted output is a new raster PDF | Searchable text is lost. Review the exported pages before sharing them. |
| Application updates | A pinned Ed25519 public key; signature, checksum and size checks before accepting an installer | The Windows installer has no Authenticode signature or established SmartScreen reputation. Downloaded installers are not run automatically. macOS/Linux updates require installing a newer package. |
| Separate extractor updates | Official releases only, with a required GitHub SHA-256 digest | This relies on the upstream publisher and GitHub. |

HDM does not automatically execute downloaded files. Renaming a file to
`.chuakiemtra` reduces accidental opening, but does not sandbox it: manually
renaming it or opening it with another tool can still execute its contents.
Defender scans, Authenticode checks and online hash reputation are supporting
signals, not guarantees that a file is safe.

macOS packages use ad-hoc signatures and are not Developer ID signed or
notarized. Signed update metadata verifies package integrity and publisher-key
continuity; it is separate from operating system publisher certificates.
See [platform support](docs/PLATFORMS.md) for platform-specific limitations.

<a id="du-lieu-cuc-bo"></a>

## Local data

- The application data directory contains `downloads.sqlite3`, settings,
  events, the browser inbox and temporary files. History can include URLs
  containing access tokens. The database and staging files are not fully
  encrypted. See [data locations](docs/PLATFORMS.md#download-history-and-staging)
  for Windows, macOS and Linux paths.
- New partial HTTP downloads are stored in `staging/<job-id>`. Blocks are
  reused only when the required verification conditions are met. An upgraded
  installation may continue to use a legacy data directory to preserve history.
- On Windows, cookies sent by the extension with the user's permission are
  encrypted with DPAPI and removed from the active inbox record after
  acceptance or cancellation. SQLite, WAL and backup files may retain earlier
  encrypted data.
- During media downloads, session cookies are decrypted into a temporary
  `hngoos-session-*` file in the data directory and removed when the task ends
  normally. Forced termination may leave that file behind. Cookie files
  manually exported and selected by the user remain under the user's control.
- Media processing, PDF operations and archive extraction use temporary staging
  files. Abrupt termination may leave data behind. Do not attach the entire
  data directory or build directory to a bug report.

HDM does not automatically upload personal files to scanning services. Online
reputation checks use file hashes; review which external service will be
opened or contacted. Video downloads, website captures, subtitles and updates
connect to the relevant servers in response to user actions.

See the [privacy policy](docs/PRIVACY.md) for more information.

## Automated checks

The [Security workflow](https://github.com/hngoos/hngoos-download-manager/actions/workflows/security.yml)
scans Git history for secrets, audits Python and JavaScript dependencies, and
runs CodeQL analysis for Python and JavaScript. Dependabot monitors dependencies
and workflow actions. Actions are pinned to commits, and checkout does not
retain credentials in the Git configuration.

The [security review record](docs/SECURITY_REVIEW.md) describes the scope and
results of the recorded self-review. No scan guarantees complete safety.
Native components such as media and PDF libraries, as well as external
websites, require ongoing updates and separate testing.
