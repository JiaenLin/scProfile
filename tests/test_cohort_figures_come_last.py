"""Design-wide panels sit at BOTH ends of the document, and the plugin says which is which.

A panel drawn over the whole design is filed under no contrast, so it answers all of them - and
walking the contrasts once collected them into whichever contrast was read first, which handed
the design-wide panels Figure 1 onwards and opened the document with the interaction, screens
before the comparisons it is computed from.

Putting all of them last was the first fix and it was half right. They are TWO groups that
happen to share a property: the totals per arm ORIENT a reader and belong first; the interaction
is the conclusion the design exists to reach and belongs last. Nothing about a panel
distinguishes them - both are unlabelled - so the plugin declares it by figure-id prefix and the
host applies whatever it is told. The host must stay ignorant of what any particular panel is,
which is what this checks by declaring made-up prefixes rather than the real ones.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import scprofile.compose as C                                              # noqa: E402

FAILURES = []


def check(ok, msg):
    if not ok:
        FAILURES.append(msg)


# Names invented for this test. If the host ever passes because it recognised a real panel name,
# it has learned about a plugin and this file is what should stop that.
BY = {("age", "fnA"): ["fig_age.png"],
      ("diet", "fnA"): ["fig_diet.png"],
      ("", "fnB"): ["zzz_opening_totals.png"],
      ("", "fnC"): ["aaa_closing_conditioned.png"]}
ROUTES = {"who_changed": ["native:fnA"],
          "what_carries_it": ["native:fnB"],
          "specificity": ["native:fnC"]}
SPEC = {"report": {"figure_position": {"zzz_opening": "overview",
                                       "aaa_closing": "conclusion"}}}

C.findings = lambda run, plugin, spec: {"age": {}, "diet": {}}
C._native_index = lambda run, plugin, spec: (BY, ROUTES, [])
C._controls = lambda run: {}
C._order = lambda f, design, controls=None: ["age", "diet"]

idx = C.figure_index("run", "plugin", spec=SPEC, design={})

want = {"fig_age.png", "fig_diet.png", "zzz_opening_totals.png", "aaa_closing_conditioned.png"}
check(set(idx) == want, "the index lost or invented a figure: %r" % (sorted(idx),))

if set(idx) == want:
    opening = idx["zzz_opening_totals.png"]
    closing = idx["aaa_closing_conditioned.png"]
    body = [idx["fig_age.png"], idx["fig_diet.png"]]
    check(opening < min(body),
          "the design-wide OVERVIEW panel is Figure %d, after a contrast at Figure %d - the "
          "reader meets a comparison before learning what the groups are" % (opening, min(body)))
    check(closing > max(body),
          "the design-wide CONCLUSION panel is Figure %d, before a contrast at Figure %d - the "
          "document answers its question before asking it" % (closing, max(body)))
    check(sorted(idx.values()) == list(range(1, len(idx) + 1)),
          "the numbers are not contiguous from 1: %r" % (sorted(idx.values()),))
    # Alphabetically the closing panel sorts FIRST and the opening one LAST, so an index that
    # happened to be ordering by name rather than by declaration would fail both checks above.

# A panel with no declared position is body, and a plugin that declares nothing still works.
w = C._positions({})
check(w("anything.png") == C.DEFAULT_POSITION,
      "an undeclared panel is not defaulting to the body of the document")
w2 = C._positions({"report": {"figure_position": {"a": "overview", "a_long": "conclusion"}}})
check(w2("a_long_x.png") == "conclusion",
      "the longer prefix did not win, so a plugin cannot state a rule and an exception together")

# THE CITATION STILL SEES EVERYTHING, whichever end a panel sits at.
both = C._figs_for(BY, ROUTES, "age", ("who_changed", "what_carries_it"), (), scope="all")
check("zzz_opening_totals.png" in both and "fig_age.png" in both,
      "a contrast can no longer cite the design-wide panel: %r" % (both,))

if FAILURES:
    print("FAIL")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("ok - overview first, contrasts in the middle, conclusion last, all by declaration")
