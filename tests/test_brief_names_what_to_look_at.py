"""The writing brief marks the figures nobody has looked at, and says so loudly if it cannot.

The brief's list of figures is the mechanism that makes looking a STEP rather than advice. If
it silently marks nothing, it reads as "everything has been reviewed" and the step is skipped by
an agent doing exactly as it was told.

That is what happened: `review.outstanding()` returns `(path, state)` PAIRS, the brief
stringified them into `"('a.png', 'unreviewed')"` and compared that against a path, so on a run
where not one figure had been opened it marked zero as outstanding. Wrapped in
`except Exception: pass`, so it could not report its own breakage either.

Checked behaviourally - the brief is built against a stubbed ledger and the output is read -
because the defect was a silently empty set, which is invisible in the presence of any string.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import scprofile.brief as B                                               # noqa: E402
import scprofile.compose as C                                            # noqa: E402
import scprofile.review as R                                             # noqa: E402

FAILURES = []


def check(ok, msg):
    if not ok:
        FAILURES.append(msg)


IDX = {"figures/looked_at.png": 1, "figures/never_opened.png": 2}

C.findings = lambda run, plugin, spec: {"age": {"ratio": 2.0, "reference": "y", "against": "a",
                                                "ratio_per_cell": 1.5, "n_significant": 3,
                                                "n_tested": 4}}
C.figure_index = lambda run, plugin, spec=None, design=None: IDX
# THE CONTROLS COVER THE DESIGN'S OWN FACTORS. The stub named a factor the fixture design does
# not have, so the reference-level clause rendered empty and the check for it failed on correct
# code - a fixture that does not match its own design tests nothing about the design.
C._controls = lambda run: {"age": "y", "f1": "a", "f2": "x"}
C._order = lambda f, design, controls=None: ["age"]
# ONE reviewed, ONE not - so an implementation that marks all or none fails either way.
R.outstanding = lambda out, plugin="": [("figures/never_opened.png", "unreviewed")]

import tempfile                                                          # noqa: E402

with tempfile.TemporaryDirectory() as d:
    # A DESIGN WITH TWO FACTORS THAT SPLIT THE SAMPLES IDENTICALLY, and an upstream constraint.
    # Both are things the run holds and the brief used not to pass on.
    _design = {"s1": {"f1": "a", "f2": "x"}, "s2": {"f1": "a", "f2": "x"},
               "s3": {"f1": "b", "f2": "y"}, "s4": {"f1": "b", "f2": "y"}}
    import json as _json
    (Path(d) / "report.json").write_text(_json.dumps({
        "constraint_on_use": "no abundance claim across f1 or f2 may be made from this object",
        "constraint_binds": {"abundance": ["f1", "f2"]}}), encoding="utf-8")
    p = B.write_brief(d, "plug", spec={"report": {"subject": "widgets"}}, design=_design)
    check(p is not None, "the brief was not written at all")
    if p:
        txt = Path(p).read_text(encoding="utf-8")
        never = [l for l in txt.splitlines() if "never_opened.png" in l]
        looked = [l for l in txt.splitlines() if "looked_at.png" in l]
        check(bool(never) and "not yet looked at" in never[0],
              "a figure nobody has opened is not marked as outstanding, so the brief reads as "
              "though everything had been reviewed: %r" % (never,))
        check(bool(looked) and "not yet looked at" not in looked[0],
              "a figure that HAS been reviewed is marked outstanding, so the mark means nothing")

    # THE SET IS ALSO WRITTEN AS A TRANSFER LIST, because under a scheduler the figures are on
    # the cluster and the agent's viewer is not. With only the markdown to work from, an agent
    # writes a throwaway parser to get the paths out - the in-house script this tool exists to
    # make unnecessary. One run-relative path per line is what rsync --files-from and tar -T
    # already take.
    if p:
        fl = Path(p).parent / B.FIGURE_LIST
        check(fl.is_file(), "no transfer list beside the brief, so the figure set cannot be "
                            "moved to wherever the agent opens images without parsing markdown")
        if fl.is_file():
            lines = [x for x in fl.read_text(encoding="utf-8").splitlines() if x.strip()]
            check(all(not x.startswith("/") for x in lines),
                  "the transfer list holds absolute paths, which no --files-from can use "
                  "against a remote run root: %r" % (lines[:3],))
            named = {l.split("`")[1] for l in txt.splitlines()
                     if l.startswith("- Figure ") and "`" in l}
            check(set(lines) == named,
                  "the transfer list and the brief name different figures, so moving the list "
                  "brings across a set the document does not describe: %r"
                  % sorted(set(lines) ^ named))

    # WHAT THE DESIGN FORBIDS MUST REACH THE AUTHOR, AND BEFORE THE CONTRASTS.
    #
    # The brief once carried none of it. The run held the upstream constraint and the aliased
    # factors; the brief listed contrasts and figures. A result section was then written that led
    # with an aliased factor's main effect and mentioned the confound once, at the end, in
    # limitations - which is the order the brief gave. A constraint that arrives after the
    # argument is written reorders nothing.
    if p:
        _t = Path(p).read_text(encoding="utf-8")
        _head = _t.split("## The contrasts", 1)[0]
        ck2 = lambda name, cond: check(cond, name)
        # THE DESIGN COMES FIRST, AS BIOLOGY. Every input to the writing used to be the run
        # describing itself, so the section that came back described the run: it reported which
        # quantity moved and never said what a move in it MEANS, and it treated the factors as
        # labels on a contrast table rather than as the interventions the experiment performed.
        ck2("the brief does not state the design it resolved",
            "design this run resolved" in _t)
        ck2("the design is not stated BEFORE the contrasts", "design this run resolved" in _head)
        ck2("the factors and their levels are not named", "`f1`" in _head and "`a`" in _head)
        ck2("the reference level is not named as what a contrast asks",
            "goes from" in _head)
        ck2("the interaction is not named as the reason the design was crossed",
            "crossed rather than run as two separate" in _head)
        ck2("the marginals are not placed after the simple effects",
            "read AFTER the simple effects" in _head)
        ck2("the brief does not ask for the factors to be written as interventions",
            "as the interventions they are" in _head)
        ck2("and does not ask what the change MEANS in the field's language",
            "in the language of the field" in _head)
        # THE CAVEATS ARE A FOOTNOTE, NOT THE FRAME. The first version of this block opened the
        # brief and the section that came back led with its caveats and never said the biology.
        ck2("what the design cannot separate is missing",
            "cannot separate" in _t and "aliased with" in _t)
        ck2("it is placed before the contrasts, where it becomes the frame",
            "cannot separate" not in _head)
        ck2("and it does not warn against leading with caveats",
            "has not reported anything" in _t)

    # A LEDGER THAT CANNOT BE READ MUST SAY SO, not quietly mark nothing.
    def _boom(out, plugin=""):
        raise RuntimeError("ledger unreadable")

    R.outstanding = _boom
    p2 = B.write_brief(d, "plug2", spec={"report": {"subject": "widgets"}}, design={})
    if p2:
        t2 = Path(p2).read_text(encoding="utf-8")
        check("could not be read" in t2 and "unreviewed" in t2,
              "the brief swallowed a broken review ledger instead of warning that nothing is "
              "marked")

if FAILURES:
    print("FAIL")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("ok - outstanding figures are marked, reviewed ones are not, and a broken ledger says so")
