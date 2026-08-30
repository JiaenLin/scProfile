"""What a result should contain, resolved from the design table and the plugin declaration.

DESIGN IS DECOUPLED FROM EXECUTION. Until this existed the only way to learn what a result should
hold was to run the profile and look at what came out, which put a compute job between a person
and every design decision, and made a missing figure discoverable only when somebody noticed they
could not write a sentence. Nothing in this file runs a profile or reads a run directory.

The enumeration is not written for a 2x2 or for any project. These tests check that it FOLLOWS
from the design table - by giving it designs of other shapes and asserting the count the rules
imply.
"""
import importlib.util
from pathlib import Path

from scprofile.design_panel import comparisons
from scprofile.planner import result_spec, spec_text

ROOT = Path(__file__).resolve().parents[1]


def _plugin(name="cellchat"):
    sp = importlib.util.spec_from_file_location(name, ROOT / "kernels" / f"{name}.py")
    m = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    return m.PLUGIN


def _factorial(**levels):
    """A balanced design table over the named factors, two samples per cell."""
    import itertools
    keys = list(levels)
    rows, n = {}, 0
    for combo in itertools.product(*(levels[k] for k in keys)):
        for _ in range(2):
            n += 1
            rows[f"S{n}"] = dict(zip(keys, combo))
    return rows


def test_a_two_by_two_gives_two_marginals_four_simples_and_one_interaction():
    """The seven questions a 2x2 supports, counted from the rules rather than listed."""
    cs = comparisons(_factorial(age=["aged", "young"], diet=["HFD", "chow"]))
    kinds = [c["kind"] for c in cs]
    assert kinds.count("marginal") == 2, kinds
    assert kinds.count("simple") == 4, kinds
    assert kinds.count("interaction") == 1, kinds


def test_a_one_factor_design_has_no_simple_effects_and_no_interaction():
    cs = comparisons(_factorial(genotype=["wt", "ko"]))
    kinds = [c["kind"] for c in cs]
    assert kinds == ["marginal"], kinds


def test_three_factors_follow_the_same_rules():
    """3 marginals, 3x2x2 = 12 simples, and 3 pairwise interactions - same code, no special case."""
    cs = comparisons(_factorial(a=["a1", "a2"], b=["b1", "b2"], c=["c1", "c2"]))
    kinds = [c["kind"] for c in cs]
    assert kinds.count("marginal") == 3, kinds
    assert kinds.count("simple") == 12, kinds
    assert kinds.count("interaction") == 3, kinds


def test_every_simple_effect_names_the_stratum_it_is_within():
    cs = comparisons(_factorial(age=["aged", "young"], diet=["HFD", "chow"]))
    for c in cs:
        if c["kind"] == "simple":
            assert c["stratum"], "a simple effect with no stratum is a marginal effect"
            assert c["other"] in c["stratum"], c


def test_an_unbalanced_cell_is_not_reported_as_an_interaction():
    """A missing cell is a gap in the design, not an interaction to draw."""
    d = _factorial(age=["aged", "young"], diet=["HFD", "chow"])
    for s, row in list(d.items()):
        if row["age"] == "young" and row["diet"] == "chow":
            del d[s]
    kinds = [c["kind"] for c in comparisons(d)]
    assert "interaction" not in kinds, "an interaction was offered over an empty cell"


def test_an_aliased_factor_is_named_as_unanswerable():
    """Age and chemistry splitting the samples identically is one question drawn twice."""
    d = _factorial(age=["aged", "young"], diet=["HFD", "chow"])
    for s, row in d.items():
        row["chemistry"] = "V2" if row["age"] == "aged" else "V3"
    cs = comparisons(d)
    age = [c for c in cs if c["kind"] == "marginal" and c["factor"] == "age"]
    assert age and "chemistry" in age[0]["aliased_with"], age


def test_the_spec_needs_no_run_directory():
    """Not one path is read. The specification exists before anything is scheduled."""
    secs = result_spec(_factorial(age=["aged", "young"], diet=["HFD", "chow"]), _plugin())
    assert len(secs) == 8, [s["kind"] for s in secs]
    assert secs[0]["kind"] == "cohort", "the object is described before it is compared"
    assert all(s["panels"] for s in secs), "a question with no panel proposed is not specified"


def test_every_proposed_panel_says_what_it_does_not_establish():
    secs = result_spec(_factorial(age=["aged", "young"], diet=["HFD", "chow"]), _plugin())
    for s in secs:
        for p in s["panels"]:
            assert p["establishes"] and p["does_not_establish"], (s["kind"], p["kind"])


def test_a_plugin_declaring_no_network_answers_no_contrast_and_says_why():
    """The plugin's own declaration decides what it can support - not a run's output."""
    secs = result_spec(_factorial(age=["aged", "young"], diet=["HFD", "chow"]),
                       {"report": {}})
    contrast = [s for s in secs if s["kind"] in ("marginal", "simple", "interaction")]
    assert contrast, "the design still poses the questions"
    for s in contrast:
        for p in s["panels"]:
            assert not p["available"], p
            assert "unit_network" in p["unavailable_because"], p


def test_the_text_form_carries_the_questions_and_the_caveats():
    txt = spec_text(result_spec(_factorial(age=["aged", "young"], diet=["HFD", "chow"]),
                                _plugin()))
    assert "does NOT establish" in txt
    assert "Q:" in txt
    assert "interaction" in txt.lower()


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
                print(f"  FAIL {name}: {e}")
    sys.exit(1 if bad else 0)
