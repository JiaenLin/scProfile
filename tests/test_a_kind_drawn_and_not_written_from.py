"""A plugin can say a figure kind is drawn and no result is written from it, and the writing
step waits only on the figures the paper is written from.

WHAT THIS COST. One cohort drew 1187 figures of 81 kinds - a circle plot per unit, a chord
diagram per pathway per contrast, 72 of that one kind. Every figure gated the result section, so
writing 24 claims meant opening 1019 images; 50 of the 81 kinds are cited by no sentence the
composer writes. `review.shards` had said for as long as it had existed that "the brief's list
holds the ones the PAPER is written from, which is a smaller set and the one the writing step
actually blocks on" - and the agenda gated on every panel drawn. The behaviour and the sentence
describing it were written by the same hand and never compared.

The host stays ignorant of what any particular panel is: the prefixes below are invented, so a
host that passed by recognising a real cellchat panel would fail here.
"""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import scprofile.agenda as A                                              # noqa: E402
import scprofile.compose as C                                            # noqa: E402
import scprofile.review as R                                             # noqa: E402

FAILURES = []


def check(ok, msg):
    if not ok:
        FAILURES.append(msg)


BY = {("age", "fnA"): ["body_of_age.png"],
      ("diet", "fnA"): ["body_of_diet.png"],
      ("age", "fnB"): ["perthing_one.png", "perthing_two.png", "perthing_three.png"]}
ROUTES = {"who_changed": ["native:fnA"], "what_carries_it": ["native:fnB"]}

C.findings = lambda run, plugin, spec: {"age": {}, "diet": {}}
C._native_index = lambda run, plugin, spec: (BY, ROUTES, [])
C._controls = lambda run: {}
C._order = lambda f, design, controls=None: ["age", "diet"]

# ---- the declaration removes a kind from the numbering, and only that kind ------------------
plain = C.figure_index("run", "p", spec={}, design={})
check(len(plain) == 5, "the fixture cannot express the failure: expected 5 numbered, got %d"
      % len(plain))

apx = C.figure_index("run", "p", spec={"report": {"figure_position": {"perthing": C.APPENDIX}}},
                     design={})
check(set(apx) == {"body_of_age.png", "body_of_diet.png"},
      "an `appendix` kind was numbered into the paper, or a body panel was lost: %r"
      % (sorted(apx),))
check(sorted(apx.values()) == [1, 2],
      "the numbers are not contiguous from 1 after a kind was withheld: %r" % (sorted(apx.values()),))

# THE LONGEST PREFIX STILL WINS, so a plugin can withhold a family and keep one member of it.
keep = C.figure_index("run", "p", spec={"report": {"figure_position": {
    "perthing": C.APPENDIX, "perthing_two": "contrast"}}}, design={})
check("perthing_two.png" in keep and "perthing_one.png" not in keep,
      "a plugin cannot state a rule and its exception together: %r" % (sorted(keep),))

# ---- the writing step waits on the ONE SELECTION, not on every panel drawn -----------------
# The set is `review.scan_set` (harness ADR-0017): the paper's figures plus one instance of
# every kind the paper does not show. A second instance of an appendix kind is outside it and
# blocks nothing; the paper's own figures, and the one instance of an uncited kind, do.
with tempfile.TemporaryDirectory() as d:
    run = Path(d)
    (run / "report.json").write_text(json.dumps({"design": {}, "kernels": {"p": {"spec": {}}}}),
                                     encoding="utf-8")
    (run / "kernels" / "p").mkdir(parents=True)
    (run / "kernels" / "p" / "WRITING_BRIEF.md").write_text("brief", encoding="utf-8")

    R.scan_set = lambda out, plugin="": ["body_of_age.png", "perthing_one.png"]
    A._authored = lambda run_, plugin_: (False, False)

    # every figure of the set looked at; a SECOND instance of the appendix kind outstanding
    R.outstanding = lambda out, plugin="": [("perthing_two.png", "unreviewed")]
    st = {t["id"]: t["state"] for t in A.tasks(run, "p")}
    check(st.get("write") != A.BLOCKED,
          "the writing step is blocked by an instance outside the selection - one look per kind "
          "is the rule, not one per panel")

    # a figure of the set outstanding must still block it: the paper's own, or the one
    # instance of a kind the paper does not show
    for fig in ("body_of_age.png", "perthing_one.png"):
        R.outstanding = lambda out, plugin="", fig=fig: [(fig, "unreviewed")]
        st = {t["id"]: t["state"] for t in A.tasks(run, "p")}
        check(st.get("write") == A.BLOCKED,
              f"{fig} is in the selection, unreviewed, and the writing step is not blocked")

    # AN EMPTY SELECTION IS NOT AN EMPTY GATE. A run with no figures on disk and no paper list
    # has an empty set, and intersecting against nothing would report every figure as looked
    # at and unblock the writing of a section against a paper that does not exist.
    R.scan_set = lambda out, plugin="": []
    R.outstanding = lambda out, plugin="": [("body_of_age.png", "unreviewed")]
    st = {t["id"]: t["state"] for t in A.tasks(run, "p")}
    check(st.get("write") == A.BLOCKED,
          "an empty selection unblocked the writing step: nothing read as nothing left")

if FAILURES:
    print("FAIL")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("ok: a kind may be drawn and not written from, and the gate follows the paper")
