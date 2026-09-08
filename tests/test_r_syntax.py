"""Every R script a plugin ships must PARSE, checked with R where R exists.

A plugin's R is a string in a Python file, so Python's own syntax check says nothing about it.
The failure mode is expensive and late: the job is scheduled, the environment is resolved, the
matrix is written, and the script dies on the first line R reads.

Where no R is installed - a maintainer's workstation - the check SAYS it was skipped rather than
passing silently, because seven suites green on a machine that cannot parse R is a weaker
statement than it looks.
"""
import importlib.util
import shutil
import subprocess
import tempfile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

import subject                                                            # noqa: E402


def _r_scripts():
    """[(plugin, attribute, source)] for every R string a shipped plugin holds.

    ONE DETECTOR, in tests/subject.py, because four suites had a copy of it and a fifth kind of
    R string would have had to be taught to all four.
    """
    return subject.r_scripts()

def _rscript():
    for cand in ("Rscript", "R"):
        p = shutil.which(cand)
        if p:
            return p
    return None


def test_the_detector_finds_the_r_that_is_here():
    """If this finds nothing the rest of the file is vacuous - but vacuous is not always wrong.

    This asserted `found`, and printed "the detector is not looking correctly" on a tree whose
    only R plugin had been deleted. It was right that the suite proved nothing and wrong about
    why, which is the reading that sends somebody to debug a detector that works.
    """
    found = _r_scripts()
    if found:
        return
    assert not subject.any_kernel_embeds_r(), (
        "a kernel file contains `library(` and the detector found no R script in it, so the "
        "detector has stopped matching and every check below is vacuously green")
    print("no plugin here embeds R, so there is nothing to parse. Not a defect - this runs "
          "again the day an R plugin arrives")


def test_every_r_script_parses():
    rs = _rscript()
    scripts = _r_scripts()
    if not rs:
        print(f"  SKIP r-syntax: no Rscript on this machine "
              f"({len(scripts)} script(s) left unchecked)")
        return
    bad = []
    for plug, attr, src in scripts:
        with tempfile.NamedTemporaryFile("w", suffix=".R", delete=False) as fh:
            fh.write(src)
            path = fh.name
        p = subprocess.run(
            [rs, "-e", f'tryCatch({{parse("{path}"); cat("ok")}}, '
                       f'error=function(e) cat("ERR:", conditionMessage(e)))'],
            capture_output=True, text=True)
        if "ok" not in p.stdout:
            bad.append(f"{plug}.{attr}: {(p.stdout + p.stderr).strip()[:200]}")
    assert not bad, bad


if __name__ == "__main__":
    import sys
    bad = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  ok   {name}")
            except AssertionError as e:
                bad += 1
                print(f"  FAIL {name}: {str(e)[:200]}")
    sys.exit(1 if bad else 0)
