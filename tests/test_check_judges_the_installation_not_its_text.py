"""`scprofile check` judges the installation, not the clone's git settings or the source's spelling.

Two ways it failed on correct code, both measured (harness B1-017, B1-024):

  A FRESH CLONE WAS RED. The row "the commit gate is installed in this clone" reads a per-clone
  git setting that cannot be committed, so `check` exited non-zero on every fresh clone, cluster
  checkout and pip install. It is now a warning: printed, with the command, and not counted red.

  A RENAME WAS RED. Twenty-one rows passed only while four modules contained exact strings, so
  renaming a private function in report.py turned one red with nothing broken; and the rows
  that read cli.py found their own literal in cli.py, so they could not fail at all.

Both asked of the real `check`, in a fresh clone that carries this tree's code.

Run: python tests/test_check_judges_the_installation_not_its_text.py
"""
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAIL = []
# a git run here asks about the clone it names, whatever hook environment ran this suite
GITENV = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


def ck(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'} {name}" + (f" — {detail}" if not cond else ""))
    if not cond:
        FAIL.append(name)


def rename(f, old, new):
    """Rename the NAME token `old` in file `f`; strings and comments are left as they are."""
    src = f.read_text(encoding="utf-8")
    lines = src.splitlines(keepends=True)
    hits = [t.start for t in tokenize.generate_tokens(io.StringIO(src).readline)
            if t.type == tokenize.NAME and t.string == old]
    for r, c in sorted(hits, reverse=True):
        lines[r - 1] = lines[r - 1][:c] + new + lines[r - 1][c + len(old):]
    f.write_text("".join(lines), encoding="utf-8")
    return len(hits)


def check(clone):
    env = dict(GITENV, PYTHONPATH=str(clone))
    env.pop("SCPROFILE_KERNELS", None)
    r = subprocess.run([sys.executable, "-m", "scprofile.cli", "check"], cwd=str(clone),
                       env=env, capture_output=True, text=True, timeout=600)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


td = Path(tempfile.mkdtemp(prefix="w023-check-"))
try:
    clone = td / "clone"
    subprocess.run(["git", "clone", "-q", "--no-local", str(ROOT), str(clone)], check=True,
                   capture_output=True, env=GITENV)
    for d in ("scprofile", "kernels", "setup"):
        shutil.copytree(ROOT / d, clone / d, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("__pycache__"))
    hp = subprocess.run(["git", "-C", str(clone), "config", "--get", "core.hooksPath"],
                        capture_output=True, text=True, env=GITENV).stdout.strip()

    print("a fresh clone, no core.hooksPath")
    ck("the clone really has no hooks path", hp == "", hp)
    rc, out = check(clone)
    gate = [l for l in out.splitlines() if "commit gate is installed" in l]
    ck("`check` exits 0", rc == 0, f"exit {rc}: " + " | ".join(
        l.strip()[:120] for l in out.splitlines() if l.strip().startswith("RED")))
    ck("and names the gate as a warning, with the command",
       bool(gate) and gate[0].strip().startswith("WARN") and "core.hooksPath" in gate[0],
       gate[0] if gate else "no gate row")
    ck("and the summary counts it apart from red", re.search(r"\b0 red, 1 warning", out)
       is not None, out.strip().splitlines()[-1] if out.strip() else "")

    print("\nthe same clone, two names renamed the way a refactor renames them")
    # BY TOKEN, NOT BY TEXT: a refactor renames the name and leaves strings alone. A text
    # replace also rewrites a row's own literal, and a row that reads cli.py for "_UN.resolve("
    # then finds it in itself - those rows could never fail, and the report.py one could.
    n = (rename(clone / "scprofile" / "cli.py", "_UN", "_units")
         + rename(clone / "scprofile" / "report.py", "_arm_content", "_arm_panels"))
    ck("both renames found their names", n >= 2, f"{n} renamed")
    rc, out = check(clone)
    ck("`check` still exits 0", rc == 0, " | ".join(
        l.strip()[:120] for l in out.splitlines() if l.strip().startswith("RED")))
    ck("and every command still answers", "GREEN  the CLI answers for its commands" in out)
finally:
    shutil.rmtree(td, ignore_errors=True)

print("\n" + ("check judges the installation" if not FAIL else f"{len(FAIL)} FAILED: {FAIL}"))
sys.exit(1 if FAIL else 0)
