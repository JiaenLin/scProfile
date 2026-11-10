"""The gate guards `main`, not work in progress; the session hook reminds and refuses nothing.

THE GATE (harness B1-092). Every commit, a work-in-progress commit on an autodev/* branch
included, ran the whole suite and was refused while anything was red, so a half-converted plugin
could not be checkpointed - while a fast-forward merge into `main` ran no hook at all. The gate
now runs on a push to refs/heads/main and on a commit made on `main`; anywhere else, nothing.

THE SESSION (harness B1-018, B1-019, B1-022, B1-070). The hook denied a scratch-directory write
naming scprofile (a clone that lives in one included), a one-line `python -c "import scprofile"`,
every `git commit` in a clone without core.hooksPath, and any .py outside the repository naming
scprofile (the plugin maker's own code). Each is now let through, with at most a reminder.

Asked of the real hook and of real git, in a clone whose suite is one file, pushing to a bare
repository in a temporary directory, so the gate is watched refusing and passing in seconds.

Run: python tests/test_the_gate_guards_main_not_work_in_progress.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAIL = []
# git here asks about the repository it names, whatever hook environment ran this suite; and
# `python3` in the hooks is this interpreter, which has what `scprofile check` imports.
ENV = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
ENV["PATH"] = str(Path(sys.executable).parent) + os.pathsep + ENV.get("PATH", "")
ENV.pop("SCPROFILE_KERNELS", None)


def ck(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'} {name}" + (f" — {detail}" if not cond else ""))
    if not cond:
        FAIL.append(name)


def git(repo, *args):
    r = subprocess.run(["git", "-C", str(repo), *args], env=ENV, capture_output=True, text=True,
                       timeout=600)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def hook(clone, payload):
    r = subprocess.run([sys.executable, str(clone / ".claude" / "hooks" / "dev_guideline.py")],
                       input=json.dumps(payload), env=ENV, capture_output=True, text=True,
                       timeout=120, cwd=str(clone))
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def suite(clone, code):
    """The clone's whole suite: one file that exits `code`."""
    (clone / "tests" / "test_one.py").write_text(
        f"import sys\nprint('  {'ok  ' if code == 0 else 'FAIL'} the one check')\n"
        f"sys.exit({code})\n", encoding="utf-8")


td = Path(tempfile.mkdtemp(prefix="w023-gate-"))
try:
    work, bare = td / "work", td / "origin.git"
    subprocess.run(["git", "clone", "-q", "--no-local", str(ROOT), str(work)], check=True,
                   env=ENV, capture_output=True)
    for d in (".claude", "setup", "scprofile"):
        shutil.copytree(ROOT / d, work / d, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("__pycache__"))
    for t in (work / "tests").glob("test_*.py"):
        t.unlink()
    suite(work, 0)
    git(work, "config", "user.name", "gate test")
    git(work, "config", "user.email", "gate.test@invalid")
    git(work, "checkout", "-q", "-B", "main")
    git(work, "add", "-A")
    git(work, "commit", "-q", "-m", "this tree's hook, and a one-file suite")
    subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True, env=ENV,
                   capture_output=True)
    git(work, "remote", "set-url", "origin", str(bare))
    rc, out = git(work, "push", "-q", "origin", "main")
    ck("the bare repository holds main before the gate is installed", rc == 0, out[-300:])

    print("\nthe session hook, in a clone with no core.hooksPath")
    for what, payload in (
            ("a scratch-directory write naming scprofile (B1-018)",
             {"tool_name": "Write", "tool_input": {"file_path": "/private/tmp/s/n.md",
                                                   "content": "scprofile"}}),
            ("a write into this clone, which lives in a temporary directory (B1-018)",
             {"tool_name": "Write", "tool_input": {"file_path": str(work / "docs" / "n.md"),
                                                   "content": "scprofile"}}),
            ("`git commit` (B1-019)",
             {"tool_name": "Bash", "tool_input": {"command": "git commit -m x"}}),
            ("a one-line `python3 -c \"import scprofile\"` (B1-022)",
             {"tool_name": "Bash", "tool_input": {"command": 'python3 -c "import scprofile"'}}),
            ("a .py outside the repository naming scprofile (B1-070)",
             {"tool_name": "Write", "tool_input": {
                 "file_path": str(td / "single-cell-harness" / "sch" / "dev" / "y.py"),
                 "content": "import scprofile\n"}})):
        rc, out = hook(work, payload)
        ck(f"{what}: exit 0", rc == 0, f"exit {rc}: {out.strip()[:200]}")
    rc, out = hook(work, {"tool_name": "Bash",
                          "tool_input": {"command": 'python3 -c "import scprofile"'}})
    ck("and the measurement gets its reminder, on stderr", "reminder" in out, out[:200])

    print("\nthe gate, installed")
    git(work, "config", "core.hooksPath", "setup/githooks")
    git(work, "checkout", "-q", "-b", "autodev/test")
    suite(work, 1)
    rc, out = git(work, "commit", "-q", "-am", "work in progress, red")
    ck("a commit on a red autodev branch succeeds", rc == 0, out[-300:])
    rc, out = git(work, "push", "-q", "origin", "HEAD:refs/heads/autodev/test")
    ck("and so does pushing that branch", rc == 0, out[-300:])
    rc, out = git(work, "push", "-q", "origin", "HEAD:main")
    ck("pushing it to main is refused, because the suite is red",
       rc != 0 and "Suites are RED" in out, f"exit {rc}: {out[-300:]}")
    rc, remote_main = git(bare, "rev-parse", "main")
    rc2, local = git(work, "rev-parse", "HEAD")
    ck("and main did not move", remote_main.strip() != local.strip())

    suite(work, 0)
    git(work, "commit", "-q", "-am", "green again")
    rc, out = git(work, "push", "-q", "origin", "HEAD:main")
    ck("green, the same push to main is let through", rc == 0, f"exit {rc}: {out[-400:]}")

    git(work, "checkout", "-q", "main")
    git(work, "reset", "-q", "--hard", "autodev/test")
    suite(work, 1)
    rc, out = git(work, "commit", "-q", "-am", "red, on main itself")
    ck("a commit made on main meets the gate: red is refused",
       rc != 0 and "Suites are RED" in out, f"exit {rc}: {out[-300:]}")
finally:
    shutil.rmtree(td, ignore_errors=True)

print("\n" + ("the gate guards main, and the session is not refused"
              if not FAIL else f"{len(FAIL)} FAILED: {FAIL}"))
sys.exit(1 if FAIL else 0)
