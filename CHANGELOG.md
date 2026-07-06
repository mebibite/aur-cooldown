# Changelog

## 0.5.0 — unreleased

First public release.

- `observe` / `upgrade` / `status` / `refresh` subcommands.
- Age judged by the AUR RPC `LastModified` (server-authoritative), never git commit
  dates, which are forgeable (`GIT_COMMITTER_DATE`) — the technique used in the
  June 2026 AUR incident.
- Local ledger binds each observed version to its exact commit hash; upgrades verify
  the commit still exists, is an ancestor of HEAD, and matches the recorded version
  (defeats reset/delete cleanup and version-string reuse).
- Auto-tracks all installed AUR packages (`pacman -Qm`, minus `-debug` companions).
- Opt-in denylist feeds (package-name granularity), fail-safe by construction.
- Unattended builds via `yay -B` (no PKGBUILD review step by design).
- Ships the yay "wall" hook and a zsh reminder in `contrib/`.
