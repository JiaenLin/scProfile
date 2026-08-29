"""What a machine can see in a figure, so the eye is spent on what it cannot.

Eleven defects were found in one figure set by opening every panel one at a time. THREE WERE
MECHANICAL - text printed over text, a label clipped by the canvas, a size channel with no key -
and finding those by eye wastes the one check that cannot be automated. Every one also shipped,
because nothing looked at the figure between drawing it and writing it.

Each check here is proved to fire on the shape it exists to catch AND to stay silent on the
correct version of the same panel, because a check that fires on correct work is a check
somebody switches off.

Run: python tests/test_figure_audit.py
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                                 # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scprofile import figure as F                                               # noqa: E402

FAIL = []


def ck(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'} {name}" + (f" — {detail}" if not cond else ""))
    if not cond:
        FAIL.append(name)


def codes(build):
    fig, ax = plt.subplots(figsize=(3, 3))
    build(ax, fig)
    got = {c for c, _d in F.audit(fig)}
    plt.close(fig)
    return got


print("text printed over text — found by eye four times in one set")
ck("two labels on the same spot are caught",
   "text_overlap" in codes(lambda ax, f: (ax.text(.5, .5, "Vascular endothelial", fontsize=8),
                                          ax.text(.505, .5, "Smooth muscle", fontsize=8))))
ck("and two labels apart are not",
   "text_overlap" not in codes(lambda ax, f: (ax.text(.1, .1, "one", fontsize=8),
                                              ax.text(.8, .9, "two", fontsize=8))))
# A TICK LABEL IS NOT A LABEL. Small text legitimately sits close to other text, and treating
# every near-miss as a collision would make this fire on every panel in the tree.
ck("text below the size floor is not policed",
   "text_overlap" not in codes(lambda ax, f: (ax.text(.5, .5, "aaaa", fontsize=3.0),
                                              ax.text(.5, .5, "bbbb", fontsize=3.0))))

print("\nan artist clipped by its own canvas — found by eye twice")
ck("a label starting outside the figure is caught",
   "off_canvas" in codes(lambda ax, f: ax.text(-4.0, .5, "observed difference between arms",
                                               fontsize=8, clip_on=True)))
ck("and one inside it is not",
   "off_canvas" not in codes(lambda ax, f: ax.text(.5, .5, "inside", fontsize=8, clip_on=True)))

print("\na size channel with no key — shipped on two panels at once")
ck("a scatter varying marker size with no legend is caught",
   "size_unkeyed" in codes(lambda ax, f: ax.scatter([1, 2, 3], [1, 2, 3], s=[10, 200, 900])))
ck("the same scatter WITH a legend is not",
   "size_unkeyed" not in codes(lambda ax, f: (ax.scatter([1, 2, 3], [1, 2, 3],
                                                         s=[10, 200, 900], label="n"),
                                              ax.legend())))
ck("a scatter at ONE size is not a size channel",
   "size_unkeyed" not in codes(lambda ax, f: ax.scatter([1, 2, 3], [1, 2, 3], s=40)))

print("\nand a plain correct panel raises nothing at all")
ck("a line plot is clean", not codes(lambda ax, f: ax.plot([1, 2], [1, 2])))
ck("a labelled scatter with a legend is clean",
   not codes(lambda ax, f: (ax.scatter([1, 2], [1, 2], s=[30, 60], label="k"), ax.legend(),
                            ax.set_xlabel("x"), ax.set_ylabel("y"))))

print("\nit is wired where every figure passes, not left to be remembered")
src = (Path(__file__).resolve().parents[1] / "scprofile" / "plugin.py").read_text()
ck("emit_figure runs the audit", "_FA.audit(fig)" in src)
ck("and records it on the figure entry", '"audit"' in src)
ck("and it REPORTS rather than refusing",
   "raise" not in src.split("_FA.audit(fig)")[1][:400],
   "a gate that blocks a run over a stray label is one somebody removes")

print("\n" + ("the audit holds" if not FAIL else f"{len(FAIL)} FAILED: {FAIL}"))
sys.exit(1 if FAIL else 0)
