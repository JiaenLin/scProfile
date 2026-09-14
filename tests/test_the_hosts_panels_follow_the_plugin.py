"""The host's own panels follow the plugin's declaration, and the plan is counted per axis
(harness ADR-0024, step 3).

THE HOST DREW EVERY KIND IT OWNS FOR EVERY PLUGIN WITH A NETWORK: three panels per contrast,
seven per arm, three for the cohort, the interaction - 84 files on a 2x2 cohort beside the
plan's own 143, most of them twins of a plate the wrapped tool draws itself. The layout decides
which of the host's kinds a reader is handed (`host_keep` in the tool's DEVPOINTS) and writes
the decision into the plugin as `report.host_panels`; the host reads it at every one of its
draw sites. A plugin that declares none gets every kind, as before - the eight plugins not yet
migrated are untouched.

Everything here is invented: a host that passed by recognising a real method's names would
fail. Run: python tests/test_the_hosts_panels_follow_the_plugin.py
"""
import sys
import tempfile
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import pandas as pd                                                             # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scprofile import compare_panel as CP                                       # noqa: E402
from scprofile import declare as D                                              # noqa: E402
from scprofile import planner as PL                                             # noqa: E402

FAIL = []


def ck(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'} {name}" + (f" — {detail}" if not cond else ""))
    if not cond:
        FAIL.append(name)


POPS = ["Alpha cell", "Beta cell", "Gamma cell", "Delta cell"]
DESIGN = {"S1": {"dose": "low"}, "S2": {"dose": "low"}, "S3": {"dose": "high"},
          "S4": {"dose": "high"}}


def edges(seed):
    rows = []
    for i, s in enumerate(POPS):
        for j, t in enumerate(POPS):
            for k, pw in enumerate(("P1", "P2", "P3")):
                rows.append({"source": s, "target": t, "prob": 0.1 + ((i * 7 + j * 3 + k + seed) % 9) / 10.0,
                             "pathway_name": pw, "interaction_name": f"L{k}-R{j}"})
    return pd.DataFrame(rows)


PER = {"S1": edges(1), "S2": edges(2), "S3": edges(3), "S4": edges(4)}
PAIRS = CP.arm_pairs(DESIGN)

print("the host's per-contrast panels follow the declared kinds")
with tempfile.TemporaryDirectory() as td:
    got = CP.draw_contrast(PER, DESIGN, PAIRS[0], td, "p", group_col="pathway_name")
    ids = {t[0].split("__")[0] for t in got}
    ck("undeclared, every kind the host owns is drawn",
       {"C1_diff_strength", "C3_flow", "C4_role_shift"} <= ids, str(ids))
with tempfile.TemporaryDirectory() as td:
    got = CP.draw_contrast(PER, DESIGN, PAIRS[0], td, "p", group_col="pathway_name",
                           kinds=["diff_matrix"])
    ids = {t[0].split("__")[0] for t in got}
    ck("declared, only the named kinds are drawn",
       "C1_diff_strength" in ids and ids <= {"C1_diff_count", "C1_diff_strength"}, str(ids))
    ck("and nothing else reached the disk",
       not [p for p in Path(td).glob("*.png") if "C3_" in p.name or "C4_" in p.name])
with tempfile.TemporaryDirectory() as td:
    got = CP.draw_contrast(PER, DESIGN, PAIRS[0], td, "p", group_col="pathway_name", kinds=[])
    ck("an empty declaration draws none of them", got == [] and not list(Path(td).glob("*.png")))

print("\nthe host's per-arm panels follow the declared kinds")
arms = CP.arms_in(DESIGN, PAIRS)
with tempfile.TemporaryDirectory() as td:
    got = CP.draw_arm_networks(PER, DESIGN, arms, td, "p", group_col="pathway_name",
                               member_col="interaction_name", kinds=["circle"])
    ids = {t[0].split("__")[0] for t in got}
    ck("only the circle is drawn per arm", ids == {"N1_circle"}, str(ids))
with tempfile.TemporaryDirectory() as td:
    got = CP.draw_arm_networks(PER, DESIGN, arms, td, "p", group_col="pathway_name",
                               member_col="interaction_name", kinds=[])
    ck("an empty declaration draws no arm panel", got == [])
with tempfile.TemporaryDirectory() as td:
    got = CP.draw_arm_networks(PER, DESIGN, arms, td, "p", group_col="pathway_name",
                               member_col="interaction_name")
    ids = {t[0].split("__")[0] for t in got}
    ck("undeclared, every arm kind is drawn", {"N1_circle", "N2_chord", "N3_matrix"} <= ids, str(ids))

print("\nthe declaration is checked against the kinds the host owns")
spec = {"name": "demo", "version": "1.0.0", "requires": {"python": ">=3.10"},
        "report": {"figures": [], "host_panels": ["across_design", "nonsense"]}}
found = [m for lvl, m in D.check(spec, "demo") if "host_panels" in m and lvl == "ERROR"]
ck("an unknown host kind is refused, by name", found and "nonsense" in found[0], str(found)[:200])
spec["report"]["host_panels"] = ["across_design", "unit_presence"]
found = [m for lvl, m in D.check(spec, "demo") if "host_panels" in m]
ck("known kinds pass", not found, str(found)[:200])
spec["report"]["host_panels"] = "across_design"
found = [m for lvl, m in D.check(spec, "demo") if "host_panels" in m and lvl == "ERROR"]
ck("a string is not a list of kinds", bool(found), str(found)[:200])

print("\nthe plan is counted per axis, before a job is submitted")
SPEC = {"report": {"figures": [
    {"id": "per_sample", "kind": "unit_presence", "drawn_by": "plugin", "axis": "sample",
     "position": "appendix"},
    {"id": "native_per_group", "kind": "matrix", "drawn_by": "tool", "fn": "f", "axis": "group",
     "position": "contrast"},
    {"id": "native_both", "kind": "circle", "drawn_by": "tool", "fn": "g", "axis": "unit",
     "position": "contrast"},
    {"id": "nativecmp_c", "kind": "diff_matrix", "drawn_by": "tool", "fn": "h",
     "axis": "contrast", "position": "contrast", "at_most": 2},
    {"id": "nativecmp_i", "kind": "interaction", "drawn_by": "plugin", "axis": "interaction",
     "position": "conclusion", "at_most": 3},
    {"id": "cohort_x", "kind": "coverage", "drawn_by": "plugin", "axis": "cohort",
     "position": "overview"}]}}
p = PL.figure_plan(SPEC, samples=10, groups=4, contrasts=6, interactions=2)
by = {r["family"]: r["files"] for r in p["rows"]}
ck("a sample-axis family multiplies by the samples", by["per_sample"] == 10, str(by))
ck("a group-axis family by the arms", by["native_per_group"] == 4, str(by))
ck("a unit-axis family by both", by["native_both"] == 14, str(by))
ck("a contrast family by the contrasts, times its ceiling", by["nativecmp_c"] == 12, str(by))
ck("an interaction family by the directions, times its ceiling", by["nativecmp_i"] == 6, str(by))
ck("a cohort family once", by["cohort_x"] == 1, str(by))
old = PL.figure_plan(SPEC, units=14, contrasts=6, cohort=1)
oby = {r["family"]: r["files"] for r in old["rows"]}
ck("without the split, a unit-axis family still counts every unit", oby["native_both"] == 14, str(oby))
ck("and the sample and group axes count the units rather than zero",
   oby["per_sample"] == 14 and oby["native_per_group"] == 14, str(oby))

if FAIL:
    print(f"\n{len(FAIL)} FAILED: " + ", ".join(FAIL))
    sys.exit(1)
print("\nthe host's panels follow the plugin, and the plan is counted per axis")
