"""The compare phase's launches run under the same kind of pool as the units: each at the share
the plugin declares, as many at once as the run's budget holds (harness ADR-0026, step 1).

MEASURED ON THE CLUSTER. Seven launches of about 72 s each, one after another, each handed all
64 cores and using one: 505 s of R and 13.5 minutes of phase, in every thirty-minute rerun. The
run phase already schedules its instances by permits - `cellchat[Aging1](2c)` eighteen at once
under a budget of 64 - and the compare phase launched the same plugin with the whole budget,
serially. A plugin that declares no `cores` keeps today's shape: one launch at a time under the
whole budget, and every earlier pin on the phase record holds unchanged.

Run: python tests/test_the_compare_launches_share_the_pool.py
"""
import contextlib
import io
import json
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scprofile import kernels as _K                                             # noqa: E402
from scprofile import report as _RP                                             # noqa: E402
from scprofile import resume as _RS                                             # noqa: E402
from scprofile import runner as _RN                                             # noqa: E402
from scprofile.compare_panel import arm_pairs                                   # noqa: E402

FAIL = []


def ck(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'} {name}" + (f" — {detail}" if not cond else ""))
    if not cond:
        FAIL.append(name)


ENTRY = (
    "import json, os, sys, time\n"
    "from pathlib import Path\n"
    "if sys.argv[1] == '--phases':\n"
    "    print('run compare'); raise SystemExit(0)\n"
    "spec = json.loads(Path(sys.argv[3]).read_text())\n"
    "out = Path(spec['out_dir']); (out / 'figures').mkdir(parents=True, exist_ok=True)\n"
    "(out / 'started.txt').write_text(json.dumps({'t': time.time(),\n"
    "    'omp': os.environ.get('OMP_NUM_THREADS')}))\n"
    "time.sleep(1.2)\n"
    "(out / 'figures' / 'nativecmp_x.png').write_bytes(b'')\n"
    "raise SystemExit(0)\n")

# A two-by-two design: six pairs (two simple effects per factor and the two margins), every
# one pooled by a unit the design names, so every one is launchable.
DESIGN = {"s1": {"dose": "lo", "time": "early"}, "s2": {"dose": "hi", "time": "early"},
          "s3": {"dose": "lo", "time": "late"}, "s4": {"dose": "hi", "time": "late"}}
UNITS = [{"unit": u, "dir": f"kernels/demo/{u}"}
         for u in ("lo_early", "hi_early", "lo_late", "hi_late", "lo", "hi", "early", "late")]


def tree(root):
    k = Path(root) / "kernels" / "demo"
    for u in UNITS:
        (k / u["unit"]).mkdir(parents=True, exist_ok=True)
        (k / u["unit"] / "in.json").write_text("{}", encoding="utf-8")
        (k / u["unit"] / "out.json").write_text(json.dumps({"figures": []}), encoding="utf-8")
    (k / "demo.py").write_text("# a plugin\n", encoding="utf-8")
    (Path(root) / "fake_entry.py").write_text(ENTRY, encoding="utf-8")
    return k


def drive(root, declared_cores, budget):
    class Fake:
        spec = {"version": "1.0.0", **({"cores": declared_cores} if declared_cores else {})}
        name = "demo"
    old = (_K.discover, _K.SHARED_ENTRY, _RN.interpreter)
    _K.discover = lambda *a, **k: {"demo": Fake()}
    _K.SHARED_ENTRY = Path(root) / "fake_entry.py"
    _RN.interpreter = lambda *a, **k: (sys.executable, "the test's own interpreter")
    buf = io.StringIO()
    t0 = time.time()
    try:
        with contextlib.redirect_stdout(buf):
            _RP._native_compare("demo", {}, {u["unit"]: [] for u in UNITS}, DESIGN,
                                arm_pairs(DESIGN), root, UNITS, declared={}, timeout=60,
                                cores=budget)
    finally:
        _K.discover, _K.SHARED_ENTRY, _RN.interpreter = old
    rec = json.loads((Path(root) / "kernels" / "demo" / _RS.COMPARE_DIRNAME
                      / _RS.PHASE_RECORD).read_text())
    starts = {}
    for d in (Path(root) / "kernels" / "demo" / _RS.COMPARE_DIRNAME).iterdir():
        f = d / "started.txt"
        if f.is_file():
            starts[d.name] = json.loads(f.read_text())
    return rec, starts, time.time() - t0, buf.getvalue()


print("a plugin declaring a share runs its pair launches at once, each at that share")
d = Path(tempfile.mkdtemp())
tree(d)
rec, starts, took, said = drive(d, declared_cores=2, budget=8)
pairs = [L for L in rec["launches"] if L["kind"] == "arm_pair"]
ck("six pairs launched", len(pairs) == 6, str([L["pair"] for L in rec["launches"]]))
ck("each launch ran at the declared share", all(L["cores"] == 2 for L in pairs),
   str([L["cores"] for L in pairs]))
ck("and its environment was capped to the share",
   all(v.get("omp") == "2" for k, v in starts.items() if k != "_across_arms"), str(starts))
pair_starts = sorted(v["t"] for k, v in starts.items() if k != "_across_arms")
ck("four of the six started together (the budget holds four shares), not one after another",
   len(pair_starts) == 6 and pair_starts[3] - pair_starts[0] < 0.9,
   f"spread of the first four {pair_starts[3] - pair_starts[0] if len(pair_starts) > 3 else None}")
ck("the phase took less than the sum of its launches", took < 6 * 1.2, f"{took:.1f}s")
ck("the phase record carries the budget, the share and how many at once",
   rec.get("cores") == 8 and rec.get("share") == 2 and rec.get("at_once") == 4,
   str({k: rec.get(k) for k in ("cores", "share", "at_once")}))
shutil.rmtree(d, ignore_errors=True)

print("\na plugin declaring no share keeps today's shape: one at a time under the whole budget")
d = Path(tempfile.mkdtemp())
tree(d)
rec, starts, took, said = drive(d, declared_cores=None, budget=8)
pairs = [L for L in rec["launches"] if L["kind"] == "arm_pair"]
ck("each launch ran under the whole budget", all(L["cores"] == 8 for L in pairs),
   str([L["cores"] for L in pairs]))
ck("the record's own limits equal the launches'", rec.get("cores") == 8 and rec.get("share") == 8
   and rec.get("at_once") == 1, str({k: rec.get(k) for k in ("cores", "share", "at_once")}))
pair_starts = sorted(v["t"] for k, v in starts.items() if k != "_across_arms")
ck("the pairs ran one after another", len(pair_starts) == 6 and pair_starts[-1] - pair_starts[0] > 5.0,
   f"spread {pair_starts[-1] - pair_starts[0] if pair_starts else None}")
shutil.rmtree(d, ignore_errors=True)

if FAIL:
    print(f"\n{len(FAIL)} FAILED: " + ", ".join(FAIL))
    sys.exit(1)
print("\nthe compare launches share the pool at the plugin's declared share")
