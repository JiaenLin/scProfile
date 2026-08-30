"""A NEGATIVE CONTROL for the drawing audit: what it must catch, and what it must not.

The loop had never been run against a figure set known to be sound, so how often it condemns a
correct panel was unmeasured - and that number decides whether anyone keeps the gate switched on.
This file fixes both halves in one place: SOUND panels the audit must be silent on, and BROKEN
panels it must catch, each broken in one specific way with the defect named.

Both halves are load-bearing. Without the sound half a check can be made to catch everything by
lowering a threshold, which is how a gate becomes noise. Without the broken half it can be made
to catch nothing, which is how a gate becomes decoration. The audit has been both: it reported 14
correctly keyed panels as unkeyed, and it passed five text collisions an eye then found.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from scprofile import figure as F


# ---------------------------------------------------------------- sound panels

def sound_plain():
    fig, ax = plt.subplots(figsize=(4, 3))
    ax.plot([1, 2, 3], [1, 4, 9])
    ax.set_xlabel("dose")
    ax.set_ylabel("response")
    ax.set_title("a perfectly ordinary panel")
    return fig


def sound_scatter_with_size_key():
    """A size channel WITH a key, placed outside the axes by the host helper."""
    fig, ax = plt.subplots(figsize=(4, 3))
    ax.scatter([1, 2, 3], [1, 2, 3], s=[5, 60, 200])
    h = [ax.scatter([], [], s=v, c="k") for v in (5, 200)]
    F.legend_outside(fig, ax, h, ["5", "200"])
    return fig


def sound_labelled_points():
    """Annotations that the declutter has separated."""
    fig, ax = plt.subplots(figsize=(4.5, 3.5))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    rows = [("alpha", 2, 8), ("beta", 5, 5), ("gamma", 8, 2), ("delta", 3, 3)]
    ts = []
    for lab, x, y in rows:
        ax.scatter([x], [y])
        ts.append(ax.annotate(lab, (x, y), fontsize=6, xytext=(3, 3),
                              textcoords="offset points"))
    F.spread_labels(ax, ts)
    return fig


def sound_many_ticks_with_room():
    """Many tick labels, but a wide enough axis: matplotlib spaces them and nothing collides."""
    fig, ax = plt.subplots(figsize=(7, 3))
    ax.plot(np.arange(11), np.arange(11))
    ax.set_xticks(range(11))
    return fig


def sound_heatmap_with_colourbar():
    fig, ax = plt.subplots(figsize=(4.5, 3.5))
    im = ax.imshow(np.random.RandomState(0).rand(6, 6))
    fig.colorbar(im, ax=ax, label="value")
    ax.set_xticks(range(6))
    ax.set_yticks(range(6))
    return fig


def sound_rotated_tick_labels():
    """The case the control was missing, and the audit was wrong about.

    Long population names on a heatmap axis, rotated 45 degrees - which is WHY they are rotated.
    Their axis-aligned boxes overlap by construction and their rotated rectangles graze at the
    corners, and the text is perfectly legible: eighty-four panels were read one at a time and
    not one rotated tick label was reported as unreadable. The audit reported FOURTEEN on a
    single panel the moment decorations entered the check.
    """
    fig, ax = plt.subplots(figsize=(4, 3.6))
    names = ["Adipocyte", "Working cardiomyocyte", "Endocardial", "Lymphatic endothelial",
             "Vascular endothelial", "Lymphoid", "Macrophage", "Mesothelial", "Fibroblast",
             "Pericyte", "Smooth muscle"]
    ax.imshow(np.random.RandomState(0).rand(len(names), len(names)))
    ax.set_xticks(range(len(names)))
    ax.set_xticklabels(names, rotation=45, ha="right", fontsize=5)
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels(names, fontsize=5)
    return fig


SOUND = (sound_plain, sound_scatter_with_size_key, sound_labelled_points,
         sound_many_ticks_with_room, sound_heatmap_with_colourbar,
         sound_rotated_tick_labels)


# --------------------------------------------------------------- broken panels

def broken_text_on_text():
    fig, ax = plt.subplots(figsize=(3, 2))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.text(0.5, 0.5, "first label here", fontsize=8)
    ax.text(0.52, 0.5, "second label here", fontsize=8)
    return fig, "text_overlap"


def broken_ticks_run_together():
    """The pseudotime F3 shape: a narrow axes carrying six tick labels."""
    fig = plt.figure(figsize=(6, 2))
    ax = fig.add_axes([0.05, 0.35, 0.16, 0.55])
    ax.barh([0, 1, 2], [1, 1, 1])
    ax.set_xlim(0, 1)
    ax.set_xticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])
    return fig, "text_overlap"


def broken_size_with_no_key():
    fig, ax = plt.subplots(figsize=(4, 3))
    ax.scatter([1, 2, 3], [1, 2, 3], s=[5, 60, 200])
    return fig, "size_unkeyed"


def broken_label_off_canvas():
    fig, ax = plt.subplots(figsize=(3, 2))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.annotate("this runs off the edge", (1, 1), xytext=(80, 50),
                textcoords="offset points")
    return fig, "off_canvas"


BROKEN = (broken_text_on_text, broken_ticks_run_together,
          broken_size_with_no_key, broken_label_off_canvas)


# ---------------------------------------------------------------------- tests

def test_no_sound_panel_is_condemned():
    """THE FALSE-POSITIVE RATE, measured rather than assumed."""
    bad = []
    for mk in SOUND:
        fig = mk()
        found = F.audit(fig)
        plt.close(fig)
        if found:
            bad.append(f"{mk.__name__}: {[c for c, _ in found]}")
    assert not bad, ("the audit condemned a panel built to be sound, which is how a gate stops "
                     f"being trusted: {bad}")


def test_every_broken_panel_is_caught():
    """THE FALSE-NEGATIVE RATE. Each panel is broken in ONE named way."""
    missed = []
    for mk in BROKEN:
        fig, want = mk()
        codes = {c for c, _ in F.audit(fig)}
        plt.close(fig)
        if want not in codes:
            missed.append(f"{mk.__name__}: wanted {want}, got {sorted(codes) or 'nothing'}")
    assert not missed, f"the audit passed a panel broken on purpose: {missed}"


def test_the_control_has_both_halves():
    """A control with only one half can be satisfied by a threshold at either extreme."""
    assert len(SOUND) >= 4, "too few sound panels to measure a false-positive rate"
    assert len(BROKEN) >= 4, "too few broken panels to measure a false-negative rate"


def test_the_decoration_classes_are_actually_covered():
    """The five misses an eye found were ALL decorations, so the control must contain them."""
    fig = sound_heatmap_with_colourbar()
    fig.canvas.draw()
    plt.close(fig)
    src = (F.__file__)
    text = open(src).read()
    for hook in ("get_xticklabels", "ax.title", "xaxis.label", "get_legend"):
        assert hook in text, f"the audit does not collect {hook}, so a whole class is invisible"


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
