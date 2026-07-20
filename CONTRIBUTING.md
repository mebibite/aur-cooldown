# Contributing

Thanks for taking an interest. aur-cooldown is a small, security-focused tool,
and the bar for changes reflects that: it should stay easy to read, easy to
audit, and conservative about what it installs. This document covers how to
report problems, how to work on the code, and — for maintainers — how releases
are cut.

## Reporting a security issue

Please do **not** open a public issue for a vulnerability, especially one that
could let a malicious version bypass the cooldown or the denylist. Report it
privately instead — see [SECURITY.md](SECURITY.md).

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

### Tests

The tests use [pytest](https://pytest.org) and [uv](https://docs.astral.sh/uv/),
so the whole suite runs with one command and no manual environment setup (uv
reads the `dev` dependency group from `pyproject.toml` and provisions pytest
into a throwaway environment for you):

    make test                            # == uv run pytest

You need `uv`, plus `git` and `pacman` (for `vercmp`) on `PATH`; the tests use
those for real and stub out the network, AUR clones, and pacman queries. If you
would rather not use uv, `pytest` (installed however you like) works too, since
`make test` is just a thin wrapper.

Before opening a PR:

    make check                           # byte-compiles the script
    make test                            # runs the suite
    zsh -n contrib/completions/_aur-cooldown
    bash -n contrib/completions/aur-cooldown.bash

If you touched packaging, build the package from a clean checkout with
`makepkg -f` and confirm the file list is what you expect. CI runs `make check`
and `make test` on every push and PR (in a pinned `archlinux:base-devel`
container), and the release workflow runs them again before publishing.

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

### Where the version lives

The version is written in exactly one place: the `VERSION = "..."` line in the
`aur-cooldown` script (it has to be embedded there, since the script ships
standalone). Everything else derives from it: `pyproject.toml` reads it via
hatchling (`uvx hatch version` prints it), and the release workflow reads it to
set `pkgver`. `PKGBUILD`'s committed `pkgver` is just a placeholder the workflow
overwrites. The one coupling to keep in sync is the git tag, and the release
workflow fails loudly if the tag and the script `VERSION` disagree.

Per release:

1. Bump `VERSION` in the `aur-cooldown` script.
2. Move the `CHANGELOG.md` unreleased entry under a new version heading with the
   date.
3. Tag and push: `git tag vX.Y.Z && git push origin vX.Y.Z`, where `X.Y.Z`
   equals the script `VERSION` exactly. The tag only marks the commit; it does
   not publish anything.
4. Actions → **Publish to AUR** → *Run workflow* → enter `vX.Y.Z`, then approve
   the `aur` environment prompt. The workflow checks the tag matches `VERSION`,
   sets `pkgver`, computes the real source checksum with `updpkgsums`,
   regenerates `.SRCINFO`, runs the tests, and pushes `PKGBUILD`, `.SRCINFO`,
   and `aur-cooldown.install` to the AUR.
5. Check the package page on the AUR and, ideally, install it on a clean system.

### Keeping the CI base image current

CI and the release workflow pin `archlinux:base-devel` by digest. The
`Update Arch base image` workflow runs monthly (and on demand) and opens a PR
bumping that pin when a newer image exists. It runs the suite against the new
image and opens the PR either way, with the pass/fail result in the PR body, so
you merge it if it passed or fix things if it failed.

It deliberately uses no stored credential: only the ephemeral `GITHUB_TOKEN`,
which is minted per run and gone when the run ends, so there is nothing that
could push to the repo if leaked. The trade-off is that `GITHUB_TOKEN` pushes do
not trigger `ci.yml` on the bump PR, so the bump run's own test result is the
signal; pushing a fix commit to the PR branch runs `ci.yml` as normal. If you
would rather CI ran automatically on the PR, run the bump from a bot-owned fork
so the credential only writes to the fork (a fork PR triggers CI like any
contributor's) — that is more isolated than a repo-scoped write token, at the
cost of maintaining a second account. There is intentionally no long-lived
write token wired into this repo.

