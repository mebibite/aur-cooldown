# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`aur-cooldown` delays AUR upgrades until a version has aged N days (default 7)
in the AUR, so a malicious push is caught and pulled before it reaches the
machine. The whole tool is one executable Python file (`aur-cooldown`, no `.py`
extension, stdlib only, 3.8+) plus support files in `contrib/`. There is no
build step — run `./aur-cooldown <cmd>` straight from a checkout.

## Commands

```sh
make check                                   # byte-compile the script
make test                                    # == uv run pytest
uv run pytest tests/test_aur_cooldown.py::test_resolve_up_to_date   # single test
uv run pytest -k denylist                    # subset
zsh  -n contrib/completions/_aur-cooldown    # completion syntax checks
bash -n contrib/completions/aur-cooldown.bash
```

Tests need `git` and `pacman` (for `vercmp`) on `PATH` — they use both for real
and stub only the network, AUR clones, and pacman queries. So the suite runs on
an Arch host or in the pinned `archlinux:base-devel` CI container.
`tests/test_nudge.py` drives `contrib/nudge.sh` through a real pty (the `[Y/n]`
prompt is skipped when stdin is not a terminal) under bash, and under zsh when
it is installed; it puts a stub `aur-cooldown` on a sandboxed `PATH` so the
host's real one is never shadowed in or run.

Run the tool against throwaway dirs so development never touches the real
ledger, cache, or config:

```sh
export AUR_COOLDOWN_STATE=$(mktemp -d) AUR_COOLDOWN_CACHE=$(mktemp -d)
export XDG_CONFIG_HOME=$(mktemp -d) AUR_COOLDOWN_DAYS=7
./aur-cooldown observe
./aur-cooldown upgrade --dry-run     # prefer --dry-run; it builds nothing
```

## Architecture

**Two halves cover two kinds of package.** `contrib/yay-init.lua` (a yay v13
`UpgradeSelect` Lua hook) holds back any AUR upgrade younger than 7 days —
that is the whole story for packages that release less often than weekly. The
Python tool exists for packages that release *faster* than the cooldown, whose
tip is always "too fresh" and which the hook alone would pin forever; it
installs the newest version that has already aged, built from git at the exact
vetted commit.

**The ledger is why the tool has state.** The AUR RPC only reports
`LastModified` (server-set, un-forgeable) for the *current* version, so
`observe` appends what it sees to `~/.local/share/aur-cooldown/ledger.jsonl`
(one JSON object per line: `pkg`, `base`, `version`, `commit`,
`last_modified`, `seen_at`). Everything else reads that history. `observe`
takes two RPC snapshots around the `git ls-remote` so a push landing mid-read
cannot bind a different commit to an older timestamp; if they disagree the
entry is skipped and retried next run.

**`resolve()` (`aur-cooldown:528`) is the core decision.** Given a package it
returns one of `build / up-to-date / none / yanked / denied / not-installed /
error`. It walks aged ledger entries newest-first, skips locally revoked and
campaign-window-denied ones, then requires the recorded commit to still be in
the package's current git history and builds the **oldest** commit carrying
that version string — so a later push reusing an already-aged version never
gets selected. `cmd_upgrade` turns that into build+install; `cmd_status`
reports it without touching git.

**Two denial layers, both fail-safe.** `~/.config/aur-cooldown/revoked` is the
local denylist. The built-in feed is aur-malware-check's `campaigns.json`,
whose entries carry a date window, so denial is version-scoped (a version is
refused only if its push timestamp falls inside the window) and a package that
has since shipped clean still installs. Campaigns without a window produce a
printed *advisory* only, never a freeze. A failed fetch keeps the previous
cache, so a bad network day can never make something newly installable.

**`setup` edits the user's dotfiles, deliberately and reversibly.** Packaging
must not touch dotfiles, so `cmd_setup` writes marked blocks (`>>> aur-cooldown
>>>` … `<<< aur-cooldown <<<`) into `~/.config/yay/init.lua` and the shell rc
via `write_block`/`strip_block`, which `--revert` removes and `--print`
previews. It backs off when yay is missing or another `UpgradeSelect` hook is
already present.

## Invariants — do not break these

- **Standard library only.** No third-party imports, ever; the tool must stay
  trivially auditable and installable without a dependency chain.
- **Never measure age from git.** Commit dates are attacker-chosen
  (`GIT_COMMITTER_DATE`); age comes only from the AUR RPC `LastModified`.
- **Fail closed.** Anything unverifiable makes the tool wait, not install. The
  denylist may only withhold an install, never cause one. Call out in the PR
  description any change that touches these properties.
- Module-level path constants (`LEDGER`, `STATE`, `CONFDIR`, …) are rebound by
  the tests' autouse `isolate_paths` fixture. Read them as module globals at
  call time; do not capture them into default arguments or closures at import.

## Conventions

Small named helpers, plain names, comments that explain *why*. `contrib/nudge.sh`
must work under both bash and zsh. A new command or flag means updating the
README, both completions, the relevant `contrib/*.example`, and a `CHANGELOG.md`
entry under the unreleased heading.

## Version and release

The version lives in exactly one place: `VERSION = "..."` in the `aur-cooldown`
script (it ships standalone, so it must be embedded). `pyproject.toml` reads it
via hatchling; `PKGBUILD`'s `pkgver` is a placeholder the release workflow
overwrites. Releases are published to the AUR only by manual dispatch of the
**Publish to AUR** workflow with an approval gate — never by a tag push. See
CONTRIBUTING.md for the full release steps.
