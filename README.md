# aur-cooldown

Delay AUR upgrades until they have aged for a week.

The AUR has no review process. When a maintainer account is hijacked or an
orphaned package is adopted by an attacker, the malicious push reaches everyone
who updates before it gets noticed. In the incidents of July 2025 (Chaos RAT)
and June 2026 (400+ packages carrying an infostealer and an eBPF rootkit), the
bad versions were identified and removed within days. Users who only installed
versions that had already been public for a week were never exposed.

aur-cooldown enforces exactly that policy: a version becomes installable once
it has survived N days (default 7) in the AUR. Detection is the community's
job; your machine just stays out of the blast window.

## How it works

Two parts, covering two kinds of packages:

The **yay hook** (`contrib/yay-init.lua`, yay v13+) makes `yay -Syu` hold back
any AUR upgrade whose newest version is less than 7 days old. For the large
majority of packages, which release less often than weekly, this is the whole
story: updates arrive one week late, and nothing else changes.

The **aur-cooldown tool** handles packages that release faster than the
cooldown (editors, AI tools, browsers with weekly builds). Their newest version
is always "too fresh", so the hook alone would pin them forever. The tool keeps
a local ledger of every version it has seen, together with the AUR server's
push timestamp, and installs the newest version that has aged past the
cooldown, exported from the package's git history at the exact vetted commit
and built with `makepkg`.

New installs are unaffected: `yay -S somepkg` behaves as always, and the
package joins the cooldown from the next `observe` on.

## Installation

From the AUR:

    yay -S aur-cooldown

From source:

    git clone https://github.com/adrinjalali/aur-cooldown
    cd aur-cooldown
    sudo make install        # /usr/local by default

Dependencies: `python` (3.8+, standard library only), `git`, `pacman`,
`base-devel` (for `makepkg`). `yay` is optional and only needed for the
`yay -Syu` cooldown hook that `setup` installs.

Then wire it into your own config:

    aur-cooldown setup          # preview with: aur-cooldown setup --print

`setup` wires up three things (the first two in a marked block it can update or
remove later with `aur-cooldown setup --revert`):

1. the yay hook, into `~/.config/yay/init.lua`, so `yay -Syu` holds fresh AUR
   upgrades (skipped, with a note, if you already have an `UpgradeSelect` hook);
2. a reminder to your shell rc (`~/.zshrc` or `~/.bashrc`) that tells you when
   the ledger is stale;
3. if you run yay with `--sudo`, the matching `sudo` setting in
   `~/.config/aur-cooldown/config`, so installs escalate the same way.

Installing the package deliberately does none of this: an Arch package must not
touch your dotfiles or another package's config, and there is no system-wide
yay configuration to drop the hook into. `setup` is the supported, reversible
way to opt in, and you can always do the two steps by hand instead.

## Usage

    aur-cooldown observe            # record versions and push times; run every few days
    aur-cooldown status             # eligible aged version vs current tip, per package
    aur-cooldown upgrade --dry-run  # preview
    aur-cooldown upgrade            # build and install what has aged in (asks first)
    aur-cooldown upgrade -y         # same, without the confirmation prompt

`upgrade` shows the plan and asks before it builds or installs anything
(pacman-style `[Y/n]`); pass `-y` for unattended runs.

`observe` is one batched RPC request (about 35 kB for 60 packages) plus a
`git ls-remote` per newly seen version. `upgrade` clones package repositories
only for packages that actually have a pending aged upgrade.

    $ aur-cooldown status
    last observe: 2026-07-05 16:57 (1d ago)
    cooldown: 7 days   tracked: 48   frozen by feed: 0

      claude-code        eligible: 2.1.191-1 (pushed 2026-06-24)   tip: 2.1.201-1 (pushed 2026-07-04)
      cursor-bin         eligible: 3.9.8-1 (pushed 2026-06-25)     tip: 3.9.16-1 (pushed 2026-06-28)
      ...

## Configuration

Everything lives in `~/.config/aur-cooldown/`; all files are optional.

| File | Purpose |
|---|---|
| `packages` | explicit package list, one per line; when absent or empty, every installed AUR package is tracked (`pacman -Qm`, excluding `-debug` split companions) |
| `revoked` | local denylist, `<pkg> <version-or-commit-prefix>` per line |
| `denylist-feeds` | remote denylist feed URLs, one per line; off by default |
| `config` | `key = value` settings; currently `sudo` and `sudoflags` |

### Gaining root for the install

`upgrade` builds the package as your user, then installs it as root. Like yay,
it uses `sudo` by default and falls back to `su` when `sudo` is not installed.
If you escalate with `su` (or `doas`, etc.), set it once:

    # ~/.config/aur-cooldown/config
    sudo = su

or pass it per run: `aur-cooldown upgrade --sudo su --sudoflags '-l'`. If you
already tell yay which command to use (`yay --sudo=su`), `aur-cooldown setup`
detects that and writes the matching `config` for you.

State (the ledger) is in `~/.local/share/aur-cooldown/`, git clones and build
trees in `~/.cache/aur-cooldown/`. `AUR_COOLDOWN_DAYS` overrides the cooldown
length.

## Denylist feeds

A feed is a URL returning AUR package names, one per line. Any tracked package
that appears on a feed is frozen: `upgrade` refuses to touch it until it drops
off the feed. Feeds are fetched during `observe` (and by `refresh`); if a fetch
fails, the previous cache is kept.

Feeds are safe to consume from third parties because a denylist is fail-safe:
it can only withhold an install, never cause one. The worst a wrong or stale
feed does is make you wait.

A good feed is the community-maintained campaign list from
[aur-malware-check](https://github.com/lenucksi/aur-malware-check), which
consolidates the aur-general mailing list and the official incident notes. Be
aware that it is name-level: a listed package was part of a campaign, which
does not necessarily mean your installed build is affected. See
`denylist-feeds.example` in the share directory.

## Security model

The cooldown is only as good as the clock it trusts, and the obvious clock is
the one that cannot be trusted: git commit dates are chosen by whoever makes
the commit, and the June 2026 attackers forged commit metadata to pose as a
long-standing maintainer. A tool that measured age with `git log` would accept
a malicious commit backdated by eight days as already aged.

aur-cooldown therefore never reads dates from git. Age comes from the AUR RPC
`LastModified` field, which the server sets when a push is accepted and the
uploader cannot influence. Since the RPC only reports it for the current
version, `observe` records it over time; that is why the ledger exists.

Each observation binds the version to the exact git commit that carried it,
captured between two RPC snapshots so that a push landing mid-observation
cannot associate a different commit with an older timestamp. At upgrade time a
version is built only if its recorded commit is still part of the package's
current history, and the build uses the oldest commit in that history carrying
the version. The practical consequences:

| Scenario | Outcome |
|---|---|
| Malicious push, backdated commit date | not eligible; its server timestamp is fresh |
| Malicious push reusing an already-aged version string | the oldest commit with that version is built, which is the original clean one |
| Bad version removed by AUR staff (delete or reset, the usual cleanup) | recorded commit gone from history; skipped, tool waits |
| Version we never observed | never installed |
| Feed or network failure | previous state kept; nothing new becomes installable |

Everything unverifiable fails closed: the tool waits rather than installs.

Known limits, stated plainly:

- The guarantee is conditional on detection: a malicious version that stays
  unnoticed longer than the cooldown will age in and be installed. The cooldown
  length is the knob; 7 days covered both known incidents comfortably.
- If a compromise were cleaned up by committing a fix on top while leaving the
  malicious commit in history (not how AUR staff have handled incidents, which
  is deletion or reset), a fast-moving package could select the superseded bad
  version during the window before the fix ages in. The denylist is the
  backstop for this case.
- aur-cooldown does not inspect package contents. It is not a scanner and does
  not replace one; for checking whether a machine was already affected by a
  known campaign, use
  [aur-malware-check](https://github.com/lenucksi/aur-malware-check).

## License

MIT.
