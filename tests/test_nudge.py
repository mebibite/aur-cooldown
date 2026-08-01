"""Tests for the shell reminder (contrib/nudge.sh).

The reminder is sourced from an interactive shell rc and now offers to run
`observe`, so it is driven here through a real pty: the prompt is deliberately
skipped when stdin is not a terminal, and only a pty exercises the answer path.
bash is required; zsh is tested too when installed, since the script has to work
under both.
"""
import os
import pty
import re
import select
import shutil
import subprocess
import termios
import time

import pytest

NUDGE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "contrib", "nudge.sh")

# (shell, flags that skip the user's own rc files)
SHELLS = [("bash", ["--norc"]), ("zsh", ["-f"])]
PARAMS = [pytest.param(s, marks=pytest.mark.skipif(shutil.which(s[0]) is None,
                                                   reason=f"{s[0]} not installed"))
          for s in SHELLS]


@pytest.fixture(params=PARAMS, ids=lambda s: s[0])
def sh(request, tmp_path):
    """Run the reminder under one shell, in a sandboxed HOME with a stub tool.

    Returns a callable: sh(answer=..., interactive=..., **env) -> output text.
    The stub `aur-cooldown` on PATH appends its arguments to `sh.calls`.
    """
    shell, flags = request.param
    bindir, state = tmp_path / "bin", tmp_path / "state" / "aur-cooldown"
    bindir.mkdir()
    state.mkdir(parents=True)
    calls = tmp_path / "calls"

    stub = bindir / "aur-cooldown"
    stub.write_text(f'#!/bin/sh\nprintf "%s\\n" "$*" >> "{calls}"\necho stub-observe-ran\n')
    stub.chmod(0o755)

    # Everything the reminder shells out to, and nothing else: the host very
    # likely has a real aur-cooldown in /usr/bin, which must never shadow the
    # stub (nor be run for real, ledger and network and all). nobin is the same
    # minus the stub, for the "tool not installed" case.
    nobin = tmp_path / "nobin"
    nobin.mkdir()
    for tool in ("date", "cat", "mkdir", "stty"):
        os.symlink(shutil.which(tool), bindir / tool)
        os.symlink(shutil.which(tool), nobin / tool)

    base = dict(os.environ, HOME=str(tmp_path), XDG_DATA_HOME=str(tmp_path / "state"),
                PATH=str(bindir))
    for var in ("AUR_COOLDOWN_NUDGE_DAYS", "AUR_COOLDOWN_NUDGE_ASK"):
        base.pop(var, None)

    def run(answer=None, typed=None, interactive=True, tty=True, post="", **env):
        # Absolute path: PATH here is the sandboxed one, without a shell in it.
        argv = ([shutil.which(shell), *flags] + (["-i"] if interactive else [])
                + ["-c", f". {NUDGE}{post}"])
        environ = dict(base, **env)
        if not interactive or not tty:
            # stderr is dropped: an interactive bash without a controlling
            # terminal warns about job control, which is not ours to assert on.
            p = subprocess.run(argv, env=environ, stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                               text=True, timeout=30)
            return _plain(p.stdout)
        master, slave = pty.openpty()
        attrs = termios.tcgetattr(slave)         # no echo, so the answer we
        attrs[3] &= ~termios.ECHO                # type back does not land in
        termios.tcsetattr(slave, termios.TCSANOW, attrs)   # the captured output
        if typed is not None:
            os.write(master, typed.encode())    # already waiting when the shell
        proc = subprocess.Popen(argv, env=environ, stdin=slave, stdout=slave,
                                stderr=slave, close_fds=True, start_new_session=True)
        os.close(slave)                         # starts: type-ahead, not an answer
        return _drain(master, proc, answer)

    run.state = state
    run.calls = calls
    run.nobin = nobin
    return run


def _plain(text):
    """Drop the colour codes, so assertions read like the message does."""
    return re.sub(r"\033\[[0-9;]*m", "", text)


def _drain(master, proc, answer=None, timeout=30):
    """Read until the child closes the pty, answering the prompt when it shows.

    The answer is typed only once "[Y/n]" is on screen, like a real user would:
    sending it earlier is type-ahead, which the reminder deliberately refuses to
    consume. If no prompt ever appears the answer is simply never sent, and the
    shell exits on its own rather than hanging.
    """
    out = b""
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            proc.kill()
            break
        if not select.select([master], [], [], remaining)[0]:
            continue
        try:
            chunk = os.read(master, 4096)
        except OSError:       # EIO once the last slave fd is gone
            break
        if not chunk:
            break
        out += chunk
        if answer is not None and b"[Y/n]" in out:
            os.write(master, answer.encode())
            answer = None
    os.close(master)
    proc.wait(timeout=10)
    return _plain(out.decode(errors="replace"))


def stale(sh, days=9):
    sh.state.joinpath("last-observe").write_text(str(int(time.time()) - days * 86400))


def observed(sh):
    return sh.calls.read_text().split() if sh.calls.exists() else []


def today():
    return time.strftime("%Y-%m-%d")


# ------------------------------------------------------------------ prompting

@pytest.mark.parametrize("answer", ["y", "Y", "\n"])
def test_yes_and_bare_enter_run_observe(sh, answer):
    """One keypress is enough; Enter takes the [Y/n] default."""
    stale(sh)
    out = sh(answer=answer)
    assert "[Y/n]" in out
    assert observed(sh) == ["observe"]


@pytest.mark.parametrize("answer", ["n", "N", "q", " ", "\x04"])
def test_anything_but_yes_declines(sh, answer):
    """Only y/Y/Enter start work — a stray key (or Ctrl-D) must not."""
    stale(sh)
    out = sh(answer=answer)
    assert "[Y/n]" in out
    assert observed(sh) == []


def test_reports_the_age_and_suggests_upgrade_after(sh):
    stale(sh, days=9)
    out = sh(answer="y")
    assert "ledger is 9d old" in out
    assert "stub-observe-ran" in out
    assert "aur-cooldown upgrade" in out       # printed only after observe succeeds


def test_unobserved_ledger_prompts_too(sh):
    out = sh(answer="n")                       # no last-observe file at all
    assert "no metadata yet" in out
    assert "[Y/n]" in out


# ------------------------------------------------------------- type-ahead

def test_typed_ahead_input_is_left_alone(sh):
    """A command typed into a slow-starting shell is neither eaten nor answered."""
    stale(sh)
    out = sh(typed="echo mine\n", post='; read -r rest; printf "LEFT:%s\\n" "$rest"')
    assert "[Y/n]" not in out                  # degraded to the plain reminder
    assert "aur-cooldown observe" in out
    assert "LEFT:echo mine" in out             # every keystroke still queued
    assert observed(sh) == []


def test_half_typed_input_counts_too(sh):
    """Not just whole lines: an unfinished command (no Enter yet) also defers."""
    stale(sh)
    out = sh(typed="echo half")                # no newline
    assert "[Y/n]" not in out
    assert "aur-cooldown observe" in out
    assert observed(sh) == []


# ------------------------------------------------------------------- silence

def test_fresh_ledger_is_silent(sh):
    stale(sh, days=1)                          # under the 3-day threshold
    assert sh(answer="y").strip() == ""
    assert observed(sh) == []


def test_threshold_is_tunable(sh):
    stale(sh, days=4)
    assert sh(answer="n", AUR_COOLDOWN_NUDGE_DAYS="7").strip() == ""
    assert "[Y/n]" in sh(answer="n", AUR_COOLDOWN_NUDGE_DAYS="4")


def test_asks_at_most_once_a_day(sh):
    stale(sh)
    assert "[Y/n]" in sh(answer="n")
    assert sh.state.joinpath("last-nudge").read_text().strip() == today()
    assert sh(answer="y").strip() == ""      # declining still stamps the day
    assert observed(sh) == []


def test_non_interactive_shell_says_nothing(sh):
    stale(sh)
    assert sh(interactive=False).strip() == ""
    assert observed(sh) == []


# ------------------------------------------------------- fallback to printing

def test_ask_disabled_prints_the_old_reminder(sh):
    stale(sh)
    out = sh(answer="y", AUR_COOLDOWN_NUDGE_ASK="0")
    assert "run aur-cooldown observe" in out
    assert "[Y/n]" not in out
    assert observed(sh) == []


def test_no_prompt_without_a_terminal(sh):
    """Interactive, but stdin is not a tty: print the reminder, never hang."""
    stale(sh)
    out = sh(tty=False)
    assert "run aur-cooldown observe" in out
    assert "[Y/n]" not in out
    assert observed(sh) == []


def test_missing_tool_falls_back_to_print(sh):
    stale(sh)
    out = sh(answer="y", PATH=str(sh.nobin))     # nothing named aur-cooldown
    assert "run aur-cooldown observe" in out
    assert "[Y/n]" not in out
