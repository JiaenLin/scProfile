"""A run renders its report once, and a redraw is offered the cache (harness ADR-0026, step 1).

WHAT THE RUNS ON THE CLUSTER SHOWED. `scprofile run` ends by writing the report, the README, the
section and the capacity record; the job the maker emits then ran `scprofile report --out` as
its first after-step and built the same pages again - the figure-set line appears twice in every
job log, about two minutes per run. And every rerun of the arc carried `--no-cache` from the
audit reference it reproduced, so eighteen units re-inferred CellChat on every redraw: the flag
that rules the cache out for an audit is the one a redraw must not carry, and this repository
is the one that knows its own flags. Both are declarations in DEVPOINTS.yaml; this holds them.

Run: python tests/test_a_run_is_reported_once.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

FAIL = []


def ck(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'} {name}" + (f" — {detail}" if not cond else ""))
    if not cond:
        FAIL.append(name)


dev = (ROOT / "DEVPOINTS.yaml").read_text(encoding="utf-8")
run_block = dev.split("\nrun:", 1)[1].split("\n\n", 1)[0] if "\nrun:" in dev else ""
after = [ln for ln in run_block.splitlines() if ln.strip().startswith("- [")]

print("the after-steps of a run do not build the report a second time")
ck("run.after names status, promised and memory", all(
    any(w in ln for ln in after) for w in ('"status"', '"--promised"', '"--memory"')), str(after))
ck("run.after names no `report`: the run already wrote it",
   not any('"report"' in ln for ln in after), str(after))

print("\na redraw drops the flag that rules the cache out")
ck("run.redraw_drops names --no-cache", "redraw_drops" in run_block and "--no-cache" in run_block,
   run_block[:300])

print("\nthe flag it names is one `run` accepts")
import subprocess                                                               # noqa: E402
helped = subprocess.run([sys.executable, "-m", "scprofile.cli", "run", "--help"], cwd=str(ROOT),
                        capture_output=True, text=True).stdout
ck("`scprofile run --no-cache` is a flag", "--no-cache" in helped, helped[:200])

if FAIL:
    print(f"\n{len(FAIL)} FAILED: " + ", ".join(FAIL))
    sys.exit(1)
print("\na run is reported once, and a redraw is offered the cache")
