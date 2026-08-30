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


# ---------------------------------------------------------------------------------------------
# THE MERGE MUST BE PRECEDED BY AN ALIGNMENT, and this is checked in the source because the
# failure it guards is INVISIBLE at runtime.
#
# A tool that subtracts two per-arm matrices by position gives three outcomes when the arms
# carry different groups: an error, a silently misaligned figure, or a correct one - and the
# middle one was observed on two of four contrasts in a real run, comparing one population
# against a different one with nothing on the page to say so. A test that only ran the code
# would have seen a PNG appear and passed.
def _check_alignment_precedes_merge():
    import re
    from pathlib import Path as _P
    bad = []
    for f in sorted((_P(__file__).resolve().parent.parent / "kernels").glob("*.py")):
        src = f.read_text()
        for m in re.finditer(r'_R_COMPARE\s*=\s*r?"""(.*?)"""', src, re.S):
            body = m.group(1)
            merge = re.search(r"^\s*\w+\s*<-\s*merge\w*\(", body, re.M)
            if not merge:
                continue
            # COMMENTS STRIPPED FIRST. The first version of this check searched the raw text
            # and was satisfied by the word "align" in a comment banner - a prose gate wearing a
            # code gate's clothes, which is the exact failure mode it exists to catch.
            head = "\n".join(re.sub(r"#.*$", "", ln) for ln in body[:merge.start()].split("\n"))
            if not re.search(r"\b(lift\w*|union|intersect)\s*\(", head):
                bad.append(f"{f.name}: merges two objects with no alignment before it")
            if "identical(levels" not in body and "stopifnot" not in body:
                bad.append(f"{f.name}: nothing asserts the two objects agree after alignment")
    return bad


_bad = _check_alignment_precedes_merge()
if _bad:
    print("FAIL")
    for b in _bad:
        print("  -", b)
    raise SystemExit(1)
print("ok: every compare block aligns its objects before merging, and asserts it")


# ---------------------------------------------------------------------------------------------
# AN R SCRIPT THAT BRIDGES TO PYTHON MUST PIN THE INTERPRETER, and pin it from R.home().
#
# reticulate, left alone, provisions its own interpreter in a uv cache. That interpreter has none
# of the packages the plugin's environment was built with, so a call that needs one fails with a
# message telling you to install a package that IS ALREADY INSTALLED - measured here as "Cannot
# find UMAP, please install through pip" with umap-learn 0.5.12 two directories away. It took out
# five plot functions at once and read exactly like a missing dependency.
#
# `Sys.which("python")` does not fix it: it depends on PATH and returned /bin/python when
# measured. R.home() is where R actually is, so the environment is its parent, and that holds
# however the script was launched.
def _check_python_bridge_is_pinned():
    import re
    from pathlib import Path as _P
    bad = []
    for f in sorted((_P(__file__).resolve().parent.parent / "kernels").glob("*.py")):
        src = f.read_text()
        for m in re.finditer(r'_R_[A-Z]+\s*=\s*r?(?:"""|\'\'\')(.*?)(?:"""|\'\'\')', src, re.S):
            body = m.group(1)
            uses_python = re.search(r"reticulate|umap\.method|py_install|import_from_path", body)
            if not uses_python:
                continue
            if "RETICULATE_PYTHON" not in body:
                bad.append(f"{f.name}: an R block reaches Python but never pins "
                           f"RETICULATE_PYTHON")
            elif "R.home()" not in body:
                bad.append(f"{f.name}: RETICULATE_PYTHON is set from something other than "
                           f"R.home(); PATH-based lookups resolve to the system python")
    return bad


_bad2 = _check_python_bridge_is_pinned()
if _bad2:
    print("FAIL")
    for b in _bad2:
        print("  -", b)
    raise SystemExit(1)
print("ok: every R block that reaches Python pins its interpreter from R.home()")
