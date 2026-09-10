"""How many figures a run will draw, from the design and the declaration, with no run.

`planner.result_spec` has been able to say what a result should CONTAIN since it was written, and
its docstring is emphatic that no run is required. Its only caller builds a page out of a
FINISHED run, so it was always read after the compute it was meant to inform - and it consults
one field, `report.unit_network`, which is the host's own panels: 84 files of 1187 on a real
cohort. Nothing looked at the plugin's own inventory before a job was submitted, and nobody could
have known that plugin would draw 1187 figures without running it.

A specification a reader can argue with is not the same as a number that can look wrong.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scprofile import planner as PL                                       # noqa: E402

FAILURES = []


def check(ok, msg):
    if not ok:
        FAILURES.append(msg)


# Invented families: a planner that passed by recognising a real panel name would fail here.
SPEC = {"native_plots": {
            "fnPerUnit": {"use": "figures/perunit_thing.png", "at_most": 2},
            "fnPerPair": {"use": "figures/percontrast__<item>.png", "at_most": 12},
            "fnBoth": {"use": "figures/perunit_two__<x>.png and figures/percontrast_two__<y>.png",
                       "at_most": {"perunit_two": 1, "percontrast_two": 6}},
            "fnCohort": {"use": "figures/wholedesign_x.png", "at_most": 3},
            "fnSkipped": {"skip": "not_applicable", "use": "figures/never.png"},
            "fnTable": {"use": "tables/numbers.csv"}},
        "report": {
            "figures": [{"id": "OWN1"}, {"id": "OWN2"}],
            "figure_axis": {"perunit": "unit", "percontrast": "contrast",
                            "wholedesign": "cohort", "OWN1": "unit", "OWN2": "unit"},
            "figure_position": {"perunit": "appendix", "percontrast": "contrast",
                                "wholedesign": "overview", "OWN1": "contrast",
                                # a plate the plugin draws ITSELF and no result is written from:
                                # the only combination in which the appendix rule decides anything
                                "OWN2": "appendix"}}}

p = PL.figure_plan(SPEC, units=10, contrasts=6, cohort=1)
by = {r["family"]: r for r in p["rows"]}

check(by["perunit_thing"]["files"] == 20, "a per-unit ceiling did not multiply by the units")
check(by["percontrast"]["files"] == 72, "a per-contrast ceiling did not multiply by the pairs")
check(by["wholedesign_x"]["files"] == 3, "a cohort family was multiplied by something")

# A CEILING PER FAMILY, because one upstream entry can name several. Declared as one number,
# `netVisual_aggregate` bounded both its families at 6 and over-counted the per-unit one by 90.
check(by["perunit_two"]["files"] == 10 and by["percontrast_two"]["files"] == 36,
      f"a per-family ceiling was not read: {by['perunit_two']}, {by['percontrast_two']}")

# A SKIPPED ENTRY DRAWS NOTHING, and a `use:` naming a table is not a figure.
check("never" not in by and "numbers" not in by, f"skipped or non-figure entries counted: {sorted(by)}")

# THE VECTOR COPY IS ONLY POSSIBLE WHERE THE HOST WRITES THE FIGURE. An upstream plot arrives as
# a PNG from the wrapped tool's own device and there is no vector to write; counting one for
# every family overstated one cohort by 171 files that were never going to exist.
check(by["percontrast"]["vector"] == 0,
      "an upstream family was given a vector copy it cannot have")
check(by["OWN1"]["vector"] == 10, "a plugin-drawn family the paper cites lost its vector copy")
check(by["OWN2"]["vector"] == 0,
      "a plugin-drawn family placed `appendix` still got a vector copy - the 180 files on one "
      "cohort this exists to stop")
check(by["OWN2"]["files"] == 10, "an appendix family stopped being drawn; it is not hidden")

# THE TOTAL IS THE SUM, and it is what a person actually reads.
check(p["total"] == p["files"] + p["vector"], "the total does not add up")
check(p["files"] == 20 + 72 + 3 + 10 + 36 + 10 + 10, f"the total is wrong: {p['files']}")

# A FAMILY WITH NO CEILING COUNTS AS ONE, so the number is a floor and never silently zero.
nocap = PL.figure_plan({"native_plots": {"f": {"use": "figures/x_y.png"}},
                        "report": {"figure_axis": {"x_": "unit"}}}, units=7, contrasts=0)
check(nocap["files"] == 7, f"an unbounded family did not count as one per axis: {nocap['files']}")

if FAILURES:
    print("FAIL")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("ok: the figure count is computable from the design and the declaration, with no run")
