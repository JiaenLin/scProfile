"""A comparison is drawn on populations BOTH arms have, and the rest are removed at SOURCE.

The union was drawn first, with a missing population's row and column hatched so a reader could
see it was absent. Honest, and still the wrong panel: on a real cohort it put two full rows and
two full columns of hatch through the middle of a 13x13 matrix - 48 of 169 cells, 28% of the
figure - carrying no comparison and breaking every real block in half.

The rule this locks: a cell that cannot hold a comparison is not drawn where comparisons are
read. The removal happens before the matrix is built, and what is removed is NAMED.
"""
import pandas as pd

from scprofile.compare_panel import contrast_populations


def _edges(pairs):
    return pd.DataFrame({"source": [a for a, _ in pairs],
                         "target": [b for _, b in pairs],
                         "weight": [1.0] * len(pairs)})


def test_the_set_is_the_intersection():
    aged = _edges([("cm", "fib"), ("fib", "endo"), ("neural", "cm")])
    young = _edges([("cm", "fib"), ("fib", "endo")])
    keep, dropped = contrast_populations({"aged": aged, "young": young})
    assert keep == ["cm", "endo", "fib"], keep
    assert "neural" not in keep, "a population absent from one arm is still on the axis"


def test_what_is_removed_is_named_with_the_arm_that_lacked_it():
    """A removal is only cheap when the thing removed is named."""
    aged = _edges([("cm", "fib"), ("neural", "cm")])
    young = _edges([("cm", "fib"), ("dc", "cm")])
    _keep, dropped = contrast_populations({"aged": aged, "young": young})
    assert set(dropped) == {"neural", "dc"}, dropped
    assert dropped["neural"] == ["young"], "the arm that lacked it is not recorded"
    assert dropped["dc"] == ["aged"]


def test_one_shared_axis_survives_the_change():
    """The invariant the union existed to protect: every arm gets the SAME set."""
    a = _edges([("x", "y"), ("y", "z")])
    b = _edges([("x", "y"), ("y", "z"), ("w", "x")])
    c = _edges([("x", "y")])
    keep, _d = contrast_populations({"a": a, "b": b, "c": c})
    assert keep == ["x", "y"], keep


def test_no_arms_is_not_a_crash():
    assert contrast_populations({}) == ([], {})


def test_a_population_in_every_arm_is_never_dropped():
    a = _edges([("p", "q")])
    b = _edges([("q", "p")])
    keep, dropped = contrast_populations({"a": a, "b": b})
    assert keep == ["p", "q"]
    assert dropped == {}


def test_the_drawing_code_no_longer_masks():
    """The mask is gone, not merely unused: a reader of the source must not find two stories."""
    import inspect

    from scprofile import compare_panel as C
    src = inspect.getsource(C)
    body = src[src.index("def draw_design_contrasts") if "def draw_design_contrasts" in src else 0:]
    assert "hatch=" not in body, (
        "a hatch is still drawn somewhere in the contrast panels; the removal is supposed to "
        "happen at source, so there is nothing left to hatch")


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
