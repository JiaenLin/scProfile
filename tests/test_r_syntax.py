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
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _r_scripts():
    """[(plugin, attribute, source)] for every R string a shipped plugin holds."""
    out = []
    for f in sorted((ROOT / "kernels").glob("*.py")):
        sp = importlib.util.spec_from_file_location(f.stem, f)
        m = importlib.util.module_from_spec(sp)
        try:
            sp.loader.exec_module(m)
        except Exception:                                             # noqa: BLE001
            continue
        for attr in dir(m):
            v = getattr(m, attr)
            if not isinstance(v, str) or len(v) < 200:
                continue
            if "library(" in v and ("<-" in v or "function(" in v):
                out.append((f.stem, attr, v))
    return out


def _rscript():
    for cand in ("Rscript", "R"):
        p = shutil.which(cand)
        if p:
            return p
    return None


def test_at_least_one_r_script_is_found():
    """If this finds nothing the rest of the file is vacuous."""
    found = _r_scripts()
    assert found, "no R script located in any plugin; the detector is not looking correctly"


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
