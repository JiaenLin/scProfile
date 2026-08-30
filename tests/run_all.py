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
"""
import argparse
import glob
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(pattern=None, python=None):
    """[(name, output)] for every suite that exited non-zero."""
    pat = pattern or str(ROOT / "tests" / "test_*.py")
    py = python or sys.executable
    env = dict(os.environ, PYTHONPATH=str(ROOT))
    bad = []
    for path in sorted(glob.glob(pat)):
        p = subprocess.run([py, path], capture_output=True, text=True, env=env, cwd=ROOT)
        if p.returncode != 0:
            bad.append((os.path.basename(path), (p.stdout + p.stderr).strip()))
    return bad, sorted(glob.glob(pat))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pattern", default=None)
    ap.add_argument("--python", default=None)
    ap.add_argument("--tail", type=int, default=12, help="lines of output per failing suite")
    a = ap.parse_args(argv)
    bad, files = run(a.pattern, a.python)
    if bad:
        print(f"{len(bad)} FAILING of {len(files)} suite(s):")
        for name, out in bad:
            print(f"\n  FAIL {name}")
            for line in out.splitlines()[-a.tail:]:
                print(f"       {line}")
        return 1
    print(f"green: {len(files)} suite(s), nothing failing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
