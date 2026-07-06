# aur-cooldown

**Age-delay your AUR upgrades.** Install an AUR update only after it has survived
`N` days (default 7) in the wild, so a malicious or broken push has time to be caught
before it lands on your machine.

This is a *prevention* tool. For *detection* ("was I already hit by a known campaign?")
use the excellent [`lenucksi/aur-malware-check`](https://github.com/lenucksi/aur-malware-check) —
the two are complementary halves (Protect vs Detect/Respond), and `aur-cooldown` can
consume its package list as a denylist feed (see below).

> **What it is not:** a scanner. It does not inspect PKGBUILDs for malice — most users
> can't meaningfully review a PKGBUILD, and the design deliberately does not depend on
> it. The protection is the *delay*, on the assumption that bad pushes are noticed
> within the cooldown window (the same assumption every "wait before updating"
> practice already relies on).

## Why

The AUR has no review process. A compromised or hijacked maintainer account can push a
malicious update that you'd pull the moment you run `yay -Syu`. The June 2026 incident
(400+ packages, infostealer + rootkit) and the July 2025 Chaos RAT packages are the
motivating examples. A short cooldown means you only ever install versions that have
already been exposed to the community for a while.

## How it works

Two pieces:

1. **The wall** (`contrib/yay-init.lua`) — a yay v13 Lua hook that makes `yay -Syu`
   refuse any AUR upgrade whose newest revision is younger than 7 days. This covers the
   ~90% of packages that release less than weekly: they simply wait a week, then upgrade
   normally. Age comes from the AUR RPC `LastModified` (set server-side at push time).

2. **The cooldown tool** (`aur-cooldown`) — for packages that release *more* than once a
   week (e.g. `claude-code`, `cursor-bin`), whose tip is *always* younger than 7 days and
   would be pinned forever by the wall. It installs the newest revision that *has* already
   aged ≥7 days.

The tricky part is doing (2) safely. See **Security model**.

## Security model

Age must be trustworthy. **Git commit dates are not** — any committer sets them freely
(`GIT_COMMITTER_DATE`; "commit stomping"), and the June 2026 attackers forged commit
metadata. So age is taken from the AUR RPC `LastModified`, which the server stamps on
push and the uploader cannot control. Because the RPC only reports it for the *current*
version, `aur-cooldown observe` captures it over time into a local ledger.

Each ledger entry binds a version to the **exact commit** that carried it. At upgrade
time, the chosen aged version is installed only if its recorded commit:

- **still exists** and **is an ancestor of the current HEAD** — so a version that was
  reset/deleted during incident cleanup is dropped automatically (you wait); and
- **its `.SRCINFO` still is that version** — so a fresh malicious commit that *reuses* an
  already-aged version string resolves to the original good commit, not the attacker's.

Everything is **fail-closed**: anything unverifiable is skipped, never installed. A
[denylist](#denylist) adds a reactive layer. The guarantee holds **as long as malice is
detected within the cooldown window** — that is the one assumption, stated plainly.

### Threats & residuals

| Threat | Status |
|---|---|
| Commit-date spoofing / backdating | **Defended** — age from server `LastModified`, never git dates |
| Reusing an aged version string on a new malicious commit | **Defended** — decision bound to the exact commit hash |
| Reset/force-push cleanup | **Defended** — ancestor-of-HEAD check, fail-closed |
| RPC MITM | **Mitigated** — HTTPS with certificate verification |
| Ledger tampering | Out of scope — requires local write access (already game over); protect via normal home-dir permissions |
| *Forward-fix* leaving malware in canonical history on a fast mover, within the window | **Residual** — narrow; real AUR remediation is reset/delete (which we catch), plus the denylist. See below. |
| Malice undetected for > cooldown window | **Fundamental limit** of any cooldown; tune `AUR_COOLDOWN_DAYS` |

The forward-fix residual: if a bad version were remediated by committing a *fix on top*
(leaving the bad commit in history) rather than resetting it away, there is a short window
(until the fix itself ages in) where a fast mover could select the superseded-but-still-
canonical bad version. In practice AUR incidents are remediated by removal (deletion /
`git reset`), which the ancestor check handles; the denylist is the backstop.

## Install

**From the AUR** (once published): install `aur-cooldown` with your helper, then run
`aur-cooldown`'s user setup below.

**From source:**

```sh
git clone https://github.com/adrinjalali/aur-cooldown
cd aur-cooldown
sudo make install                # binary + templates to /usr/local
make setup-user                  # nudge + config templates into your home; prints 2 steps
```

`make setup-user` seeds `~/.config/aur-cooldown/` and installs the shell reminder, then
prints the two steps it deliberately won't do for you (they touch files you may own):

1. Add to `~/.zshrc`:
   ```zsh
   [[ -f ~/.local/share/aur-cooldown/nudge.zsh ]] && source ~/.local/share/aur-cooldown/nudge.zsh
   ```
2. Merge `contrib/yay-init.lua` into `~/.config/yay/init.lua` (the wall).

Requirements: `python` (3.8+, stdlib only), `git`, `yay` (v13+ for the wall), `pacman`.

## Usage

```sh
aur-cooldown observe          # capture versions+commits+push-times; refresh feeds
aur-cooldown status           # per package: eligible aged version vs current tip
aur-cooldown upgrade --dry-run # preview what would be installed
aur-cooldown upgrade          # build & install aged versions, unattended (yay -B)
```

`observe` is cheap — one batched RPC call (~35 KB for ~60 packages) plus a tiny
`git ls-remote` only for versions that changed. Run it every few days; the shell nudge
reminds you. `upgrade` touches git only for packages that actually have a pending aged
upgrade. Everything else keeps flowing through normal `yay -Syu` (held by the wall).

Config (`~/.config/aur-cooldown/`):

- `packages` — explicit list; if empty/absent, **all installed AUR packages** are tracked.
- `revoked` — manual denylist: `<pkg> <version-or-commit-prefix>`.
- `denylist-feeds` — see below.

Environment: `AUR_COOLDOWN_DAYS` (default 7).

## Denylist

Two layers, both **fail-safe** — a denylist can only *withhold* an install, never cause
one:

- **Local** (`revoked`): freeze a specific version or commit you've learned is bad.
- **Feeds** (`denylist-feeds`, opt-in, off by default): URLs returning AUR package
  *names* to freeze entirely. Fetched on `observe`/`refresh`, best-effort (a failure
  keeps the last cache). Point it at the community campaign list
  ([`lenucksi/aur-malware-check`](https://github.com/lenucksi/aur-malware-check)) and/or,
  during an incident, the official Arch pad. Because a bad feed can only make you *wait*,
  consuming a community list only ever makes you more conservative. See
  `contrib/denylist-feeds.example`.

If an installed package appears on a feed, `observe` warns you and `upgrade` refuses to
touch it. For a full system/IOC scan of a known campaign, use
[`aur-malware-check`](https://github.com/lenucksi/aur-malware-check).

## How new installs behave

`yay -S newpkg` is unaffected — it installs normally and the package auto-enrolls into
the cooldown on the next `observe`. A brand-new package can't be aged on first sight
(there's no prior authoritative timestamp for it), so first installs are a deliberate,
conscious action outside the tool's scope.

## License

MIT. See [LICENSE](LICENSE).
