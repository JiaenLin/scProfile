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




def _png(path):
    import numpy as np
    from matplotlib import image as _im
    path.parent.mkdir(parents=True, exist_ok=True)
    _im.imsave(str(path), np.zeros((8, 12, 3)))


def _index(spec):
    """{plate: main figure number} and {plate: (supplementary, n, letter)} on a run invented here."""
    import shutil
    d = Path(tempfile.mkdtemp())
    try:
        run = d / "run"
        (run / "report").mkdir(parents=True)
        native = []
        for lab in ("dose", "time"):
            for stem in ("body", "perthing_one", "perthing_two", "perthing_three"):
                rel = f"kernels/p/compare/{lab}/figures/{stem}.png"
                _png(run / rel)
                native.append({"id": f"NC_{lab}_{stem}", "path": rel, "label": lab,
                               "caption": f"{lab}: {stem}."})
        (run / "report" / "panels.json").write_text(
            json.dumps({"p": {"native": native, "cohort": [], "contrast": [], "arm": []}}),
            encoding="utf-8")
        design = {"S1": {"dose": "low", "time": "early"}, "S2": {"dose": "high", "time": "late"}}
        (run / "report.json").write_text(json.dumps({"design": design,
                                                     "kernels": {"p": {"spec": spec}}}),
                                         encoding="utf-8")
        return (C.figure_index(run, "p", spec=spec, design=design),
                C.figure_panels(run, "p", spec=spec, design=design))
    finally:
        shutil.rmtree(d, ignore_errors=True)


plain, plain_p = _index({})
check(len(plain) == 8, "the fixture cannot express the failure: expected 8 numbered, got %d"
      % len(plain))
apx, apx_p = _index({"report": {"figure_position": {"perthing": C.APPENDIX}}})
check({k.rsplit("/", 1)[-1] for k in apx} == {"body.png"},
      "an `appendix` kind was numbered into the paper, or a body panel was lost: %r"
      % (sorted(apx),))
check(sorted(set(apx.values())) == [1, 2],
      "the numbers are not contiguous from 1 after a kind was withheld: %r" % (sorted(apx.values()),))
check(all(apx_p[k][0] for k in apx_p if "perthing" in k) and any("perthing" in k for k in apx_p),
      "an `appendix` kind is not in the set as a SUPPLEMENTARY figure: %r"
      % ({k.rsplit('/', 1)[-1]: v for k, v in apx_p.items()},))
keep, _ = _index({"report": {"figure_position": {"perthing": C.APPENDIX,
                                                 "perthing_two": "contrast"}}})
names = {k.rsplit("/", 1)[-1] for k in keep}
check("perthing_two.png" in names and "perthing_one.png" not in names,
      "a plugin cannot state a rule and its exception together: %r" % (sorted(names),))
# THE POSITION MAP ITSELF: a rule and its exception, longest prefix first, and the default.
w = C._positions({})
check(w("anything.png") == C.DEFAULT_POSITION, "an undeclared panel is not body by default")
w2 = C._positions({"report": {"figure_position": {"a_long": "conclusion", "a": "overview"}}})
check(w2("a_long_x.png") == "conclusion" and w2("a_x.png") == "overview",
      "the longest declared prefix does not win")

with tempfile.TemporaryDirectory() as d:
    run = Path(d)
    (run / "report.json").write_text(json.dumps({"design": {}, "kernels": {"p": {"spec": {}}}}),
                                     encoding="utf-8")
    (run / "kernels" / "p").mkdir(parents=True)
    (run / "kernels" / "p" / "WRITING_BRIEF.md").write_text("brief", encoding="utf-8")

    R.scan_set = lambda out, plugin="": ["body_of_dose.png", "perthing_one.png"]
    A._authored = lambda run_, plugin_: (False, False)

    # every figure of the set looked at; a SECOND instance of the appendix kind outstanding
    R.outstanding = lambda out, plugin="": [("perthing_two.png", "unreviewed")]
    st = {t["id"]: t["state"] for t in A.tasks(run, "p")}
    check(st.get("write") != A.BLOCKED,
          "the writing step is blocked by an instance outside the selection - one look per kind "
          "is the rule, not one per panel")

    # a figure of the set outstanding must still block it: the paper's own, or the one
    # instance of a kind the paper does not show
    for fig in ("body_of_dose.png", "perthing_one.png"):
        R.outstanding = lambda out, plugin="", fig=fig: [(fig, "unreviewed")]
        st = {t["id"]: t["state"] for t in A.tasks(run, "p")}
        check(st.get("write") == A.BLOCKED,
              f"{fig} is in the selection, unreviewed, and the writing step is not blocked")

    # AN EMPTY SELECTION IS NOT AN EMPTY GATE. A run with no figures on disk and no paper list
    # has an empty set, and intersecting against nothing would report every figure as looked
    # at and unblock the writing of a section against a paper that does not exist.
    R.scan_set = lambda out, plugin="": []
    R.outstanding = lambda out, plugin="": [("body_of_dose.png", "unreviewed")]
    st = {t["id"]: t["state"] for t in A.tasks(run, "p")}
    check(st.get("write") == A.BLOCKED,
          "an empty selection unblocked the writing step: nothing read as nothing left")

if FAILURES:
    print("FAIL")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("ok: a kind may be drawn and not written from, and the gate follows the paper")
