"""A first run is not blocked for having reused nothing.

Stations 2-5 of the loop (landscape, licence, adopt, merge) ask whether reuse reuses. Every first
run of a new cohort has used no `--reuse-from`, so all four were BLOCKED and the loop exited 1
until a second, redundant run existed (harness B1-020). On such a run they are now `n/a` and do
not block; on a run that did reuse anything, they are asked exactly as before. And a blocked round
reports the eye's coverage as a count, not as an instruction about what may be reported (B1-016).

Asked of the real driver, `tests/loop_stations.py`, on run directories built here.

Run: python tests/test_a_first_run_needs_no_reuse.py
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAIL = []


def ck(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'} {name}" + (f" — {detail}" if not cond else ""))
    if not cond:
        FAIL.append(name)


def loop(*argv):
    env = dict(os.environ, PYTHONPATH=str(ROOT))
    r = subprocess.run([sys.executable, str(ROOT / "tests" / "loop_stations.py"), *argv],
                       cwd=str(ROOT), env=env, capture_output=True, text=True, timeout=300)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def run_dir(where, **extra):
    where.mkdir(parents=True)
    (where / "report.json").write_text(json.dumps({"plugins": {}, **extra}), encoding="utf-8")
    return where


with tempfile.TemporaryDirectory() as t:
    fresh = run_dir(Path(t) / "runs" / "20990101T000000Z_first")

    print("a first run: nothing reused")
    rc, out = loop("--run", str(fresh), "--station", "2,3,4,5")
    marks = [l for l in out.splitlines() if l.startswith("  n/a ")]
    ck("stations 2-5 are n/a, all four", len(marks) == 4, out[-500:])
    ck("each says why", all("no run used --reuse-from" in l for l in marks), str(marks))
    ck("and the loop exits 0", rc == 0, f"exit {rc}")
    rc, out = loop("--run", str(fresh), "--station", "2,3,4,5", "--json")
    try:
        st = {k: v["state"] for k, v in json.loads(out)["stations"].items()}
    except Exception as e:                                                # noqa: BLE001
        st = {"unreadable": str(e)}
    ck("the JSON says n/a and names no blocked station",
       set(st.values()) == {"n/a"} and rc == 0, f"{st} exit {rc}")

    print("\na run that holds a licence: reuse was asked for, so the stations are asked")
    lic = run_dir(Path(t) / "runs2" / "20990101T000000Z_licensed")
    (lic / "LICENCES").mkdir()
    (lic / "LICENCES" / "x.json").write_text(json.dumps({"grade": "granted"}), encoding="utf-8")
    rc, out = loop("--run", str(lic), "--station", "2,3,4,5")
    ck("no station is n/a", not [l for l in out.splitlines() if l.startswith("  n/a ")],
       out[-400:])
    ck("adoption that never happened is BLOCKED, not skipped",
       rc == 1 and any(l.startswith("BLOCKED") and "4 adopt" in l for l in out.splitlines()),
       f"exit {rc}: {out[-400:]}")

    print("\na whole round over a directory of runs, blocked")
    # THE ROUND REPORTS COVERAGE AS A COUNT (harness B1-016), and a finding that is not a bug is
    # answered rather than turned into a change (B1-096). The round is blocked here at station 1,
    # which is when the count is printed.
    rc, out = loop("--runs", str(fresh.parent))
    ck("the round is blocked, and says where", rc == 1 and "THE LOOP IS BLOCKED AT" in out,
       f"exit {rc}")
    ck("it reports the eye's coverage as N of M", "    eye: 0/0 looked at" in out, out[-600:])
    ck("and nothing tells the reader what may not be reported as progress",
       "PROGRESS" not in out.upper(), [l for l in out.splitlines() if "PROGRESS" in l.upper()])
    ck("a finding that is not a bug is answered or recorded",
       "answered (review --answer) or recorded" in out
       and "or it did not happen" not in out, out[-600:])

print("\n" + ("a first run needs no reuse" if not FAIL else f"{len(FAIL)} FAILED: {FAIL}"))
sys.exit(1 if FAIL else 0)
