# Changelog

## Unreleased

- Reworked the denylist around aur-malware-check's `campaigns.json`. Denial is
  now **version-scoped by date window**: a version is refused only if its AUR
  push timestamp falls inside a campaign's compromise window, so a package that
  has shipped a clean version since is no longer pinned by name forever (the old
  name-level feed froze listed packages indefinitely). On by default; disable
  with `denylist = off` or repoint with `denylist_source`.
- Campaigns with no date window are no longer frozen. Their entries are
  legitimate hijacked-then-cleaned packages; `observe`/`status`/`upgrade` print
  an advisory naming any installed one and suggest an `IgnorePkg` hard-block,
  rather than silently pinning it.
- `refresh` now reports windowed vs advisory package counts. The cache moved to
  `~/.local/share/aur-cooldown/denylist.cache.json`.

## 0.6.1 — 2026-07-17

First public release. (0.6.0 was tagged but never published; its release
tarball was missing a packaged file.)

- `observe`, `upgrade`, `status`, `refresh` subcommands; single-file Python,
  standard library only.
- Package age is measured with the AUR RPC `LastModified` timestamp, which is
  set server-side at push time. Git commit dates are never trusted: they are
  chosen by the committer and were forged in the June 2026 AUR incident.
- The ledger binds every observed version to its exact git commit, taken
  between two RPC snapshots so a concurrent push cannot associate a different
  commit with an older timestamp.
- Upgrades build the oldest canonical commit carrying the aged version and
  require the recorded commit to still be part of the package's history.
  Versions removed during incident cleanup are skipped; reusing an aged
  version string on a newer commit has no effect.
- Tracks all installed AUR packages by default (`pacman -Qm`, excluding
  `-debug` split companions); an explicit list can be configured instead.
- Local denylist plus optional remote denylist feeds (package-name level,
  off by default). Feeds can only withhold an install, never cause one.
- Ships a yay v13 hook that holds fresh AUR upgrades in `yay -Syu`, and a
  POSIX shell snippet (bash/zsh) that reminds you when the ledger goes stale.
- `aur-cooldown setup` wires the hook and reminder into your own config in
  reversible, marker-delimited blocks (`--print` to preview, `--revert` to
  undo). Package installation never edits user files, per Arch guidelines.
  `setup` skips the yay hook when yay is not on `PATH`.
- Ships zsh and bash completions (subcommands, flags, and installed AUR
  package names), installed into the standard completion directories.
- `upgrade` asks for confirmation before building anything (pacman-style
  `[Y/n]`); `-y`/`--yes` skips the prompt for unattended runs. Without a
  terminal it refuses unless `-y` is given.
- `upgrade` builds the pinned commit by exporting it (`git archive`) to a
  plain tree and running `makepkg`. `yay -B` was unusable: it treats the
  build directory as a git clone to update to the latest commit, which
  errored on the export and would have defeated the point of building an
  older, vetted revision. `makepkg` builds exactly the exported tree and
  cannot drift off the commit aur-cooldown selected.
- `upgrade` now lists held packages instead of only counting them: which
  version is cooling and the day it becomes eligible, and separately which
  installed packages have not been observed yet.
- `upgrade` escalates the install itself instead of relying on `makepkg -si`:
  it builds as the user, then installs the built package as root through a
  configurable command. Defaults to `sudo`, falling back to `su`, and honours
  `--sudo`/`--sudoflags` or a `sudo` line in `~/.config/aur-cooldown/config`
  (mirroring yay). This makes it work for users who escalate with `su` or
  `doas` rather than `sudo`. Repository dependencies are installed the same
  way; AUR dependencies are still not resolved.
- `aur-cooldown setup` detects a `yay --sudo=<bin>` preference in your shell rc
  and writes the matching `config`, so `upgrade` escalates like your yay does.
- Before every privileged step, `upgrade` prints the exact command it is about
  to run as root (e.g. `running as root: su -c 'pacman -U ...'`).
- `upgrade` downloads sources into a persistent cache (`SRCDEST`,
  `~/.cache/aur-cooldown/sources`) instead of the throwaway build tree, so a
  rebuild after a failure reuses the already-fetched, checksummed files rather
  than downloading them again.
