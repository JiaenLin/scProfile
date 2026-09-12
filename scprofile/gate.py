"""Where the commit gate lives, and whether this checkout has it installed.

ONE DEFINITION, READ BY THREE PARTIES. The development-guideline hook (`.claude/hooks/
dev_guideline.py`) runs the gate; `scprofile check` reports whether it is installed; the
session hook refuses a commit while it is not. Each of those used to be the place a path like
this would be typed, and a path typed three times is a path that drifts once.

WHY THE GATE IS A GIT HOOK AND NOT ONLY A SESSION HOOK. The guideline's commit rules - no
commit while a suite is red, none while `scprofile check` is red, no figure code without
`check --deep` - were enforced by a `PreToolUse` hook that Claude Code loads from the directory
a session was STARTED in. That keys the gate to the session, and the thing it guards is the
repository: a session rooted in the harness that edits `kernels/cellchat.py` through the plugin
maker makes exactly the same commit and met no gate at all. Measured: one such session committed
figure code, then ran `check --deep` afterwards, and used two commands the hook denies. A git
hook fires on `git commit` in THIS repository whatever ran it, which is the axis the rule is
actually about.

`core.hooksPath` is per-clone configuration and cannot be committed, so a fresh clone is not
gated until `install_command()` has been run once. That is why this module exists: three places
say so, and one command fixes it.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

#: The committed directory git is pointed at. Relative to the repository root, which is how
#: `git config core.hooksPath` resolves a relative value.
HOOKS_PATH = "setup/githooks"

#: The hook git runs before a commit. Two lines of shell that exec the guideline with
#: `--pre-commit`, so the rules exist once.
PRE_COMMIT = "pre-commit"


def root_of(start=None):
    """The repository root above `start`, or None when this is not a git checkout."""
    p = Path(start or __file__).resolve()
    for cand in (p, *p.parents):
        if (cand / ".git").exists():
            return cand
    return None


def configured(root):
    """What `core.hooksPath` says in this checkout - '' when unset or not a git checkout."""
    try:
        r = subprocess.run(["git", "config", "--get", "core.hooksPath"], cwd=str(root),
                           capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return ""
    return (r.stdout or "").strip() if r.returncode == 0 else ""


def installed(root=None):
    """(ok, why). True when git will run the committed hook before a commit here.

    Accepts the relative form and the absolute form of the same directory: git accepts both, and
    a check that refused one spelling of the right answer would be a gate firing on correct
    behaviour - which this project has learned gets a gate switched off.
    """
    root = Path(root or root_of() or ".").resolve()
    if not (root / ".git").exists():
        return False, f"{root} is not a git checkout, so nothing fires on commit here"
    hook = root / HOOKS_PATH / PRE_COMMIT
    if not hook.is_file():
        return False, f"{HOOKS_PATH}/{PRE_COMMIT} is not in the repository"
    got = configured(root)
    if not got:
        return False, f"core.hooksPath is unset; run `{install_command()}`"
    want = (root / HOOKS_PATH).resolve()
    have = (root / got).resolve() if not Path(got).is_absolute() else Path(got).resolve()
    if have != want:
        return False, (f"core.hooksPath is {got!r}, not {HOOKS_PATH!r}; run "
                       f"`{install_command()}`")
    return True, f"core.hooksPath = {got}"


def install_command():
    """The one command that installs the gate in a clone. Printed wherever it is found absent."""
    return f"git config core.hooksPath {HOOKS_PATH}"
