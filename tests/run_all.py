"""The gate: run every suite the way the job template runs it, and return non-zero if any fails.

WHY THIS EXISTS AS A FILE. I had been gating with a shell one-liner that IMPORTED each test
module and called its `test_*` functions. That was the wrong mechanism twice over:

  - these suites are SCRIPTS. Several call `sys.exit()` at module scope, and `test_contract`
    takes pytest fixtures. Importing them runs them, or fails on a signature.
  - `SystemExit` inherits from BaseException, so it escaped the runner's `except` and terminated
    it WITH CODE 0. The gate reported success by dying quietly, and every file sorted after
    `test_reuse_ablation` was never run at all.

`setup/dev_cycle.pbs` step 0 already had it right - one subprocess per file, exit code decides.
This is that, callable from a workstation, so the gate a change is checked against and the gate
the cluster runs are the same gate.

WHY `--jobs` EXISTS, AND WHY IT DEFAULTS TO 4 NOW

One subprocess per suite is the point of this runner and is not negotiable: an exit code is then
a fact about one file. But ISOLATION AND SERIALISATION ARE INDEPENDENT, and this ran them one at
a time. Each subprocess re-imports the whole stack, so the wall clock is dominated by the same
imports repeated once per suite.

`--jobs N` runs N of those subprocesses at once. Each is still its own process with its own exit
code, and results are collected in SORTED order rather than completion order, so the report is
identical to the serial one. It defaulted to 1 because suites sharing a temporary path would
collide, and that is a property of the suites rather than of the runner - the default may only be
raised for a suite set MEASURED to give the same result both ways.

MEASURED (harness ADR-0026, step 1, 2026-09-15): the 98-suite set green serially in 138 s and
green with `--jobs 4` on three consecutive runs in 49 s each, the same verdict every time. The
commit gate had passed `--jobs 4` since ADR-0023; the default stayed at 1, so every author's
prompt and the cluster's own step 0 ran the serial form - 2.3 minutes per exchange for a result
the gate already had in 50 s. The default follows the measurement.
"""
import argparse
import glob
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def has_arrays(py) -> bool:
    """Whether interpreter `py` can import the array stack the CLI checks need."""
    try:
        return subprocess.run([py, "-c", "import anndata, numpy, pandas"], capture_output=True,
                              timeout=120).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def interpreter(python=None):
    """(interpreter, why) - the one the suites run under.

    THE GATE SKIPPED THE HALF THAT WOULD HAVE FAILED (harness ADR-0026, the open items): its
    interpreter has no array stack, the status contract's CLI half printed SKIP and exited 0,
    and a change that broke that contract was committed green; the same suite under an
    interpreter with anndata said FAIL. When the running interpreter lacks the stack and the
    repository's own `.venv/bin/python` - or $SCPROFILE_TEST_PYTHON - has it, the suites run
    under that one, and the summary says which. `--python` and SCPROFILE_TEST_PYTHON_FORCE=1
    take an interpreter as given.
    """
    if python:
        return python, "given with --python"
    forced = os.environ.get("SCPROFILE_TEST_PYTHON")
    if forced and os.environ.get("SCPROFILE_TEST_PYTHON_FORCE"):
        return forced, "$SCPROFILE_TEST_PYTHON, forced"
    if has_arrays(sys.executable):
        return sys.executable, "this interpreter has the array stack"
    for cand, why in ((forced, "$SCPROFILE_TEST_PYTHON"),
                      (str(ROOT / ".venv" / "bin" / "python"), "the repository's .venv")):
        if cand and os.path.exists(cand) and has_arrays(cand):
            return cand, f"{why}: this interpreter lacks the array stack and that one has it"
    return sys.executable, ("this interpreter lacks the array stack and no other was found "
                            "(.venv/bin/python or $SCPROFILE_TEST_PYTHON); CLI checks SKIP")


#: A SKIP LINE STARTS WITH THE WORD: `  SKIP a run in which ...`, `ok: skipped, pandas is not
#: importable here`. Matching the word anywhere counted a check that PASSED about skipping.
SKIP_STARTS = ("SKIP", "skipped", "ok: skipped")


def skipped_in(out) -> int:
    """How many checks a suite's output says it skipped."""
    return sum(1 for ln in out.splitlines() if ln.strip().startswith(SKIP_STARTS))


def run(pattern=None, python=None, jobs=1):
    """[(name, output)] for every suite that exited non-zero, and the skip count."""
    pat = pattern or str(ROOT / "tests" / "test_*.py")
    py, _why = interpreter(python)
    env = dict(os.environ, PYTHONPATH=str(ROOT))
    bad = []

    def one(path):
        p = subprocess.run([py, path], capture_output=True, text=True, env=env, cwd=ROOT)
        return path, p.returncode, (p.stdout + p.stderr).strip()

    paths = sorted(glob.glob(pat))
    if jobs > 1:
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as pool:
            outcomes = list(pool.map(one, paths))     # sorted order, not completion order
    else:
        outcomes = [one(x) for x in paths]
    run.skipped = sum(skipped_in(out) for _p, _c, out in outcomes)
    for path, code, out in outcomes:
        if code != 0:
            bad.append((os.path.basename(path), out))
        elif not out:
            # A SUITE THAT RUNS NOTHING EXITS 0, which is indistinguishable from a suite that
            # passed. Found with a canary that asserted False and was reported green: it had no
            # runner, so executing the file merely defined a function. Silence is the signature -
            # every real suite here prints what it checked.
            bad.append((os.path.basename(path),
                        "the suite produced NO OUTPUT and exited 0. It probably defines tests "
                        "and never runs them - a file with neither a __main__ block nor "
                        "module-level calls is not a suite, it is a library."))
    return bad, sorted(glob.glob(pat))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pattern", default=None)
    ap.add_argument("--python", default=None)
    ap.add_argument("--jobs", type=int, default=4,
                    help="run this many suites at once; each is still its own process")
    ap.add_argument("--tail", type=int, default=12, help="lines of output per failing suite")
    a = ap.parse_args(argv)
    py, why = interpreter(a.python)
    print(f"interpreter: {py}  ({why})")
    bad, files = run(a.pattern, py, a.jobs)
    skipped = getattr(run, "skipped", 0)
    if bad:
        print(f"{len(bad)} FAILING of {len(files)} suite(s):")
        for name, out in bad:
            print(f"\n  FAIL {name}")
            for line in out.splitlines()[-a.tail:]:
                print(f"       {line}")
        return 1
    # A GREEN WITH SKIPS IS A WEAKER STATEMENT, and the summary says so in the word the suites
    # use: what this interpreter could not run has not been established.
    print(f"green: {len(files)} suite(s), nothing failing"
          + (f"; {skipped} check(s) SKIPPED on this interpreter - not established here"
             if skipped else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
