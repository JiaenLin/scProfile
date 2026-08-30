"""A design in the object must not be invisible because no table was passed.

WHAT THIS COST: a run was launched without `--design` on an object whose obs already carried
the study's two factors and its batch. The host printed "design table NOT GIVEN", resolved no
arms, scheduled ten per-sample instances instead of eighteen, drew no contrast at all and ran to
completion. Nothing failed. The comparison the study exists to make was simply absent.

A derived design is NOT a replacement for a table - a table can carry factors the object has
never heard of - so a passed table always wins, and a derived one is always reported as derived.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FAILURES = []


def check(c, m):
    if not c:
        FAILURES.append(m)


try:
    import pandas as pd
except Exception:                                                         # noqa: BLE001
    print("ok: skipped, pandas is not importable here (this check runs where the arrays are)")
    raise SystemExit(0)

from scprofile.inputs import derive_design                                # noqa: E402

obs = pd.DataFrame({
    "smp":   ["a"] * 3 + ["b"] * 3 + ["c"] * 2 + ["d"] * 2,
    "fac1":  ["hi"] * 6 + ["lo"] * 4,
    "fac2":  ["p"] * 3 + ["q"] * 3 + ["p"] * 2 + ["q"] * 2,
    "block": ["B1"] * 6 + ["B2"] * 4,
    "percell": list("xyzxyzxyxy"),                       # varies within a sample
    "score": [0.1, 0.2, 0.3] * 3 + [0.4],                # continuous
    "flat":  ["k"] * 10,                                 # one level
    "renamed_sample": ["a"] * 3 + ["b"] * 3 + ["c"] * 2 + ["d"] * 2,
})
tab, fac = derive_design(obs, "smp")

check(fac == ["fac1", "fac2", "block"], f"wrong factors: {fac}")
check(set(tab) == {"a", "b", "c", "d"}, f"wrong samples: {sorted(tab)}")
check(tab["a"] == {"fac1": "hi", "fac2": "p", "block": "B1"}, f"wrong row: {tab['a']}")
for bad, why in (("percell", "varies within a sample, so it is not sample-level metadata"),
                 ("score", "is continuous, so a per-sample value is a measurement"),
                 ("flat", "has one level, so it defines no contrast"),
                 ("renamed_sample", "has one level per sample, so it IS the sample")):
    check(bad not in fac, f"{bad} was taken as a design factor, but it {why}")

# THE UNIT AXIS MUST FOLLOW. Deriving factors nothing uses would be a message, not a fix.
from scprofile import units as U                                          # noqa: E402

plan, _why = U.resolve(tab, sample_key="smp", samples=sorted(tab))
grp = [p for p in plan if p["kind"] == "group"]
check(bool(grp), "a derived design resolved no group axis, so no contrast can be drawn")
if grp:
    check(len(grp[0]["units"]) >= 4,
          f"derived design gave only {len(grp[0]['units'])} group unit(s)")

if FAILURES:
    print("FAIL")
    for f in FAILURES:
        print("  -", f)
    raise SystemExit(1)
print(f"ok: {len(fac)} factor(s) derived from the object, 4 non-factors correctly refused, "
      f"and the unit axis resolves {len(grp[0]['units'])} group unit(s) from them")
