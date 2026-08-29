"""A declutter must survive whatever the host does to the canvas afterwards.

The host resizes every figure to its declared column width AFTER the plugin has finished
drawing. A declutter is solved in display space, so that resize undoes it: the points move
with the canvas and the labels, which carry fixed point offsets, do not. The host then
measured the collisions it had just created and reported them against the plugin.

This asserts the recovery, not the placement: overlaps present after a canvas change must be
gone once `resolve_overlaps` has run, which is what the host calls before it saves.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from scprofile import figure as F


def _panel(width=4.2):
    """Labels crowded enough that placement alone will not separate them."""
    fig, ax = plt.subplots(figsize=(width, 3.4))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    rows = [("population alpha", 4.9, 5.1), ("population beta", 5.0, 5.0),
            ("population gamma", 5.1, 4.9), ("population delta", 4.8, 4.8),
            ("population epsilon", 2.0, 8.0), ("population zeta", 8.0, 2.0)]
    texts = []
    for lab, x, y in rows:
        ax.scatter([x], [y], s=8)
        texts.append(ax.annotate(lab, (x, y), fontsize=5.5, xytext=(3, 3),
                                 textcoords="offset points", ha="left", va="bottom"))
    return fig, ax, texts


def _overlaps(fig):
    return [d for c, d in F.audit(fig) if c == "text_overlap"]


def test_declutter_separates():
    fig, ax, texts = _panel()
    F.spread_labels(ax, texts)
    assert not _overlaps(fig), "the declutter did not separate the labels it was given"
    plt.close(fig)


def test_canvas_change_is_recovered():
    """The defect and its fix, in one test.

    The test must SEE the defect before it may claim to fix one. An earlier version changed the
    canvas in a way that happened not to reintroduce any overlap, so it asserted "no overlaps"
    against a panel that never had any and would have passed with the fix deleted.
    """
    fig, ax, texts = _panel()
    F.spread_labels(ax, texts)
    assert not _overlaps(fig), "nothing to test: the declutter left overlaps of its own"
    # what the host does next, and the plugin cannot see: the geometry changes underneath it.
    # Widening the limits pulls the points together in display space while the labels, which
    # carry fixed point offsets, stay where the declutter put them.
    ax.set_xlim(-40, 50)
    ax.set_ylim(-40, 50)
    broken = _overlaps(fig)
    assert broken, "the canvas change did not reintroduce the defect, so this test is vacuous"
    n = F.resolve_overlaps(fig)
    assert n >= 1, "no declutter was registered, so the host had nothing to re-solve"
    after = _overlaps(fig)
    assert len(after) < len(broken), (
        f"re-solving did not reduce the overlaps: {len(broken)} -> {len(after)}")
    plt.close(fig)


def test_registration_survives_several_label_sets():
    fig, ax, texts = _panel()
    F.spread_labels(ax, texts[:3])
    F.spread_labels(ax, texts[3:])
    assert F.resolve_overlaps(fig) == 2
    plt.close(fig)


def test_no_registration_is_not_an_error():
    fig, ax = plt.subplots()
    assert F.resolve_overlaps(fig) == 0
    plt.close(fig)


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
