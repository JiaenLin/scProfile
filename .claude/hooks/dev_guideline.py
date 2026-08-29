#!/usr/bin/env python3
"""PreToolUse hook that ENFORCES DEVELOPMENT.md. It denies; it does not remind.

A guideline that prints is advice, and advice is what gets skipped under time pressure. Every
rule below is one that was written down here and then broken by the person who wrote it, so the
enforcement is mechanical: exit 2 blocks the call and the reason goes back to the caller.

WHAT IS ENFORCED, and why each is mechanically checkable:

  1. NO TOOL CODE IN A SCRATCHPAD. Writing a .py outside the repo that imports scprofile is
     building the thing somewhere a run can never reach it. Put it in the package.
  2. NO COMMIT WHILE THE SUITES ARE RED. "Commit only when green" was stated and then broken by
     a command that chained `git commit` after a loop that merely printed PASS/FAIL.
  3. NO COMMIT WHILE `scprofile check` IS RED.
  4. NO COMMIT OF FIGURE CODE WITHOUT `check --deep` PASSING. Behaviour, not source greps.

What is NOT enforced, and cannot be: whether anybody LOOKED at a figure. No hook can see eyes on
a picture. `scprofile review` records it and the count is printed here on every figure-code
commit, so the number is in front of whoever is committing.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIGURE_CODE = ("figure.py", "design_panel.py", "compare_panel.py", "network_panels.py",
               "panels.py", "report.py")


def deny(msg):
    print(f"BLOCKED by DEVELOPMENT.md\n\n{msg}\n", file=sys.stderr)
    return 2


def run(cmd, **kw):
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=900, **kw)


def main():
    try:
        ev = json.load(sys.stdin)
    except Exception:
        return 0
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
        return 0

    if tool != "Bash":
        return 0
    cmd = str(ti.get("command") or "")
    if "git commit" not in cmd or str(ROOT) not in cmd and "scProfile" not in cmd:
        # a commit elsewhere is not ours to police
        if "git commit" not in cmd:
            return 0

    # 2. every suite must pass
    failed = [t.name for t in sorted((ROOT / "tests").glob("test_*.py"))
              if run([sys.executable, str(t)]).returncode != 0]
    if failed:
        return deny("Suites are RED: " + ", ".join(failed) +
                    "\nEvery check must be able to fail, and these are failing. Fix them first.")

    # 3. the tool's own check must be green
    c = run([sys.executable, "-m", "scprofile.cli", "check"],
            env={**__import__("os").environ, "PYTHONPATH": str(ROOT)})
    if c.returncode != 0:
        red = [l for l in (c.stdout or "").splitlines() if l.strip().startswith("RED")]
        return deny("`scprofile check` is RED:\n" + "\n".join(red[:6]))

    # 4. figure code demands the behavioural checks
    touched = run(["git", "diff", "--cached", "--name-only"]).stdout
    if any(f in touched for f in FIGURE_CODE) or "kernels/" in touched:
        d = run([sys.executable, "-m", "scprofile.cli", "check", "--deep"],
                env={**__import__("os").environ, "PYTHONPATH": str(ROOT)})
        if d.returncode != 0:
            red = [l for l in (d.stdout or "").splitlines() if l.strip().startswith("RED")]
            return deny("Figure code changed and `check --deep` is RED:\n" + "\n".join(red[:6]))
        print("DEVELOPMENT.md: figure code changed. A green suite is not a look — open the "
              "figures this changes and record them with `scprofile review`.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
