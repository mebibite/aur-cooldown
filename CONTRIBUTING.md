# Contributing

Thanks for taking an interest. aur-cooldown is a small, security-focused tool,
and the bar for changes reflects that: it should stay easy to read, easy to
audit, and conservative about what it installs. This document covers how to
report problems, how to work on the code, and — for maintainers — how releases
are cut.

## Reporting a security issue

Please do **not** open a public issue for a vulnerability, especially one that
could let a malicious version bypass the cooldown or the denylist.

Use GitHub's private vulnerability reporting (the repository's
**Security** tab → *Report a vulnerability*). A useful report says
what the tool does, what it should have done, and — if you have one —
a concrete sequence (ledger state, commits, timestamps) that
demonstrates the gap. You'll get a response as soon as reasonably
possible.

The threat model and the guarantees the tool tries to keep are written out in
the README's "Security model" section; findings that break one of those are
exactly what's most valuable.

## Reporting bugs and requesting features

For anything that isn't a security weakness, open an issue. For a bug, include:

- `aur-cooldown --version` and your distribution;
- the exact command you ran and its full output;
- what you expected instead.

For a feature, describe the problem you're trying to solve before the solution
you have in mind — it often changes the shape of the fix.

## Working on the code

aur-cooldown is a single Python file (`aur-cooldown`) plus a few support files
in `contrib/`. There is no build step and no dependency install: you run the
script straight from a checkout.

    git clone https://github.com/adrinjalali/aur-cooldown
    cd aur-cooldown
    ./aur-cooldown status

Run it against throwaway directories so you never touch your real ledger,
cache, or config while developing:

    export AUR_COOLDOWN_STATE=$(mktemp -d)
    export AUR_COOLDOWN_CACHE=$(mktemp -d)
    export XDG_CONFIG_HOME=$(mktemp -d)
    export AUR_COOLDOWN_DAYS=7
    ./aur-cooldown observe
    ./aur-cooldown upgrade --dry-run     # prefer --dry-run; it builds nothing

Before opening a PR:

    make check                           # byte-compiles the script
    zsh -n contrib/completions/_aur-cooldown
    bash -n contrib/completions/aur-cooldown.bash

If you touched packaging, build the package from a clean checkout with
`makepkg -f` and confirm the file list is what you expect.

### Guidelines

- **Standard library only.** The tool is one Python file (3.8+) with no
  third-party dependencies. That is deliberate: it has to be trivially
  auditable and installable without a dependency chain. Keep it that way.
- **Match the surrounding style.** Small named helpers, plain names, comments
  that explain *why*. Read a few functions before adding one.
- **Fail closed.** Anything unverifiable must make the tool wait, not install.
  Never measure age from git commit dates (they are attacker-chosen); age comes
  only from the AUR server's `LastModified`. The denylist must stay fail-safe —
  able to withhold an install, never to cause one. If a change weakens any of
  this, say so explicitly in the PR.
- **Portable shell.** `contrib/nudge.sh` must work under both bash and zsh; the
  yay hook is Lua. Keep completions in sync with the CLI.
- **Keep the docs current.** New command or flag → update the README, the
  completions, and any relevant `contrib/*.example`. Add an entry to
  `CHANGELOG.md` under the unreleased heading.

### Pull requests

Keep each PR to one logical change with a clear description of the motivation.
Commit messages should explain the reasoning, not just restate the diff. Call
out any change to behavior or to the security properties above.

By contributing you agree that your work is licensed under the project's MIT
license.

## Releasing (maintainers)

Releases are published to the AUR by the **Publish to AUR** workflow
(`.github/workflows/aur-publish.yml`). It is manual on purpose: a tag push can
be triggered by a leaked git credential, whereas a manual dispatch requires a
GitHub session established with account 2FA, and the deploy waits on an
approval in the `aur` environment. There is no automatic path to publishing.

Per release:

1. Move the `CHANGELOG.md` unreleased entry under a new version heading with the
   date. Bump `pkgver` in `PKGBUILD` to match (the workflow also rewrites it
   from the tag, but keep the committed file honest).
2. Tag and push: `git tag vX.Y.Z && git push origin vX.Y.Z`. The tag only marks
   the commit; it does not publish anything.
3. Actions → **Publish to AUR** → *Run workflow* → enter `vX.Y.Z`, then approve
   the `aur` environment prompt. The workflow sets the version, computes the
   real source checksum with `updpkgsums`, regenerates `.SRCINFO`, and pushes
   `PKGBUILD`, `.SRCINFO`, and `aur-cooldown.install` to the AUR.
4. Check the package page on the AUR and, ideally, install it on a clean system.

