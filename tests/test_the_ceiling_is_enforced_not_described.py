"""A declared ceiling has to stop the drawing, not describe it.

`at_most` was read by the planner and by NOTHING ELSE. The two ceilings one real plugin honoured
were literals transcribed into its embedded R by hand, so the declaration described the execution
instead of governing it - and the plan it feeds was true only while somebody kept two numbers in
step. A plan that can drift silently from the run it predicts is worth nothing.

Two halves, because the host can only stop what it writes itself:

  where the host writes the figure, it REFUSES past the ceiling;
  where the wrapped tool writes into its own graphics device, the file is on disk before the
  host sees it, so the run is held against the declaration afterwards and a family that exceeded
  it fails `capacity --promised`.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scprofile import planner as PL                                       # noqa: E402
from scprofile.plugin import _ceiling_for                                 # noqa: E402

FAILURES = []


def check(ok, msg):
    if not ok:
        FAILURES.append(msg)


# ---- the writer's guard ---------------------------------------------------------------------
CEIL = {"thing": 2, "thing_special": 5}
check(_ceiling_for(CEIL, "thing_one") == ("thing", 2),
      "the family's ceiling was not found for a figure that belongs to it")
check(_ceiling_for(CEIL, "thing_special_x") == ("thing_special", 5),
      "the longer prefix did not win, so a family cannot be bounded with one member excepted")
check(_ceiling_for(CEIL, "unrelated") is None,
      "a figure no ceiling covers was given one")
check(_ceiling_for({}, "thing_one") is None, "an undeclared plugin acquired a ceiling")
check(_ceiling_for({"thing": "not a number"}, "thing_one") is None,
      "a ceiling that is not a number was enforced anyway")

# ---- the run held against the declaration ----------------------------------------------------
SPEC = {"native_plots": {"fn": {"use": "figures/perpair__<item>.png", "at_most": 2},
                         "fnOk": {"use": "figures/fine__<item>.png", "at_most": 3}},
        "report": {"figure_axis": {"perpair": "contrast", "fine": "contrast"}}}

paths = ([f"cmp/A/figures/perpair__{i}.png" for i in range(5)]      # over, in one contrast
         + [f"cmp/B/figures/perpair__{i}.png" for i in range(2)]    # exactly at the ceiling
         + [f"cmp/A/figures/fine__{i}.png" for i in range(3)]       # a bounded family that is ok
         + ["cmp/A/figures/unrelated.png"])                          # covered by no declaration
over = PL.over_ceiling(SPEC, paths)
check([(f, d, n, c) for f, d, n, c in over] == [("perpair", "cmp/A/figures", 5, 2)],
      f"the wrong families were reported over their ceiling: {over}")

# PER OCCURRENCE OF THE AXIS, NOT PER RUN. Summing the two contrasts to 7 and comparing that
# against 2 would report every bounded family in every design as over-drawn.
check(not [r for r in over if r[1].endswith("B/figures")],
      "a contrast that stayed within its ceiling was reported as exceeding it")

# AND THE CHECK MUST BE ABLE TO PASS. A fixture where everything is over the line passes for an
# implementation that reports every family it sees.
check(PL.over_ceiling(SPEC, [f"cmp/B/figures/perpair__{i}.png" for i in range(2)]) == [],
      "a run inside every ceiling was still reported as over one")

if FAILURES:
    print("FAIL")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("ok: the ceiling stops the writer, and the run is held against it where it cannot")
