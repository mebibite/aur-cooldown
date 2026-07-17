# Security Policy

## Reporting a vulnerability

Please report security issues privately. Do not open a public issue,
especially for anything that could let a malicious package version bypass the
cooldown or the denylist.

Use GitHub's private vulnerability reporting:
[**Report a vulnerability**](https://github.com/adrinjalali/aur-cooldown/security/advisories/new)
(the same button appears on the repository's **Security** tab).

A useful report says what the tool does, what it should have done, and — if you
have one — a concrete sequence (ledger state, commits, timestamps) that
demonstrates the gap. You'll get a response as soon as reasonably possible.

The guarantees the tool tries to keep are written out in the
[Security model](README.md#security-model) section of the README; findings that
break one of those are exactly what's most valuable.

## Supported versions

Fixes land in the latest release; there are no separate maintenance branches.
Always report against the newest version (`aur-cooldown --version`).
