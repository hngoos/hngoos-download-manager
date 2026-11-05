# Security Policy

## Reporting a vulnerability

If you find a security issue in HDM, submit a
[private vulnerability report](https://github.com/hngoos/hngoos-download-manager/security/advisories/new)
or email [1hngoos@gmail.com](mailto:1hngoos@gmail.com).

Please keep vulnerability details private until a fix or mitigation is
available. Use [GitHub Issues](https://github.com/hngoos/hngoos-download-manager/issues)
for ordinary bugs and feature requests.

### What to include

- The HDM version, operating system and browser extension version, if relevant.
- Steps to reproduce the issue using synthetic or non-sensitive data.
- The expected and actual behavior, and the potential security impact.
- A minimal proof of concept or redacted screenshots, if available.

Do not send passwords, cookies, access tokens, signing keys, personal files,
or download history databases. Describe suspicious samples before sending
anything; do not attach live malware to the repository.

## Supported versions

| Version | Security support |
| --- | --- |
| [Latest release](https://github.com/hngoos/hngoos-download-manager/releases/latest) | Receives security fixes |
| `main` | Receives fixes for ongoing development |
| Older releases | Upgrade to the latest release |

macOS and Linux packages remain previews. See
[platform support](docs/PLATFORMS.md) for their current limitations.

## Response and disclosure

HDM is maintained by an individual. Reports are reviewed as capacity permits;
there is no guaranteed response time or bug bounty program. Please coordinate
public disclosure with the maintainer so users have time to update.

## Security and privacy details

- [Protection boundaries and local data](docs/SECURITY.md)
- [Privacy policy](docs/PRIVACY.md)
- [Recorded security review](docs/SECURITY_REVIEW.md)

<a id="du-lieu-cuc-bo"></a>
<a id="local-data"></a>

Local data handling is documented in the
[security reference](docs/SECURITY.md#local-data).
