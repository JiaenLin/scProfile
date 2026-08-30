"""Every contrast's change on BOTH scales, written by the tool rather than computed by hand.

The numbers a result section quotes were produced by an ad-hoc script and went straight into a
manuscript's claims. This project's evidence rule forbids that: a number nobody can open is a
number nobody can check.

The reason both scales are needed is not stylistic. Where a method normalises within each object,
an element's SHARE of its arm and its RAW value answer different questions and can disagree in
sign - measured on a real cohort, five of six leading elements reversed between them, because the
arm totals differed 3.8-fold and a collapsing total makes whatever shrinks least appear to rise.
"""
import pandas as pd

from scprofile.compare_panel import arm_pairs, two_scale_table


def _design():
    return {f"S{i}": {"f1": a, "f2": b} for i, (a, b) in enumerate(
        [("lo", "p")] * 3 + [("lo", "q")] * 3 + [("hi", "p")] * 2 + [("hi", "q")] * 2)}


def _per(weights):
    """weights: {sample: {element: value}}"""
    out = {}
    for s, w in weights.items():
        out[s] = pd.DataFrame({
            "source": ["x"] * len(w), "target": ["y"] * len(w),
            "prob": list(w.values()), "group": list(w),
        })
    return out


def test_it_reports_both_scales_for_every_contrast():
    d = _design()
    per = _per({s: {"A": 1.0, "B": 2.0} for s in d})
    rows = two_scale_table(per, d, arm_pairs(d), group_col="group")
    assert rows
    for r in rows:
        for k in ("raw_delta", "share_delta_pp", "total_from", "total_to", "scales_agree"):
            assert k in r, k


def test_a_sign_disagreement_between_scales_is_marked():
    """THE CASE THE TABLE EXISTS FOR: an element that falls in absolute terms while its share rises.

    Element A falls from 10 to 6 while the arm total collapses from 110 to 16, so A's share goes
    from 9% to 37%. The raw change is negative and the share change is positive.
    """
    d = _design()
    per = {}
    for s, row in d.items():
        if row["f1"] == "lo":
            per[s] = _per({s: {"A": 10.0, "B": 100.0}})[s]
        else:
            per[s] = _per({s: {"A": 6.0, "B": 10.0}})[s]
    rows = two_scale_table(per, d, arm_pairs(d), group_col="group")
    a = [r for r in rows if r["element"] == "A" and r["contrast"] == "f1"]
    assert a, "the marginal contrast on f1 is missing"
    r = a[0]
    # DIRECTION-AGNOSTIC ON PURPOSE. Which level is `from` is `arm_pairs`' business, and an
    # earlier version of this test asserted a sign after assuming the order - so it failed on a
    # correct table. What matters is that the two scales point OPPOSITE ways.
    assert r["raw_delta"] * r["share_delta_pp"] < 0, (
        f"raw and share should disagree in sign here: {r}")
    assert r["scales_agree"] is False, "a sign disagreement was not marked"


def test_agreement_is_marked_when_both_move_together():
    d = _design()
    per = {}
    for s, row in d.items():
        per[s] = _per({s: {"A": 10.0 if row["f1"] == "lo" else 2.0, "B": 10.0}})[s]
    rows = two_scale_table(per, d, arm_pairs(d), group_col="group")
    a = [r for r in rows if r["element"] == "A" and r["contrast"] == "f1"][0]
    assert a["raw_delta"] * a["share_delta_pp"] > 0, a
    assert a["scales_agree"] is True


def test_the_arm_totals_are_carried_so_a_reader_can_see_the_denominator():
    d = _design()
    per = _per({s: {"A": 1.0} for s in d})
    r = two_scale_table(per, d, arm_pairs(d), group_col="group")[0]
    assert r["total_from"] > 0 and r["total_to"] > 0


def test_no_group_column_is_not_a_crash():
    d = _design()
    per = {s: pd.DataFrame({"source": ["x"], "target": ["y"], "prob": [1.0]}) for s in d}
    assert two_scale_table(per, d, arm_pairs(d), group_col="group") == []


if __name__ == "__main__":
    import sys
    bad = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  ok   {name}")
            except AssertionError as e:
                bad += 1
                print(f"  FAIL {name}: {str(e)[:160]}")
    sys.exit(1 if bad else 0)
