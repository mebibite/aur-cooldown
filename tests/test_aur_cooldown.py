"""Unit tests for aur-cooldown.

The tool is a single executable script (no .py extension), so it is loaded as a
module here. Network (HTTP/RPC), pacman queries, and AUR clones are stubbed;
git and vercmp are used for real, so these run on an Arch host (or the archlinux
CI container). Run with: make test
"""
import calendar
import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
import shutil
import subprocess
import tempfile
import time
import types
import unittest
from unittest import mock

TOOL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "aur-cooldown")


def load_module():
    loader = importlib.machinery.SourceFileLoader("aur_cooldown", TOOL)
    mod = importlib.util.module_from_spec(importlib.util.spec_from_loader("aur_cooldown", loader))
    loader.exec_module(mod)
    return mod


m = load_module()


def ts(datestr):
    return calendar.timegm(time.strptime(datestr, "%Y-%m-%d"))


def git(repo, *args):
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
    return subprocess.run(["git", "-C", repo, *args], check=True, env=env,
                          stdout=subprocess.PIPE, text=True).stdout.strip()


class Base(unittest.TestCase):
    """Isolate every file path the tool touches into a fresh temp dir."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        state = os.path.join(self.tmp, "state")
        cache = os.path.join(self.tmp, "cache")
        conf = os.path.join(self.tmp, "config")
        for d in (state, cache, conf):
            os.makedirs(d, exist_ok=True)
        m.STATE, m.CACHE, m.CONFDIR = state, cache, conf
        m.LEDGER = os.path.join(state, "ledger.jsonl")
        m.LASTOBS = os.path.join(state, "last-observe")
        m.DENY_CACHE = os.path.join(state, "denylist.cache.json")
        m.SRCDEST = os.path.join(cache, "sources")
        m.PKGCONF = os.path.join(conf, "packages")
        m.DENY = os.path.join(conf, "revoked")
        m.FEEDSCONF = os.path.join(conf, "denylist-feeds")
        m.CONFIGFILE = os.path.join(conf, "config")

    def write(self, path, text):
        with open(path, "w") as fh:
            fh.write(text)

    def read(self, path):
        with open(path) as fh:
            return fh.read()

    def write_ledger(self, rows):
        with open(m.LEDGER, "w") as fh:
            for r in rows:
                fh.write(json.dumps(r) + "\n")

    def row(self, pkg, version, last_modified, commit="c" * 40, base=None):
        return {"pkg": pkg, "base": base or pkg, "version": version,
                "commit": commit, "last_modified": last_modified, "seen_at": last_modified}


# --------------------------------------------------------------------- ledger

class TestLedger(Base):
    def test_loads_valid_skips_malformed(self):
        with open(m.LEDGER, "w") as fh:
            fh.write(json.dumps(self.row("foo", "1-1", 100)) + "\n")
            fh.write("not json\n")
            fh.write("\n")
            fh.write(json.dumps({"pkg": "bar"}) + "\n")            # missing keys
        rows = m.load_ledger()
        self.assertEqual([r["pkg"] for r in rows], ["foo"])

    def test_missing_file_is_empty(self):
        self.assertEqual(m.load_ledger(), [])

    def test_aged_versions_filters_and_orders(self):
        rows = [self.row("foo", "1-1", 100, "a" * 40),
                self.row("foo", "2-1", 200, "b" * 40),
                self.row("foo", "3-1", 300, "d" * 40),
                self.row("foo", "4-1", 400, "")]        # no commit -> ignored
        aged = m.aged_versions("foo", 250, rows)
        self.assertEqual([e["version"] for e in aged], ["2-1", "1-1"])

    def test_base_for(self):
        rows = [self.row("foo", "1-1", 100, base="foo-base")]
        self.assertEqual(m.base_for("foo", rows), "foo-base")
        self.assertEqual(m.base_for("absent", rows), "")


# ------------------------------------------------------------- local denylist

class TestLocalDenylist(Base):
    def test_parse_and_match(self):
        self.write(m.DENY, "# comment\nfoo 1.2.3-1\nbar deadbee\n\n")
        deny = m.local_denylist()
        self.assertEqual(set(deny), {("foo", "1.2.3-1"), ("bar", "deadbee")})
        self.assertTrue(m.denied_version("foo", "1.2.3-1", "x" * 40, deny))     # exact version
        self.assertTrue(m.denied_version("bar", "9-9", "deadbeef1234", deny))   # commit prefix
        self.assertFalse(m.denied_version("bar", "9-9", "feed0000", deny))
        self.assertFalse(m.denied_version("other", "1.2.3-1", "x", deny))


# ------------------------------------------------------------- campaign denylist

CAMPAIGNS = json.dumps({"campaigns": [
    {"id": "c1", "type": "aur", "display": "C1 (June)",
     "lists": ["data/campaigns/c1/packages.txt", "data/campaigns/c1/packages-extra.txt"],
     "date_window": {"start": "2026-06-09", "end": "2026-06-14"}},
    {"id": "c2", "type": "aur", "display": "C2 spam",
     "lists": ["data/campaigns/c2/packages.txt"], "date_window": None},
    {"id": "npm", "type": "npm", "lists": ["data/whatever.txt"],
     "date_window": {"start": "2026-06-09", "end": "2026-06-14"}},
]})
ROOT = "https://raw.githubusercontent.com/lenucksi/aur-malware-check/master/"
FILES = {
    m.DENY_SOURCE: CAMPAIGNS,
    ROOT + "data/campaigns/c1/packages.txt": "foo\nbar\n",
    ROOT + "data/campaigns/c1/packages-extra.txt": "# extra\nextra-pkg\n",
    ROOT + "data/campaigns/c2/packages.txt": "spammy\n",
}


class TestCampaignDenylist(Base):
    def refresh(self, conf=None, files=None):
        with mock.patch.object(m, "_http_get", lambda url: (files or FILES)[url]):
            return m.refresh_denylist(conf or {})

    def test_window_bounds_inclusive(self):
        start, end = m._window_bounds({"start": "2026-06-09", "end": "2026-06-14"})
        self.assertEqual(start, ts("2026-06-09"))
        self.assertEqual(end, ts("2026-06-14") + 86400 - 1)

    def test_names_parsing(self):
        self.assertEqual(m._names("# c\nfoo\n bar baz \n\n"), ["foo", "bar"])

    def test_windows_advisory_and_inheritance(self):
        dl = self.refresh()
        self.assertEqual(set(dl["windows"]), {"foo", "bar", "extra-pkg"})   # extra inherits c1 window
        self.assertEqual(dl["advisory"], {"spammy": ["C2 spam"]})           # npm campaign ignored
        self.assertEqual(dl["windows"]["foo"][0],
                         [ts("2026-06-09"), ts("2026-06-14") + 86399])

    def test_window_denied(self):
        dl = self.refresh()
        self.assertTrue(m.window_denied("foo", ts("2026-06-10"), dl))
        self.assertFalse(m.window_denied("foo", ts("2026-06-08"), dl))    # before
        self.assertFalse(m.window_denied("foo", ts("2026-06-20"), dl))    # after
        self.assertFalse(m.window_denied("spammy", ts("2026-06-10"), dl))  # advisory has no window

    def test_persisted_and_loaded(self):
        self.refresh()
        dl = m.load_denylist()
        self.assertIn("foo", dl["windows"])
        self.assertIn("spammy", dl["advisory"])

    def test_corrupt_cache_is_empty(self):
        self.write(m.DENY_CACHE, "{ not json")
        self.assertEqual(m.load_denylist(), {"windows": {}, "advisory": {}})

    def test_extra_feed_is_advisory(self):
        self.write(m.FEEDSCONF, "https://example.org/list.txt\n")
        files = dict(FILES, **{"https://example.org/list.txt": "mypkg\n"})
        dl = self.refresh(files=files)
        self.assertEqual(dl["advisory"]["mypkg"], ["https://example.org/list.txt"])

    def test_disabled_returns_empty(self):
        self.refresh()  # populate a cache first
        dl = m.refresh_denylist({"denylist": "off"})
        self.assertEqual(dl, {"windows": {}, "advisory": {}})

    def test_fail_closed_keeps_cache(self):
        good = self.refresh()
        def boom(_url):
            raise OSError("network down")
        with mock.patch.object(m, "_http_get", boom):
            stale = m.refresh_denylist({})
        self.assertEqual(sorted(stale["windows"]), sorted(good["windows"]))

    def test_advisory_hits_intersects_installed(self):
        dl = self.refresh()
        with mock.patch.object(m, "installed_aur", lambda: ["spammy", "unrelated"]):
            self.assertEqual(m.advisory_hits(dl), [("spammy", ["C2 spam"])])
        with mock.patch.object(m, "installed_aur", lambda: ["unrelated"]):
            self.assertEqual(m.advisory_hits(dl), [])


# ------------------------------------------------------------------ resolve

class TestResolve(Base):
    def make_repo(self):
        repo = os.path.join(self.tmp, "repo")
        os.makedirs(repo)
        subprocess.run(["git", "init", "-q", "-b", "master", repo], check=True)
        git(repo, "config", "user.email", "t@t")
        git(repo, "config", "user.name", "t")
        git(repo, "config", "commit.gpgsign", "false")   # CI/host may enable signing
        return repo

    def commit(self, repo, pkgver, pkgrel="1"):
        self.write(os.path.join(repo, ".SRCINFO"),
                   f"pkgbase = demo\n\tpkgver = {pkgver}\n\tpkgrel = {pkgrel}\n\npkgname = demo\n")
        self.write(os.path.join(repo, "PKGBUILD"), f"pkgver={pkgver}\npkgrel={pkgrel}\n")
        git(repo, "add", "-A")
        git(repo, "commit", "-q", "-m", f"{pkgver}-{pkgrel}")
        return git(repo, "rev-parse", "HEAD")

    def resolve(self, pkg, cutoff, rows, deny=None, dl=None, is_auto=True, installed=None):
        with mock.patch.object(m, "installed_version", lambda p: installed):
            return m.resolve(pkg, cutoff, rows, deny or [], dl or {"windows": {}, "advisory": {}}, is_auto)

    def test_not_installed_auto(self):
        action, _ = self.resolve("foo", m.now(), [], installed=None, is_auto=True)
        self.assertEqual(action, "not-installed")

    def test_unobserved(self):
        action, detail = self.resolve("foo", m.now(), [], installed="1-1", is_auto=False)
        self.assertEqual((action, detail["state"]), ("none", "unobserved"))

    def test_cooling(self):
        rows = [self.row("foo", "2-1", m.now() - 3600, "a" * 40)]   # fresh, newer than installed
        action, detail = self.resolve("foo", m.now() - m.DAYS * 86400, rows,
                                      installed="1-1", is_auto=False)
        self.assertEqual((action, detail["state"]), ("none", "cooling"))

    def test_up_to_date(self):
        rows = [self.row("foo", "1-1", 100, "a" * 40)]
        action, detail = self.resolve("foo", m.now(), rows, installed="1-1", is_auto=False)
        self.assertEqual(action, "up-to-date")

    def test_build_picks_oldest_commit_for_reused_version(self):
        repo = self.make_repo()
        sha_old = self.commit(repo, "1.0")     # version 1.0-1 (original)
        self.commit(repo, "2.0")               # 2.0-1
        sha_reuse = self.commit(repo, "1.0")   # 1.0-1 again (malicious reuse), HEAD
        # Even with the *reused* commit recorded, the oldest carrier is built.
        rows = [self.row("foo", "1.0-1", 100, sha_reuse)]
        with mock.patch.object(m, "sync_repo", lambda base: repo):
            action, d = self.resolve("foo", m.now(), rows, installed=None, is_auto=False)
        self.assertEqual(action, "build")
        self.assertEqual(d["commit"], sha_old)

    def test_yanked_when_recorded_commit_absent(self):
        repo = self.make_repo()
        self.commit(repo, "1.0")               # history has 1.0-1 but on a different sha
        rows = [self.row("foo", "1.0-1", 100, "0" * 40)]   # recorded sha not in history
        with mock.patch.object(m, "sync_repo", lambda base: repo):
            action, _ = self.resolve("foo", m.now(), rows, installed=None, is_auto=False)
        self.assertEqual(action, "yanked")

    def test_window_denied_before_touching_git(self):
        dl = {"windows": {"foo": [[ts("2026-06-09"), ts("2026-06-14") + 86399]]}, "advisory": {}}
        rows = [self.row("foo", "1.0-1", ts("2026-06-10"), "a" * 40)]
        def fail(_base):
            raise AssertionError("sync_repo must not be called for a window-denied version")
        with mock.patch.object(m, "sync_repo", fail):
            action, _ = self.resolve("foo", m.now(), rows, dl=dl, installed=None, is_auto=False)
        self.assertEqual(action, "denied")


# ------------------------------------------------------------------- cooling

class TestCoolingInfo(Base):
    def test_states(self):
        rows = [self.row("foo", "2-1", 500, "a" * 40)]
        self.assertEqual(m.cooling_info("foo", "1-1", rows)["state"], "cooling")
        self.assertEqual(m.cooling_info("foo", "2-1", rows)["state"], "current")
        self.assertEqual(m.cooling_info("bar", None, rows)["state"], "unobserved")


# -------------------------------------------------------------------- config

class TestConfig(Base):
    def test_read_config(self):
        self.write(m.CONFIGFILE, "sudo = su   # inline comment\n\n# full\nsudoflags = -l\n")
        conf = m.read_config()
        self.assertEqual(conf, {"sudo": "su", "sudoflags": "-l"})

    def test_resolve_sudo_precedence(self):
        args = types.SimpleNamespace(sudo=None, sudoflags=None)
        self.write(m.CONFIGFILE, "sudo = su\nsudoflags = -l\n")
        self.assertEqual(m.resolve_sudo(args), ("su", ["-l"]))
        cli = types.SimpleNamespace(sudo="doas", sudoflags="-u root")
        self.assertEqual(m.resolve_sudo(cli), ("doas", ["-u", "root"]))
        os.remove(m.CONFIGFILE)
        with mock.patch.object(m.shutil, "which", lambda b: "/usr/bin/sudo"):
            self.assertEqual(m.resolve_sudo(args), ("sudo", []))
        with mock.patch.object(m.shutil, "which", lambda b: None):
            self.assertEqual(m.resolve_sudo(args), ("su", []))

    def test_as_root_forms(self):
        self.assertEqual(m.as_root(["pacman", "-U", "a"], "sudo", []),
                         ["sudo", "pacman", "-U", "a"])
        self.assertEqual(m.as_root(["pacman", "-U", "a b"], "su", []),
                         ["su", "-c", "pacman -U 'a b'"])
        self.assertEqual(m.as_root(["pacman", "-U", "a"], "doas", ["-u", "root"]),
                         ["doas", "-u", "root", "pacman", "-U", "a"])


# --------------------------------------------------------------------- setup

class TestSetupBlocks(Base):
    def test_write_block_idempotent_and_revert(self):
        path = os.path.join(self.tmp, "rc")
        self.write(path, "existing line\n")
        start, end = "# >>>", "# <<<"
        m.write_block(path, start, end, "BODY1", "apply")
        self.assertIn("BODY1", self.read(path))
        m.write_block(path, start, end, "BODY2", "apply")     # replace, not duplicate
        text = self.read(path)
        self.assertNotIn("BODY1", text)
        self.assertEqual(text.count(start), 1)
        self.assertIn("existing line", text)
        m.write_block(path, start, end, "BODY2", "revert")
        self.assertNotIn(start, self.read(path))
        self.assertIn("existing line", self.read(path))

    def test_detect_yay_escalator(self):
        rc = os.path.join(self.tmp, "zshrc")
        self.write(rc, "alias ls='ls --color'\nalias yay='yay --sudo=su'\n")
        with mock.patch.object(m, "shell_rc", lambda: (rc, "zsh")):
            self.assertEqual(m.detect_yay_escalator(), ("su", ""))
        self.write(rc, "alias yay='yay'\n")
        with mock.patch.object(m, "shell_rc", lambda: (rc, "zsh")):
            self.assertIsNone(m.detect_yay_escalator())


# ---------------------------------------------------------------------- deps

class TestInstallDeps(Base):
    def build_with_srcinfo(self, srcinfo):
        build = os.path.join(self.tmp, "build")
        os.makedirs(build, exist_ok=True)
        self.write(os.path.join(build, ".SRCINFO"), srcinfo)
        return build

    def test_no_srcinfo_ok(self):
        self.assertTrue(m.install_deps(os.path.join(self.tmp, "empty"), "sudo", []))

    def test_all_satisfied(self):
        build = self.build_with_srcinfo("pkgbase = x\n\tdepends = bash\n")
        with mock.patch.object(m, "run", lambda *a, **k: types.SimpleNamespace(stdout="")):
            self.assertTrue(m.install_deps(build, "sudo", []))

    def test_installs_missing(self):
        build = self.build_with_srcinfo(
            "pkgbase = x\n\tdepends = foo>=1\n\tmakedepends = bar\n")
        calls = {}
        def fake_root(cmd, sudo, flags):
            calls["cmd"] = cmd
            return 0
        with mock.patch.object(m, "run", lambda *a, **k: types.SimpleNamespace(stdout="foo>=1\nbar")), \
             mock.patch.object(m, "run_root", fake_root), \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertTrue(m.install_deps(build, "su", []))
        self.assertIn("foo", calls["cmd"])
        self.assertIn("bar", calls["cmd"])
        self.assertIn("-S", calls["cmd"])


if __name__ == "__main__":
    unittest.main()
