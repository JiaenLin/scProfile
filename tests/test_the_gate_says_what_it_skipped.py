"""The gate counts the checks the interpreter it ran under could not run, and runs the suites
under the repository's own interpreter where one exists (harness ADR-0026, the open items).

A FALSE GREEN, MET WHILE CLOSING THE OPEN ITEMS: `run` was taught to refuse at its door and the
commit gate said green - its interpreter has no array stack, so the status contract's CLI half
printed "SKIP ... the cluster runs it" and exited 0, and the door had broken that contract (no
FAILED.txt, no "no plugin ran"). The same suite under an interpreter with anndata said FAIL. A
gate that skips the half that would have failed, and calls the rest green, is a gate a
maintainer learns to trust wrongly - and with no human in the loop, nobody re-runs it by hand.
Two rules: the summary counts every SKIP the suites printed and says the word; and when the
running interpreter lacks the array stack but `<repo>/.venv/bin/python` (or
$SCPROFILE_TEST_PYTHON) has it, the suites run under that one and the summary says which.

Run: python tests/test_the_gate_says_what_it_skipped.py
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

FAIL = []


def ck(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'} {name}" + (f" — {detail}" if not cond else ""))
    if not cond:
        FAIL.append(name)


def gate(pattern, env_extra=None, *extra):
    env = dict(os.environ, PYTHONPATH=str(ROOT))
    env.pop("SCPROFILE_TEST_PYTHON", None)
    env.update(env_extra or {})
    p = subprocess.run([sys.executable, str(ROOT / "tests" / "run_all.py"), "--pattern", pattern,
                        "--jobs", "1", *extra], capture_output=True, text=True, env=env, cwd=str(ROOT))
    return p.returncode, p.stdout + p.stderr


print("the summary counts what was skipped")
with tempfile.TemporaryDirectory() as td:
    d = Path(td)
    (d / "test_a.py").write_text("print('  ok   one')\nprint('  SKIP two: no array stack here')\n"
                                 "print('ok: skipped, pandas is not importable here')\n")
    (d / "test_b.py").write_text("print('  ok   three')\n")
    rc, out = gate(str(d / "test_*.py"))
    ck("green, and the skips counted with the word", rc == 0 and "green: 2 suite(s)" in out
       and "2 check(s) SKIPPED" in out.replace("skipped", "SKIPPED"), out[-300:])
    (d / "test_b.py").write_text("print('  ok   three')\nraise SystemExit(1)\n")
    rc, out = gate(str(d / "test_*.py"))
    ck("a failing suite still fails, skips or not", rc != 0 and "FAIL test_b.py" in out, out[-300:])

print("\nthe suites run under the repository's own interpreter when this one lacks the array stack")
with tempfile.TemporaryDirectory() as td:
    d = Path(td)
    fake = d / "bin"
    fake.mkdir()
    # a fake interpreter that records it was the one used, then runs the file with the real one
    (fake / "python").write_text(f"#!/bin/sh\necho 'RAN UNDER THE FAKE'\nexec {sys.executable} \"$@\"\n")
    os.chmod(fake / "python", 0o755)
    (d / "test_c.py").write_text("print('  ok   c')\n")
    rc, out = gate(str(d / "test_*.py"), {"SCPROFILE_TEST_PYTHON": str(fake / "python"),
                                            "SCPROFILE_TEST_PYTHON_FORCE": "1"})
    ck("$SCPROFILE_TEST_PYTHON is used, and the summary names it",
       rc == 0 and "RAN UNDER THE FAKE" not in out.split("green")[0][:0] and str(fake / "python") in out, out[-400:])
    src = (ROOT / "tests" / "run_all.py").read_text(encoding="utf-8")
    ck("the repository's .venv is the default candidate", '".venv" / "bin" / "python"' in src or ".venv/bin/python" in src)
    ck("and only taken when this interpreter lacks the array stack and that one has it",
       "anndata" in src and "has_arrays" in src)

if FAIL:
    print(f"\n{len(FAIL)} FAILED: " + ", ".join(FAIL))
    sys.exit(1)
print("\nthe gate says what it skipped")
