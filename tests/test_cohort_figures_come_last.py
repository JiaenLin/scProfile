"""A panel drawn across the whole design is numbered AFTER the contrasts it is drawn across.

A figure filed under no contrast answers all of them - which is correct, and is why
`_figs_for` folds the unlabelled panels into every contrast's evidence. But the FIGURE INDEX
walked the contrasts once and took whatever each one answered with, so the design-wide panels
were collected by whichever contrast happened to be read first and took Figure 1 onwards. The
document then opened with the question the whole design exists to answer - the interaction -
several screens before the comparisons it is computed from, and the reader walked the argument
backwards.

This is a rule about SCOPE, not about any particular panel or plugin: everything drawn for one
contrast is read first, in the design's own order; everything drawn across the design is read
after all of it. The check is behavioural - it calls `figure_index` and looks at where the
numbers land - because the defect was an ORDER, and an order is not visible in the presence of
any string.
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


CONTRAST = {"fig_age.png", "fig_diet.png"}
COHORT = {"fig_across_arms.png"}

# Two contrasts, each with a panel of its own, plus ONE panel filed under no contrast - the
# shape `_across_arms` has in a real run, where every interaction plate carries label "".
BY = {("age", "fnA"): ["fig_age.png"],
      ("diet", "fnA"): ["fig_diet.png"],
      ("", "fnB"): ["fig_across_arms.png"]}
ROUTES = {"who_changed": ["native:fnA"], "what_carries_it": ["native:fnB"]}

C.findings = lambda run, plugin, spec: {"age": {}, "diet": {}}
C._native_index = lambda run, plugin, spec: (BY, ROUTES, [])
C._controls = lambda run: {}
C._order = lambda f, design, controls=None: ["age", "diet"]

idx = C.figure_index("run", "plugin", spec=None, design={})

check(set(idx) == CONTRAST | COHORT,
      "the index lost or invented a figure: %r" % (sorted(idx),))

if set(idx) == CONTRAST | COHORT:
    last_contrast = max(idx[p] for p in CONTRAST)
    first_cohort = min(idx[p] for p in COHORT)
    check(first_cohort > last_contrast,
          "a design-wide panel is numbered Figure %d, ahead of a contrast panel at Figure %d - "
          "the document opens with the answer and shows the comparisons behind it later"
          % (first_cohort, last_contrast))
    check(sorted(idx.values()) == list(range(1, len(idx) + 1)),
          "the numbers are not contiguous from 1: %r" % (sorted(idx.values()),))

# AND THE CITING STILL SEES EVERYTHING. Moving the cohort panels later must not stop a sentence
# about one contrast from pointing at a panel drawn across the design - the numbering wants them
# apart, the citation wants them together, which is why `scope` is an argument and not a split.
both = C._figs_for(BY, ROUTES, "age", ("who_changed", "what_carries_it"), (), scope="all")
check("fig_across_arms.png" in both and "fig_age.png" in both,
      "a contrast can no longer cite the design-wide panel: %r" % (both,))
only = C._figs_for(BY, ROUTES, "age", ("who_changed", "what_carries_it"), (), scope="contrast")
check("fig_across_arms.png" not in only,
      "scope='contrast' still returns the design-wide panel: %r" % (only,))

if FAILURES:
    print("FAIL")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("ok - contrast panels first, design-wide panels after, citation still sees both")
