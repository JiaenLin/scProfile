"""A new plugin is admitted by writing its file: nothing else has to be edited or run.

Two things turned a ninth plugin red the moment `scaffold --new` wrote it (harness B1-094,
B1-014):

  THE TABLE. ROADMAP.md's shipped table is rendered from the declarations, and nothing rendered
  it until somebody ran `generated --write` by hand. The scaffold now rewrites it as it writes.

  THE RATCHET. A test pinned the number of wrappers that had not accounted for their upstream's
  figures at eight, "may shrink and may not grow" - and the scaffold's template is such a
  wrapper, so a ninth plugin was red by construction. The validator already refuses a wrapper
  that says neither, so the admission is in the plugin's own file; the count is not a gate.

Asked of the real `scaffold <name> --new`, in a fresh clone carrying this tree's code, with a
name no document can already contain.

Run: python tests/test_a_new_plugin_is_admitted_by_its_file.py
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAIL = []
NAME = "zzprobe"
ENV = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
ENV.pop("SCPROFILE_KERNELS", None)


def ck(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'} {name}" + (f" — {detail}" if not cond else ""))
    if not cond:
        FAIL.append(name)


def run(clone, *argv):
    r = subprocess.run([sys.executable, *argv], cwd=str(clone), env=dict(ENV, PYTHONPATH=str(clone)),
                       capture_output=True, text=True, timeout=600)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


td = Path(tempfile.mkdtemp(prefix="w023-new-"))
try:
    clone = td / "clone"
    subprocess.run(["git", "clone", "-q", "--no-local", str(ROOT), str(clone)], check=True,
                   capture_output=True, env=ENV)
    for d in ("scprofile", "kernels", "tests"):
        shutil.copytree(ROOT / d, clone / d, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("__pycache__"))
    for f in ("ROADMAP.md", "DEVPOINTS.yaml"):
        shutil.copyfile(ROOT / f, clone / f)
    ck("the name is new here", not (clone / "kernels" / f"{NAME}.py").exists()
       and NAME not in (clone / "ROADMAP.md").read_text(encoding="utf-8"))

    print(f"\nscaffold {NAME} --new, and no further command")
    rc, out = run(clone, "-m", "scprofile.cli", "scaffold", NAME, "--new")
    ck("the scaffold writes the plugin", rc == 0 and (clone / "kernels" / f"{NAME}.py").is_file(),
       out[-300:])
    rows = [l for l in (clone / "ROADMAP.md").read_text(encoding="utf-8").splitlines()
            if NAME in l]
    ck("ROADMAP.md names it on exactly one line, its table row",
       len(rows) == 1 and rows[0].startswith(f"| `{NAME}` |"), str(rows))
    rc, out = run(clone, "-m", "scprofile.cli", "generated")
    ck("and every generated block is current", rc == 0, out[-300:])
    rc, out = run(clone, "tests/test_native_plots.py")
    ck("the figure-accounting suite admits the ninth wrapper", rc == 0,
       "; ".join(l.strip()[:160] for l in out.splitlines() if "FAIL" in l) or out[-300:])
finally:
    shutil.rmtree(td, ignore_errors=True)

print("\n" + ("a new plugin is admitted by its file" if not FAIL else f"{len(FAIL)} FAILED: {FAIL}"))
sys.exit(1 if FAIL else 0)
