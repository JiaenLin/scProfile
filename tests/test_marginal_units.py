"""A marginal comparison needs a unit on each side, and the crossing does not provide one.

The failure this pins: with two factors, `resolve` returned the four crossed arms and nothing
else, so `aged` pooled over diet existed as a QUESTION the design enumerated and as no OBJECT
any tool could be handed. Every marginal contrast printed "no single unit pools each side" and
drew nothing, on every run, while the design plainly asked for it.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scprofile import units as U                                          # noqa: E402

FAILURES = []


def check(cond, msg):
    if not cond:
        FAILURES.append(msg)


D2 = {f"s{i}": {"f1": a, "f2": b, "batch": "b1"}
      for i, (a, b) in enumerate([("lo", "x"), ("lo", "x"), ("lo", "y"), ("lo", "y"),
                                  ("hi", "x"), ("hi", "x"), ("hi", "y"), ("hi", "y")])}

plan, why = U.resolve(D2, prefer="group")
grp = next(p for p in plan if p["kind"] == "group")

check(set(grp["units"]) >= {"lo_x", "lo_y", "hi_x", "hi_y"},
      f"the crossed arms are missing: {sorted(grp['units'])}")
check({"lo", "hi", "x", "y"} <= set(grp["units"]),
      f"no marginal unit per level: {sorted(grp['units'])}")
check(sorted(grp["units"]["lo"]) == ["s0", "s1", "s2", "s3"],
      f"the marginal unit does not pool the level: {grp['units'].get('lo')}")
check(any("marginal" in w for w in why), "resolve did not say it added marginal units")

mem = U.membership(D2)
for filt, want in (({"f1": "lo"}, "lo"), ({"f2": "y"}, "y"),
                   ({"f1": "hi", "f2": "x"}, "hi_x")):
    side = frozenset(s for s, r in D2.items()
                     if all(str(r.get(k)) == v for k, v in filt.items()))
    hit = [u for u, m in mem.items() if m == side]
    check(want in hit, f"{filt} matched {hit}, wanted {want}")

# ONE FACTOR: the levels ARE the crossing, so marginal units would be duplicates under a
# second name - the worst kind, because two names for one object read as two results.
D1 = {f"s{i}": {"f1": a} for i, a in enumerate(["lo", "lo", "hi", "hi"])}
check(U.marginal_groups(D1, ["f1"]) == {},
      "a one-factor design got marginal units duplicating its own arms")

# A LEVEL NAME THAT COLLIDES must be qualified, or a unit name means two things.
DC = {"s0": {"f1": "a", "f2": "a"}, "s1": {"f1": "b", "f2": "a"},
      "s2": {"f1": "a", "f2": "b"}, "s3": {"f1": "b", "f2": "b"}}
mg = U.marginal_groups(DC, ["f1", "f2"])
check(all("=" in k for k in mg), f"colliding level names were not qualified: {sorted(mg)}")
check(sorted(mg) == ["f1=a", "f1=b", "f2=a", "f2=b"], f"unexpected labels: {sorted(mg)}")

if FAILURES:
    print("FAIL")
    for f in FAILURES:
        print("  -", f)
    raise SystemExit(1)
print(f"ok: marginal units resolve on both sides of every marginal contrast "
      f"({len(grp['units'])} group unit(s) from a 2x2)")
