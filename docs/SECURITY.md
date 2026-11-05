# Security policy

[Home](../README.md) · [Feature reference](FEATURES.md) · [Privacy](PRIVACY.md)

## Supported versions

| Version | Policy |
| --- | --- |
| v0.1.0 | Receives security fixes |
| Documentation on `main` | Receives corrections and updated guidance |

## Report a vulnerability privately

Use [Report a vulnerability](https://github.com/hngoos/hngoos-download-manager/security/advisories/new) to submit a private report. Include the affected version, reproducible steps using synthetic or non-sensitive data, the impact, and any known mitigation.

Do not publish working exploits in public issues. Do not include passwords, cookies, access tokens, signing keys, private download databases, or personal files. If a suspicious sample is needed, describe it first and use a harmless synthetic example; do not attach live malware to the repository.

HDM is maintained by an individual. There is no guaranteed response time or bug bounty program.

## Understand the protection boundaries

- File inspection detects selected risk indicators; it is not a full malware analysis engine.
- Quarantine by filename does not isolate a file from other applications or from a compromised Windows account.
- A locally computed checksum describes the bytes. Verification requires an expected checksum from a trusted source.
- Authenticode status and online hash reputation are supporting signals, not guarantees of safety.
- DPAPI protects queued session data under the current Windows account. Other processes running as that user may be able to decrypt it.
- PDF redaction produces a raster document without the original text layer. Review the exported pages before sharing them.
- Signed update metadata checks publisher-key continuity and package integrity. The current installer does not have an Authenticode signature or established SmartScreen reputation.

The [feature reference](FEATURES.md) documents archive limits, experimental features, and current verification scope. The [privacy policy](PRIVACY.md) explains local data and optional extension permissions.
