"""Every plot the wrapped tool ships is used or accounted for, and the excuses are a closed set.

Asked which of a wrapped tool's 29 plotting functions a plugin used, the answer was ONE. The
other 28 were explained away with four reasons, three of which are not reasons: "reimplemented",
"never considered", "dependency missing". Prose cannot stop that - a free-text field accepts any
sentence - so the vocabulary is closed and those three are rejected by name.
"""
from scprofile import native as N


def test_the_three_excuses_are_rejected_by_name():
    for bad in ("reimplemented", "not_considered", "dependency_missing"):
        assert bad in N.REJECTED, bad
        _u, _s, p = N.account(["f"], {"f": {"skip": bad}})
        assert p and "REJECTED" in p[0][1], (bad, p)


def test_a_rejection_carries_the_remedy_not_just_a_refusal():
    _u, _s, p = N.account(["f"], {"f": {"skip": "reimplemented"}})
    assert "superseded_by_design" in p[0][1], "the rejection does not say what to do instead"


def test_every_valid_reason_demands_checkable_evidence():
    for reason, (_what, needs, _help) in N.VALID.items():
        assert needs, f"{reason} can be claimed with no evidence at all"
        _u, _s, p = N.account(["f"], {"f": {"skip": reason}})
        assert p, f"{reason} was accepted with none of {needs} supplied"


def test_not_applicable_needs_evidence_and_then_passes():
    _u, s, p = N.account(["netVisual_spatial"],
                         {"netVisual_spatial": {"skip": "not_applicable",
                                                "evidence": "the object carries no coordinates"}})
    assert s and not p, p


def test_superseded_needs_both_a_panel_and_a_named_defect():
    d = {"f": {"skip": "superseded_by_design", "panel": "N1_circle"}}
    _u, _s, p = N.account(["f"], d)
    assert p, "a supersession was accepted without naming the defect it corrects"
    d["f"]["defect"] = "the upstream scales each facet to its own maximum"
    _u, s2, p2 = N.account(["f"], d)
    assert s2 and not p2, p2


def test_an_unlisted_function_is_a_problem_not_a_silent_pass():
    """The accounting is exhaustive or it is a sample of the ones somebody remembered."""
    _u, _s, p = N.account(["a", "b"], {"a": {"use": "F1"}})
    assert any(fn == "b" and "UNACCOUNTED" in why for fn, why in p), p


def test_a_declaration_for_a_function_the_tool_does_not_export_is_flagged():
    _u, _s, p = N.account(["a"], {"a": {"use": "F1"}, "ghost": {"use": "F2"}})
    assert any(fn == "ghost" for fn, _w in p), p


def test_using_it_is_the_default_path_and_needs_only_where():
    u, _s, p = N.account(["a"], {"a": {"use": "F4_network"}})
    assert u == {"a": "F4_network"} and not p


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


def _all_specs():
    import importlib.util
    from pathlib import Path
    out = {}
    for f in sorted((Path(__file__).resolve().parents[1] / "kernels").glob("*.py")):
        sp = importlib.util.spec_from_file_location(f.stem, f)
        m = importlib.util.module_from_spec(sp)
        try:
            sp.loader.exec_module(m)
        except Exception:                                                 # noqa: BLE001
            continue
        out[f.stem] = getattr(m, "PLUGIN", {})
    return out


def test_a_plugin_that_wraps_a_tool_owes_an_accounting():
    assert N.requires_accounting({"wraps": {"tool": "SomeTool"}})
    assert not N.requires_accounting({})


def test_the_debt_is_a_RATCHET_and_may_only_shrink():
    """A new wrapper arriving with no accounting is a regression; the named ones are known debt.

    This is what locks the practice. Without it, 'list the tool's plots and use them' is advice,
    and advice is followed until somebody is in a hurry.
    """
    owing, unexpected = N.accounting_debt(_all_specs())
    assert not unexpected, (
        "a plugin wraps a tool and does not account for its plots, and is not on the known-debt "
        f"list: {unexpected}. Either declare native_plots for it, or - if the debt is genuinely "
        "being taken on - add it to OWES_ACCOUNTING with that decision recorded.")
    stale = [n for n in N.OWES_ACCOUNTING if n not in owing]
    assert not stale, (
        f"these paid their debt but are still listed as owing it: {stale}. Remove them from "
        "OWES_ACCOUNTING so the ratchet keeps its meaning.")


def test_the_plugin_that_paid_is_no_longer_on_the_list():
    assert "cellchat" not in N.OWES_ACCOUNTING, (
        "cellchat declares native_plots; leaving it on the debt list makes the list a decoration")
