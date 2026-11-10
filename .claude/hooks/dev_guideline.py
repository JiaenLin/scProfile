#!/usr/bin/env python3
"""The development guideline: a gate at the door of `main`, and reminders for the session.

TWO AXES, TWO TRIGGERS, ONE FILE.

  THE GATE.     What may land on `main`: nothing while a suite is red, nothing while `scprofile
                check` is red, no figure code while `check --deep` is red. Run by git from the
                committed `setup/githooks` (installed once per clone by `git config core.hooksPath
                setup/githooks`): `pre-push` for a push to refs/heads/main (`--pre-push`), and
                `pre-commit` for a commit made on `main` itself (`--pre-commit`). A commit on any
                other branch meets no gate, so a half-converted plugin can be checkpointed while it
                is red (harness B1-092): a green suite is what a change needs when it is ACCEPTED,
                and it is accepted at `main`. The push is the door because a fast-forward merge
                runs no pre-commit hook.

  THE SESSION.  Where an agent puts things while it works: a Claude Code `PreToolUse` hook (JSON on
                stdin). It REMINDS and never denies (harness B1-018, B1-019, B1-022, B1-070). The
                denials it used to make stopped a one-line measurement, a clone in a scratch
                directory and the plugin maker's own code, and no rule asked for any of them.

WHY THE GATE IS A GIT HOOK, MEASURED. All the rules were once a `PreToolUse` hook, which Claude
Code loads from the directory a session was STARTED in, so a session rooted in another repository
committed here past every rule. A git hook fires in THIS repository whatever ran it.

THE ESCAPE, RECORDED HERE BECAUSE NOTHING RECORDS IT. `git push --no-verify` skips the gate and
leaves no trace. It is written down where the gate is.

What is NOT enforced, and cannot be: whether anybody LOOKED at a figure. No hook can see eyes on a
picture. `scprofile review` records it, and the reminder is printed whenever the gate passes
figure code.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

FIGURE_CODE = ("figure.py", "design_panel.py", "compare_panel.py", "network_panels.py",
               "panels.py", "report.py")

#: The one ref the gate guards, and git's name for "no object" in a pre-push line.
MAIN = "refs/heads/main"
ZERO = "0" * 40


def deny(msg, code=1):
    """Refuse, and say why. git takes any non-zero."""
    print(f"BLOCKED by DEVELOPMENT.md\n\n{msg}\n", file=sys.stderr)
    return code


def remind(msg):
    """Say it, refuse nothing: a PreToolUse hook that exits 0 lets the call through."""
    print(f"DEVELOPMENT.md (a reminder; nothing is refused): {msg}", file=sys.stderr)
    return 0


def run(cmd, **kw):
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=900, **kw)


# -----------------------------------------------------------------------------------------------
# THE SESSION AXIS - reminders only
# -----------------------------------------------------------------------------------------------

def session(ev):
    """Two reminders, and every path returns 0."""
    tool = ev.get("tool_name")
    ti = ev.get("tool_input") or {}
    if tool in ("Write", "Edit", "NotebookEdit"):
        p = str(ti.get("file_path") or "")
        body = str(ti.get("content") or ti.get("new_string") or "")
        if p.endswith(".py") and not p.startswith(str(ROOT)) and "scprofile" in body:
            return remind(
                f"{p} is a .py outside this repository that uses scprofile. If it is part of the "
                "tool, it belongs in scprofile/ or tests/, where a run and the suite reach it.")
        return 0
    if tool == "Bash":
        cmd = str(ti.get("command") or "")
        if (("import scprofile" in cmd or "from scprofile" in cmd)
                and ("<<" in cmd or " -c " in cmd) and "-m scprofile.cli" not in cmd):
            return remind(
                "scProfile code run from the shell. A measurement is fine; a script you will "
                "need again belongs in tests/ - `python tests/preview_panels.py --out <RUNDIR>` "
                "redraws panels from a finished run.")
    return 0


# -----------------------------------------------------------------------------------------------
# THE GATE
# -----------------------------------------------------------------------------------------------

def pre_commit():
    """A commit made ON `main` meets the gate, against what is staged; any other branch, none."""
    head = run(["git", "symbolic-ref", "-q", "HEAD"])
    if (head.stdout or "").strip() != MAIN:
        return 0
    return gate(run(["git", "diff", "--cached", "--name-only"]).stdout or "")


def pre_push(lines):
    """A push to refs/heads/main meets the gate; a push of any other ref meets none.

    git hands one line per ref on stdin: `<local ref> <local sha> <remote ref> <remote sha>`. The
    suites and `check` run on this checkout, which is what can run; the figure-code rule reads what
    the push carries. A remote `main` this clone has no object for, or none at all, counts as
    figure code touched, so the behavioural checks run rather than being skipped on a guess.
    """
    to_main = [f for f in (l.split() for l in lines)
               if len(f) == 4 and f[2] == MAIN and f[1] != ZERO]
    if not to_main:
        return 0
    touched = []
    for _lref, lsha, _rref, rsha in to_main:
        d = run(["git", "diff", "--name-only", rsha, lsha]) if rsha != ZERO else None
        touched.append(d.stdout if d is not None and d.returncode == 0 else "kernels/")
    return gate("\n".join(touched))


def gate(touched):
    """Rules 2, 3, 4. Non-zero refuses."""
    # 2. every suite must pass - BY THE ONE RUNNER, not a loop that looks like it. DEVELOPMENT.md
    #    says "the gate is `python tests/run_all.py`, and nothing else", and this step was a
    #    second loop over the same files that did not set PYTHONPATH the way the runner does. The
    #    first time the gate was made to run for real it refused on seven suites the runner
    #    passes - the suites were fine and the copy of the runner was not.
    r = run([sys.executable, str(ROOT / "tests" / "run_all.py"), "--jobs", "4"])
    if r.returncode != 0:
        tail = "\n".join(((r.stdout or "") + (r.stderr or "")).strip().splitlines()[-12:])
        return deny("Suites are RED (`python tests/run_all.py`):\n" + tail +
                    "\nEvery check must be able to fail, and these are failing. Fix them first.")

    # 3. the tool's own check must be green
    env = {**os.environ, "PYTHONPATH": str(ROOT)}
    c = run([sys.executable, "-m", "scprofile.cli", "check"], env=env)
    if c.returncode != 0:
        red = [l for l in (c.stdout or "").splitlines() if l.strip().startswith("RED")]
        return deny("`scprofile check` is RED:\n" + "\n".join(red[:6]))

    # 4. figure code demands the behavioural checks
    if any(f in touched for f in FIGURE_CODE) or "kernels/" in touched:
        d = run([sys.executable, "-m", "scprofile.cli", "check", "--deep"], env=env)
        if d.returncode != 0:
            red = [l for l in (d.stdout or "").splitlines() if l.strip().startswith("RED")]
            return deny("Figure code changed and `check --deep` is RED:\n" + "\n".join(red[:6]))
        print("DEVELOPMENT.md: figure code changed. A green suite is not a look — open the "
              "figures this changes and record them with `scprofile review`.", file=sys.stderr)
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--pre-commit" in argv:
        return pre_commit()
    if "--pre-push" in argv:
        return pre_push(sys.stdin.read().splitlines())
    try:
        ev = json.load(sys.stdin)
    except Exception:
        return 0
    return session(ev)


if __name__ == "__main__":
    sys.exit(main())
