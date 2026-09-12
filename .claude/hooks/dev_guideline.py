#!/usr/bin/env python3
"""The development guideline, ENFORCED. It denies; it does not remind.

A guideline that prints is advice, and advice is what gets skipped under time pressure. Every
rule below is one that was written down here and then broken by the person who wrote it, so the
enforcement is mechanical: a refused call goes back to the caller with the reason.

TWO AXES, TWO TRIGGERS, ONE FILE. The rules are about two different things and are fired by two
different mechanisms, and keeping them in one file is what stops the two drifting apart:

  THE SESSION.  Rules 1, 1b and 1c are about where an agent puts things while it works - a .py in
                a scratchpad, scProfile material outside the repository, ad-hoc scProfile code in
                a heredoc. They fire as a Claude Code `PreToolUse` hook (JSON on stdin), because
                the session is where those things happen.

  THE COMMIT.   Rules 2, 3 and 4 are about what may land in THIS REPOSITORY - no commit while a
                suite is red, none while `scprofile check` is red, no figure code without
                `check --deep`. They fire as a git `pre-commit` hook (`--pre-commit`, no stdin),
                installed by `git config core.hooksPath setup/githooks`, because a commit is a
                property of the repository and not of the session that made it.

WHY THE SPLIT, MEASURED. All five rules were a `PreToolUse` hook, which Claude Code loads from
the directory a session was STARTED in. A session rooted in the plugin maker's repository edits
this one through the maker - which is the round's own rule - and its commits met no gate:
figure code was committed with `check --deep` run afterwards, and two of the commands rule 1c
denies were run. The rules were right and the trigger was keyed to the wrong axis. The commit
rules now fire on `git commit` here whatever ran it; the session rules keep firing where the
session is.

The session hook still has one thing to say about commits: it refuses one while the git gate is
NOT INSTALLED in this clone, and prints the command that installs it. `core.hooksPath` is
per-clone configuration and cannot be committed, so a fresh clone is gated by nothing until
somebody runs that command once - and the moment that matters is the first commit.

THE ESCAPE, RECORDED HERE BECAUSE NOTHING RECORDS IT. `git commit --no-verify` skips the gate and
leaves no trace, where a session hook's refusal was at least visible in the transcript. This
project holds that a gate whose escapes are all recorded is a gate that stays on, and this one
falls short of that standard; it is written down where the gate is, which is less.

What is NOT enforced, and cannot be: whether anybody LOOKED at a figure. No hook can see eyes on
a picture. `scprofile review` records it and the reminder is printed on every figure-code commit,
so the number is in front of whoever is committing.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

FIGURE_CODE = ("figure.py", "design_panel.py", "compare_panel.py", "network_panels.py",
               "panels.py", "report.py")


def deny(msg, code=2):
    """Refuse, and say why. 2 is what a PreToolUse hook returns to block; git takes any non-zero."""
    print(f"BLOCKED by DEVELOPMENT.md\n\n{msg}\n", file=sys.stderr)
    return code


def run(cmd, **kw):
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=900, **kw)


#: Path fragments that mean "this will not survive". Not an exhaustive list of temp dirs - the
#: ones an agent is actually handed.
SCRATCH = ("/scratchpad", "/tmp/", "/var/folders/", "/private/tmp/", "/.cache/")

#: Suffixes whose content is prose or code rather than data. A pulled PNG is a VIEW of a run and
#: is not development material; a .md draft of scProfile's own documentation is.
TEXTY = (".md", ".py", ".txt", ".rst", ".json", ".yml", ".yaml", ".toml", ".sh", ".cfg")


def _is_scratch(path):
    p = str(path).replace("\\", "/")
    return any(frag in p for frag in SCRATCH)


def _texty(path):
    return str(path).lower().endswith(TEXTY)


# -----------------------------------------------------------------------------------------------
# THE SESSION AXIS
# -----------------------------------------------------------------------------------------------

def session(ev):
    """Rules 1, 1b, 1c - and the one thing the session says about a commit."""
    tool = ev.get("tool_name")
    ti = ev.get("tool_input") or {}

    # 1. tool code written outside the package
    if tool in ("Write", "Edit", "NotebookEdit"):
        p = str(ti.get("file_path") or "")
        body = str(ti.get("content") or ti.get("new_string") or "")
        if p.endswith(".py") and not p.startswith(str(ROOT)) and "scprofile" in body:
            return deny(
                f"{p} is a .py outside the repository that uses scprofile.\n"
                "Ship it in the tool, or it does not exist. Put it in scprofile/ or tests/, "
                "where a run and the suite can reach it.")
        # 1b. SCPROFILE MATERIAL IN A SCRATCHPAD. The repository is the only home; a run
        #     directory is the only other place scProfile output belongs. A scratchpad is
        #     neither - it has no commit, no history, and it is gone with the session.
        #
        #     SCOPED TO SCRATCH PATHS ON PURPOSE. A project's own RUNLOG legitimately names
        #     scprofile and lives outside this repository, and denying that would be a gate
        #     firing on correct behaviour - which this project has learned gets a gate switched
        #     off. What is denied is the location that cannot keep anything.
        if _is_scratch(p) and "scprofile" in body.lower() and _texty(p):
            return deny(
                f"{p} is in a scratchpad and names scProfile.\n"
                "THE REPOSITORY IS THE ONLY HOME. Development material - docs, examples, "
                "harnesses, drafts - goes in the repo and is committed. A written RESULT goes "
                "in the run it came from:\n"
                "    scprofile paper --out <RUNDIR> --write <file>\n"
                "Four manuscript drafts and every panel-rendering harness were written to a "
                "scratchpad once. None of them survived the session.")
        return 0

    if tool != "Bash":
        return 0

    cmd = str(ti.get("command") or "")
    # 1c. AD-HOC SCPROFILE CODE IN A SHELL HEREDOC. A script that imports scprofile and is
    #     typed into a shell runs once and is gone; the next person needing it rebuilds it from
    #     memory, which is exactly what happened to every panel-rendering harness used while
    #     this figure set was being fixed. Use the CLI, or commit the script.
    #
    #     `python -m scprofile.cli ...` is the CLI and is always fine. So is `python tests/x.py`.
    #     What is denied is `python - <<EOF ... import scprofile ... EOF` and `python -c`.
    if ("scprofile" in cmd
            and ("import scprofile" in cmd or "from scprofile" in cmd)
            and ("<<" in cmd or " -c " in cmd)
            and "-m scprofile.cli" not in cmd):
        return deny(
            "this runs scProfile code from a shell heredoc.\n"
            "USE THE CLI, OR COMMIT THE SCRIPT. A script typed into a shell runs once and is "
            "gone, and the next person who needs it rebuilds it from memory.\n"
            "  - to look at panels from a finished run:  python tests/preview_panels.py --out "
            "<RUNDIR> ...\n"
            "  - to check something once:                scprofile <command> --out <RUNDIR>\n"
            "  - if neither fits, it is a script worth committing: put it in tests/ and run it "
            "from there.")
    if "git commit" not in cmd:
        return 0
    # A COMMIT IS GATED BY GIT, NOT HERE - so what this checks is that git WILL gate it. The
    # rules themselves run in `pre_commit()` below, once, whichever session or terminal commits.
    from scprofile import gate as _G
    ok, why = _G.installed(ROOT)
    if not ok:
        return deny(
            f"the commit gate is not installed in this clone: {why}\n"
            f"The guideline's commit rules run as a git pre-commit hook here, so that a commit "
            f"from ANY session meets them. Install it once:\n"
            f"    {_G.install_command()}\n"
            f"then commit again.")
    return 0


# -----------------------------------------------------------------------------------------------
# THE COMMIT AXIS
# -----------------------------------------------------------------------------------------------

def pre_commit():
    """Rules 2, 3, 4 - against what is STAGED. Non-zero refuses the commit."""
    # 2. every suite must pass - BY THE ONE RUNNER, not a loop that looks like it. DEVELOPMENT.md
    #    says "the gate is `python tests/run_all.py`, and nothing else", and this step was a
    #    second loop over the same files that did not set PYTHONPATH the way the runner does. The
    #    first time the gate was made to run for real it refused on seven suites the runner
    #    passes - the suites were fine and the copy of the runner was not. Two mechanisms for
    #    one question is the defect the guideline names, found in the file that enforces it.
    r = run([sys.executable, str(ROOT / "tests" / "run_all.py"), "--jobs", "4"])
    if r.returncode != 0:
        tail = "\n".join(((r.stdout or "") + (r.stderr or "")).strip().splitlines()[-12:])
        return deny("Suites are RED (`python tests/run_all.py`):\n" + tail +
                    "\nEvery check must be able to fail, and these are failing. Fix them first.",
                    code=1)

    # 3. the tool's own check must be green
    c = run([sys.executable, "-m", "scprofile.cli", "check"],
            env={**__import__("os").environ, "PYTHONPATH": str(ROOT)})
    if c.returncode != 0:
        red = [l for l in (c.stdout or "").splitlines() if l.strip().startswith("RED")]
        return deny("`scprofile check` is RED:\n" + "\n".join(red[:6]), code=1)

    # 4. figure code demands the behavioural checks
    touched = run(["git", "diff", "--cached", "--name-only"]).stdout
    if any(f in touched for f in FIGURE_CODE) or "kernels/" in touched:
        d = run([sys.executable, "-m", "scprofile.cli", "check", "--deep"],
                env={**__import__("os").environ, "PYTHONPATH": str(ROOT)})
        if d.returncode != 0:
            red = [l for l in (d.stdout or "").splitlines() if l.strip().startswith("RED")]
            return deny("Figure code changed and `check --deep` is RED:\n" + "\n".join(red[:6]),
                        code=1)
        print("DEVELOPMENT.md: figure code changed. A green suite is not a look — open the "
              "figures this changes and record them with `scprofile review`.", file=sys.stderr)
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--pre-commit" in argv:
        return pre_commit()
    try:
        ev = json.load(sys.stdin)
    except Exception:
        return 0
    return session(ev)


if __name__ == "__main__":
    sys.exit(main())
