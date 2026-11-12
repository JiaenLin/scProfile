"""A plugin's own refusal inside run() fails the fixture's last step (harness ROUTE R46, pool D).

autodev W055: with the plugin's interpreter, abundance refusing inside run() (its per-level floor
above what the fixture has) read `ok` at the fixture tier. The run's STATUS.json says `ok`
("kernels ran, results merged") and `run` exits 0, and the ladder reads STATUS in the tier's
folder, one above the run's. The refusal is in the instance's out.json. `scprofile capacity
--all-ok` reads every one and exits 1 naming each instance not `ok`; the fixture command DEVPOINTS
declares runs it as its last step. Fails at 2e5b95a: no such flag, and the step has none.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FAIL = []


def ck(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'} {name}" + (f" - {detail}" if not cond else ""))
    if not cond:
        FAIL.append(name)


def cap(run):
    r = subprocess.run([sys.executable, "-m", "scprofile.cli", "capacity", "--out", str(run),
                        "--all-ok"], cwd=str(ROOT), capture_output=True, text=True, timeout=300)
    return r.returncode, r.stdout + r.stderr


td = Path(tempfile.mkdtemp(prefix="w055-allok-"))
for name, states in (("ok", {"a": "ok", "b/u1": "ok"}), ("refused", {"a": "ok", "b/u1": "refused"}),
                     ("partial", {"a": "partial"}), ("unreadable", {"a": None}), ("empty", {})):
    run = td / name
    (run / "kernels").mkdir(parents=True)
    json.dump({"status": "ok", "headline": "kernels ran, results merged, report written"},
              open(run / "STATUS.json", "w"))
    for rel, st in states.items():
        (run / "kernels" / rel).mkdir(parents=True)
        (run / "kernels" / rel / "out.json").write_text(
            "{not json" if st is None else json.dumps({"status": st, "headline": f"{st} here"}))
print("1. `capacity --all-ok` reads every instance's out.json, not the run's STATUS")
rc, out = cap(td / "ok")
ck("every instance ok: exit 0", rc == 0 and "every one of 2 instance(s) ended ok" in out, out)
rc, out = cap(td / "refused")
ck("one per-unit instance refused, the run's STATUS ok: exit 1, the instance named",
   rc == 1 and "kernels/b/u1/out.json: refused - refused here" in out, out)
rc, out = cap(td / "partial")
ck("a partial is not ok", rc == 1 and "partial" in out, out)
rc, out = cap(td / "unreadable")
ck("an unreadable record is not ok", rc == 1 and "unreadable" in out, out)
rc, out = cap(td / "empty")
ck("no instance at all is not ok", rc == 1 and "no instance" in out, out)

print("\n2. the fixture command's last step asks it")
import yaml                                                                    # noqa: E402
fx = (yaml.safe_load((ROOT / "DEVPOINTS.yaml").read_text(encoding="utf-8")).get("fixture") or {})
last = (fx.get("command") or [[]])[-1]
ck("the last step is `capacity --all-ok` on the run", "capacity" in last and "--all-ok" in last
   and "{out}/run" in last, last)
ck("and no refusal is accepted at the tier", not fx.get("accepts_refusal"), fx.get("accepts_refusal"))

print()
if FAIL:
    print(f"{len(FAIL)} FAILED: {FAIL}")
    sys.exit(1)
print("a plugin's own refusal fails the fixture's last step")
