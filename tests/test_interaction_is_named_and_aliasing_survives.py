"""Two defects in the branch only a crossed design reaches, both found on a real 2x2.

NEITHER IS REACHABLE ON ONE FACTOR, which is why neither was found by a suite that passes. An
interaction needs two crossed factors to exist at all, and an alias between a design factor and a
technical one needs a design that HAS a technical column worth checking.

  1. THE INTERACTION HAD NO NAME. Every marginal and every simple effect is built by `_entry`,
     which calls `contrast_label`. The interaction branch builds its dict by hand and left the
     key out. That is not cosmetic: the label is how a consumer finds the figures drawn for a
     contrast, `compose` selects on it, and a figure carrying the empty label is filed as a
     COHORT figure - the opposite of what an interaction is. So the one comparison a 2x2 exists
     to produce could never be matched to a panel.

  2. NAMING THE BIOLOGICAL FACTORS DELETED THE ALIASING WARNING. `aliased()` took one list and
     used it as both the factors to report on AND the candidates to compare against, so a caller
     that named its two design factors - the careful thing to do, and what the planner does -
     compared them only against each other. A factor perfectly aliased with a technical column
     came back clean, and every caption then described an effect that is equally an effect of
     the machine that measured it.

NOBODY'S VOCABULARY. The design below is the SHAPE of a real cohort and none of its words: two
crossed factors, two levels each, one technical column that splits the samples exactly as the
first factor does, and a second technical column that does not.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scprofile.design_panel import aliased, comparisons, contrast_label   # noqa: E402

fails = []


def check(ok, msg):
    if not ok:
        fails.append(msg)


# f1 x f2, two per cell. `machine` splits the samples exactly as f1 does; `run` does not.
DES = {}
for i, (f1, f2) in enumerate([(a, b) for a in ("lo", "hi") for b in ("base", "alt")
                              for _ in (0, 1)]):
    DES[f"u{i}"] = {"f1": f1, "f2": f2,
                    "machine": "m1" if f1 == "lo" else "m2",
                    "run": "r1" if i % 2 else "r2"}

BIO, TECH = ["f1", "f2"], ["machine", "run"]
CTRL = {"f1": "lo", "f2": "base"}

# 1. the interaction is named, and not named the same as the marginal it is not
got = comparisons(DES, factors=BIO, technical=TECH, controls=CTRL)
inter = [c for c in got if c["kind"] == "interaction"]
check(len(inter) == 1, f"a 2x2 with every cell filled produced {len(inter)} interaction(s)")
if inter:
    lab = inter[0].get("label")
    check(bool(lab), "the interaction carries no label, so no consumer can find its figures")
    check(lab == "f1 \u00d7 f2",
          f"the interaction is named {lab!r} - it must be the same string "
          f"`compare_panel.draw_interaction` returns, because `compose` matches on it")
    marg = {c.get("label") for c in got if c["kind"] == "marginal"}
    check(lab not in marg,
          f"the interaction shares the name {lab!r} with a marginal, so one contrast's panels "
          f"will be placed under the other's question")

check(contrast_label("f1", None, other="f2") == "f1 \u00d7 f2",
      "contrast_label cannot name a pair")
check(contrast_label("f1") == "f1", "contrast_label changed how it names a marginal")
check(contrast_label("f1", {"f2": "base"}) == "f1 | f2 = base",
      "contrast_label changed how it names a simple effect")

# 2. the alias survives being asked about the biological factors only
check(aliased(DES, BIO).get("f1") == ["machine"],
      f"narrowing the factors lost the alias: {aliased(DES, BIO)}")
check(aliased(DES, BIO).get("f2") == [],
      "a factor with no alias was given one")
check(aliased(DES).get("f1") == ["machine"], "the alias is not found even over every column")

for c in got:
    if c["factor"] == "f1" or c.get("other") == "f1":
        check("machine" in (c.get("aliased_with") or []) or c["factor"] != "f1",
              f"{c.get('label')!r} involves the aliased factor and does not say so")
check((inter[0].get("aliased_with") if inter else None) == ["machine"],
      "the interaction does not carry the alias, so the one comparison the design exists for "
      "reads as a clean result")

# 3. and the reading order still holds: simple, then marginal, then interaction
rank = {"simple": 0, "marginal": 1, "interaction": 2}
seq = [rank[c["kind"]] for c in got]
check(seq == sorted(seq), f"the reading order moved: {[c['kind'] for c in got]}")

if fails:
    print("FAIL")
    for f in fails:
        print("  -", f)
    sys.exit(1)
print("ok - the interaction is named, and an alias with a technical column survives being "
      "asked about the biology")
