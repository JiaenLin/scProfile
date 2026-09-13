"""The host's own panels answer what the eye found on them (harness ADR-0019, step 2).

Two cold lookers marked eight of the host's composed panels on a real cohort (blind 0005), and
those are the host's debt, not the plugin's: nothing to paste, mechanism to change. Each check
here is one finding, stated as the looker stated it, failing on the drawing as it was:

  N2 chord           ribbon width encodes strength and no key on the figure says so
  N3 matrix          a grey cross marks cells and nothing defines it
  N6 role heatmap    the same undefined grey cross
  N4 role scatter    every point in one corner of a shared 0-6 scale, labels crowded together
  P1 presence        the sentinel row ranked among real populations, its cells coloured as data
  P2 unit totals     the pooled arms' grey bars covered by no legend entry
  across the design  the difference column varies marker size and nothing keys it
  (C4 role shift)    labels over arrows in a crowded centre - the same declutter as N4

Run: python tests/test_the_hosts_panels_answer_the_eye.py
"""
import sys
import tempfile
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                                 # noqa: E402
import pandas as pd                                                             # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scprofile import compare_panel as CP                                       # noqa: E402
from scprofile import design_panel as DP                                        # noqa: E402
from scprofile import figure as F                                               # noqa: E402
from scprofile import network_panels as NP                                      # noqa: E402

FAIL = []


def ck(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'} {name}" + (f" — {detail}" if not cond else ""))
    if not cond:
        FAIL.append(name)


POPS = ["Alpha cell", "Beta cell", "Gamma cell", "Delta cell", "Epsilon cell",
        "Zeta cell", "Eta cell", "Theta cell", "Iota cell"]


def edges_for(pops, strength=1.0, pathways=("P1", "P2", "P3")):
    rows = []
    for i, s in enumerate(pops):
        for j, t in enumerate(pops):
            if (i + j) % 3 == 0 and i != j:
                rows.append({"source": s, "target": t, "prob": strength * (1 + (i * j) % 5) / 5,
                             "pathway": pathways[(i + j) % len(pathways)]})
    return pd.DataFrame(rows)


class Draw:
    """A shim whose figures we can inspect: keeps the figure object instead of closing it."""

    def __init__(self):
        self.figs = {}
        self.figure = F

    def plot(self):
        return plt

    def emit_figure(self, fid, fig, caption="", source=None):
        self.figs[fid] = (fig, caption)


def texts_of(fig):
    out = []
    for ax in fig.get_axes():
        out += [t.get_text() for t in ax.texts]
        out += [ax.get_title(), ax.get_xlabel(), ax.get_ylabel()]
        out += [t.get_text() for t in ax.get_xticklabels() + ax.get_yticklabels()]
        lg = ax.get_legend()
        if lg is not None:
            out += [t.get_text() for t in lg.get_texts()]
            out.append(lg.get_title().get_text())
    for lg in fig.legends:
        out += [t.get_text() for t in lg.get_texts()]
    out += [t.get_text() for t in fig.texts]
    return " | ".join(x for x in out if x)


print("N2: the chord's ribbon width has a key on the figure")
d = Draw()
NP.chord(d, edges_for(POPS), POPS, title="arm A")
fig = d.figs["N2_chord"][0]
ck("a key names what the width encodes", "width" in texts_of(fig).lower(), texts_of(fig)[:200])
plt.close(fig)

print("\nN3 and N6: the grey cross is defined on the figure")
d = Draw()
NP.matrix(d, edges_for(POPS), POPS, title="arm A")
fig = d.figs["N3_matrix"][0]
ck("the matrix keys its cross", "no edge" in texts_of(fig).lower(), texts_of(fig)[:200])
plt.close(fig)
d = Draw()
NP.role_heatmap(d, edges_for(POPS), POPS, "pathway", title="arm A")
fig = d.figs["N6_role_heatmap"][0]
ck("the role heatmap keys its cross", "no edge" in texts_of(fig).lower(), texts_of(fig)[:200])
plt.close(fig)

print("\nN4: labels crowded in one corner of a shared scale are separated in both directions")
d = Draw()
NP.role_scatter(d, edges_for(POPS, strength=0.02), POPS, title="arm A", scale={"role": 6.0})
fig = d.figs["N4_role"][0]
_b, _a, _r = F.audit_and_repair(fig)
ck("no label collides after the declutter and the save's own repairs",
   "text_overlap" not in [c for c, _ in _a], str(_a)[:300])
plt.close(fig)

print("\nthe declutter keeps every label at its own x and still clears a clump")
fig, ax = plt.subplots(figsize=(3.3, 2.4))
ax.set_xlim(0, 6)
ax.set_ylim(0, 6)
ts = []
for k, name in enumerate(POPS[:6]):
    ax.scatter([0.2 + 0.03 * k], [0.2 + 0.02 * k], s=20)
    ts.append(ax.annotate(name, (0.2 + 0.03 * k, 0.2 + 0.02 * k), fontsize=7, xytext=(4, 2),
                          textcoords="offset points"))
F.spread_labels(ax, ts)
_pairs = [dd for c, dd in F.audit(fig) if c == "text_overlap"
          and sum(1 for n in POPS[:6] if n in dd) >= 2]
ck("six labels on six points a few pixels apart no longer overlap each other", not _pairs,
   str(_pairs)[:300])
# A LABEL MOVES SIDEWAYS ONLY ON A LADDER, AND THEN IT CARRIES A LEADER LINE (harness ADR-0020):
# the rule paid for in ADR-0019 was that a drifted label lands on a neighbour's point; a label
# tied to its point by a line has not drifted.
_leaders = getattr(fig, "_scprofile_leaders", {}) or {}
ck("and none moved sideways without a leader line tying it to its point",
   all(t.xyann[0] == 4 or id(t) in _leaders for t in ts), str([t.xyann for t in ts]))
plt.close(fig)

print("\nP1: the sentinel row is last, and its cells carry no data colour")
d = Draw()
lbu = {"armA*": {"Alpha cell": 500, "Beta cell": 300, "EXCLUDED": 200},
       "armB*": {"Alpha cell": 400, "Beta cell": 350, "EXCLUDED": 150},
       "s1": {"Alpha cell": 250, "Beta cell": 150, "EXCLUDED": 100},
       "s2": {"Alpha cell": 250, "Beta cell": 150, "EXCLUDED": 100}}
tot = {"Alpha cell": 1400, "Beta cell": 950, "EXCLUDED": 550}
NP.unit_presence(d, lbu, tot, unit_axis={"armA*": "group", "armB*": "group"},
                 sentinels=("EXCLUDED",))
fig = d.figs["P1_population_presence"][0]
ax = fig.get_axes()[0]
ticks = [t.get_text() for t in ax.get_yticklabels()]
ck("the sentinel is the last row, not ranked among the populations",
   ticks and "sentinel" in ticks[-1].lower() and "sentinel" not in ticks[0].lower(), str(ticks))
import numpy as np                                                              # noqa: E402
arr = ax.images[0].get_array()
last = np.ma.getmaskarray(arr)[-1] if np.ma.isMaskedArray(arr) else np.isnan(np.asarray(arr))[-1]
ck("and its cells are blank", bool(np.all(last)), str(np.asarray(arr)[-1]))
plt.close(fig)

print("\nP2: the pooled arms' grey bars have a legend entry")
d = Draw()
per = {"s1": edges_for(POPS[:4]), "s2": edges_for(POPS[:4], 0.8), "s3": edges_for(POPS[:4], 1.2),
       "s4": edges_for(POPS[:4], 0.9), "armA*": edges_for(POPS[:4], 2.0),
       "armB*": edges_for(POPS[:4], 2.1)}
design = {"s1": {"age": "lo"}, "s2": {"age": "lo"}, "s3": {"age": "hi"}, "s4": {"age": "hi"}}
NP.unit_totals(d, per, design=design, unit_axis={"armA*": "group", "armB*": "group"},
               unit_members={"armA*": ["s1", "s3"], "armB*": ["s2", "s4"]})
fig = d.figs["P2_unit_totals"][0]
ck("a bar that pools levels of the factor is keyed", "pool" in texts_of(fig).lower()
   or "mixed" in texts_of(fig).lower(), texts_of(fig)[:300])
plt.close(fig)

print("\nacross the design: the difference column's marker size is keyed")
with tempfile.TemporaryDirectory() as td:
    per_sample = {"s1": {"cells": 100.0, "edges": 10.0}, "s2": {"cells": 120.0, "edges": 12.0},
                  "s3": {"cells": 90.0, "edges": 20.0}, "s4": {"cells": 110.0, "edges": 25.0}}
    dsg = {"s1": {"age": "lo", "diet": "a"}, "s2": {"age": "lo", "diet": "b"},
           "s3": {"age": "hi", "diet": "a"}, "s4": {"age": "hi", "diet": "b"}}
    dest = Path(td) / "p_across_design.png"
    n, rec = DP.draw(per_sample, dsg, dest)
    ck("the panel drew", n > 0 and dest.is_file(), str((n, rec)))
    ck("and its record carries what the key says", isinstance(rec, dict))
    src = (ROOT / "scprofile" / "design_panel.py").read_text(encoding="utf-8")
    ck("the difference column keys marginal against simple", "marginal effect" in src
       and "simple effect" in src and "legend(" in src[src.find("difference\\nbetween arms") - 2500:
                                                          src.find("difference\\nbetween arms") + 800],
       "no legend near the difference column")

# ---------------------------------------------------------------------------------------------
# THE SECOND LOOK (harness ADR-0020, step 1). Two cold lookers on the rerun found ten more things
# on the host's own panels. Each check below is one finding, in the looker's words, failing on
# the drawing as it was.
#
#   C1 diff (x2), P2 totals   a colour-bar title and an axis title cut at the image's edge
#   C3 flow                   a dagger and a shaded band that nothing on the panel explains
#   C4 role shift             labels crowding together, touching
#   C5 interaction            two colours with no key
#   N3 matrix                 the "no edge" key drawn over real cells
#   N4 role                   nine labels piled at the origin, unreadable
#   N7 contribution           bars that sum to 80% of a total with nothing saying so
#   across the design         an asterisk on a header with no footnote
# ---------------------------------------------------------------------------------------------
from PIL import Image                                                           # noqa: E402


def border_ink(path, px=3):
    """Dark pixels in the outermost `px` columns and rows of a PNG - a text cut at the edge."""
    a = np.asarray(Image.open(path).convert("L"))
    return {"right": int((a[:, -px:] < 250).sum()), "left": int((a[:, :px] < 250).sum()),
            "top": int((a[:px, :] < 250).sum()), "bottom": int((a[-px:, :] < 250).sum())}


print("\nC1 and P2: a title that reaches past the figure box is saved whole, never cut")
with tempfile.TemporaryDirectory() as td:
    fig, axes = plt.subplots(1, 4, figsize=(F.DOUBLE, 3.0), layout="constrained", sharey=True)
    for ax, lab in zip(axes, ["edges", "interaction strength", "edges per 1,000 cells",
                              "interaction strength per 1,000 cells"]):
        ax.barh(range(14), np.arange(14) + 1, height=0.72)
        ax.set_xlabel(lab, fontsize=7)
        ax.tick_params(labelsize=6)
    axes[0].set_yticks(range(14), [f"unit {i}" for i in range(14)], fontsize=6)
    e = F.save(fig, Path(td), "totals", caption="c", formats=("png",), dpi=200,
               log=lambda *a, **k: None, stamp="the cohort   ·   14 units")
    ink = border_ink(e["path"])
    ck("the fourth panel's axis title is not cut at the right edge", ink["right"] == 0, str(ink))
    fig, ax = plt.subplots(figsize=(F.SINGLE, F.SINGLE * 0.92), layout="constrained")
    names = [f"Compartment/Lineage/Population number {i}" for i in range(13)]
    im = ax.imshow(np.random.default_rng(0).normal(size=(13, 13)), cmap="RdBu_r", vmin=-1, vmax=1)
    ax.set_xticks(range(13), names, rotation=45, ha="right", fontsize=5)
    ax.set_yticks(range(13), names, fontsize=5)
    ax.set_xlabel("receiver")
    ax.set_ylabel("sender")
    cb = fig.colorbar(im, ax=ax, fraction=0.045, pad=0.02)
    cb.set_label("aged minus young   (% of the arm's own total, significant only)", fontsize=6)
    e = F.save(fig, Path(td), "diff", caption="c", formats=("png",), dpi=200,
               log=lambda *a, **k: None, stamp="age   ·   4 vs 6 samples, cells pooled per arm")
    ink = border_ink(e["path"])
    ck("the colour-bar title is not cut at the top or right edge", ink["top"] == 0 and ink["right"] == 0,
       str(ink))

# THE TEXT OF A PANEL AS IT IS SAVED. The compare and design panels save through `figure.save`
# and return paths; this wraps the save to keep every text the figure carried, name by name.
_SAVED = {}
_orig_save = F.save


def _capturing_save(fig, out_dir, name, **kw):
    _SAVED[name] = texts_of(fig)
    return _orig_save(fig, out_dir, name, **kw)


def edges_pairs(pops, strength=1.0, pathways=("P1", "P2", "P3")):
    e = edges_for(pops, strength, pathways)
    e["pair"] = e["source"].str[:3] + "-" + e["target"].str[:3] + "-" + e["pathway"]
    return e


print("\nC3: the dagger and the shaded band are keyed on the panel")
F.save = _capturing_save
try:
    with tempfile.TemporaryDirectory() as td:
        per = {"s1": edges_for(POPS, 1.0), "s2": edges_for(POPS, 1.1),
               "s3": edges_for(POPS, 2.0, ("P1", "P2", "P3", "P4")),
               "s4": edges_for(POPS, 2.2, ("P1", "P2", "P3", "P4"))}     # P4 scored in one arm only
        design = {"s1": {"age": "young"}, "s2": {"age": "young"}, "s3": {"age": "aged"},
                  "s4": {"age": "aged"}}
        spec = ("age", "age", "young", "aged", {"age": "young"}, {"age": "aged"})
        CP.draw_contrast(per, design, spec, Path(td), "p", weight="prob", group_col="pathway")
        flow = [v for k, v in _SAVED.items() if "C3_flow" in k]
        ck("the flow panel drew with a one-arm group", bool(flow) and "†" in flow[0], str(flow)[:200])
        ck("and the panel itself says what the dagger and the band mean",
           bool(flow) and "one arm only" in flow[0], flow[0][:300] if flow else "no panel")

    print("\nC5: the interaction panel keys its two colours")
    with tempfile.TemporaryDirectory() as td:
        per = {}
        design = {}
        k = 0
        for age in ("young", "aged"):
            for diet in ("a", "b"):
                for rep in (1, 2):
                    k += 1
                    e = edges_for(POPS, 1.0 + 0.7 * (age == "aged") + 0.4 * (diet == "b")
                                  + 0.9 * (age == "aged" and diet == "b"))
                    e["pathway"] = [("P1", "P2", "P3", "P4")[n % 4] for n in range(len(e))]
                    per[f"s{k}"] = e
                    design[f"s{k}"] = {"age": age, "diet": diet}
        specs = CP.interaction_specs(design)
        ck("the design has one interaction", len(specs) == 1, str(specs))
        CP.draw_interaction(per, design, specs[0], Path(td), "p", weight="prob", group_col="pathway")
        inter = [v for k, v in _SAVED.items() if "C5_interaction" in k]
        ck("the panel keys what orange and blue mean",
           bool(inter) and "direction" in inter[0].lower() and ("revers" in inter[0].lower()
                                                                or "flip" in inter[0].lower()),
           inter[0][:300] if inter else "no panel")

    print("\nacross the design: the asterisk on a header has its footnote on the panel")
    with tempfile.TemporaryDirectory() as td:
        per_sample = {f"s{i}": {"cells": 100.0 + i, "edges": 10.0 + i} for i in range(1, 9)}
        dsg = {f"s{i}": {"age": "young" if i <= 4 else "aged", "diet": "a" if i % 2 else "b",
                         "chemistry": "v2" if i <= 4 else "v3"} for i in range(1, 9)}
        dest = Path(td) / "p_across_design.png"
        DP.draw(per_sample, dsg, dest)
        grid = [v for k, v in _SAVED.items() if "across_design" in k]
        ck("age is marked as aliased on its header", bool(grid) and "age*" in grid[0], str(grid)[:200])
        ck("and the panel carries the footnote", bool(grid) and "aliased" in grid[0].lower()
           and "chemistry" in grid[0], grid[0][:400] if grid else "no panel")
finally:
    F.save = _orig_save

print("\nN7: bars that carry less than the whole say how much, and how many carry the rest")
d = Draw()
big = edges_pairs(POPS, pathways=("P1",) * 6 + ("P2",))          # one dominant pathway, many pairs
NP.contribution(d, big, POPS, "pathway", "pair", top=5)
fig = d.figs["N7_contribution"][0]
txt = texts_of(fig)
ck("the panel says how much of the total the drawn bars carry", "%" in txt and "carry" in txt, txt[:300])
ck("and how many pairs carry the rest", "the rest" in txt, txt[:300])
plt.close(fig)

def pipeline(fig, stamp="arm A   ·   2 samples pooled"):
    """What the host does to a panel between the plugin's draw and the file: the column fit,
    the stamp, the re-solve, the audit and the repairs - the geometry the eye sees."""
    F.fit_column(fig)
    t = fig.text(0.0, -0.006, stamp, ha="left", va="top", fontsize=5.2)
    F.stamp_below(fig, t)
    F.resolve_overlaps(fig)
    _b, after, reps = F.audit_and_repair(fig)
    fig.canvas.draw()
    return after, reps


def label_boxes(ax):
    r = ax.figure.canvas.get_renderer()
    return [(t, t.get_window_extent(r)) for t in ax.texts if str(t.get_text()).strip()]


print("\nN3: the key for the crossed cells never sits on the cells")
LONG = [f"Compartment/Lineage/Population {i}" for i in range(13)]
d = Draw()
e = edges_for(LONG, 0.4)
NP.matrix(d, e, LONG, title="arm A")
fig = d.figs["N3_matrix"][0]
pipeline(fig)
ax = fig.get_axes()[0]
lg = ax.get_legend() or (fig.legends[0] if fig.legends else None)
lb = lg.get_window_extent(fig.canvas.get_renderer()) if lg is not None else None
ck("the matrix has its key", lg is not None)
_r = fig.canvas.get_renderer()
_others = [a.get_window_extent(_r) for a in fig.get_axes()] + \
          [a.yaxis.label.get_window_extent(_r) for a in fig.get_axes()[1:]]
ck("and the key's box overlaps neither the data area nor the colour bar and its title",
   lb is not None and not any(lb.overlaps(b) for b in _others),
   f"legend {lb} vs {[str(b) for b in _others if lb is not None and lb.overlaps(b)]}")
plt.close(fig)

print("\nN4: nine labels piled at the origin are laid out so every name can be read")
d = Draw()
NP.role_scatter(d, edges_for(POPS, strength=0.004), POPS, title="arm A", scale={"role": 6.0})
fig = d.figs["N4_role"][0]
after, reps = pipeline(fig)
ax = fig.get_axes()[0]
boxes = label_boxes(ax)
pairs = [(a.get_text(), b.get_text()) for i, (a, ba) in enumerate(boxes)
         for b, bb in boxes[i + 1:] if ba.overlaps(bb)]
ck("nine labels within a corner of a shared scale no longer overlap one another", not pairs,
   str(pairs)[:300])
axb = ax.get_window_extent(fig.canvas.get_renderer())
ck("and every label stays inside the axes", all(axb.contains(b.x0, b.y0) and axb.contains(b.x1, b.y1)
                                                 for _t, b in boxes),
   str([(t.get_text(), (round(b.x0), round(b.x1))) for t, b in boxes if not axb.contains(b.x1, b.y1)])[:300])
plt.close(fig)

print("\nC4: role-shift labels that crowd one region keep a gap between them")
F.save = _capturing_save
_GEOM = {}
def _geom_save(fig, out_dir, name, **kw):
    r = _orig_save(fig, out_dir, name, **kw)
    if "C4_role" in name:
        _GEOM["boxes"] = label_boxes(fig.get_axes()[0])
    return r
F.save = _geom_save
try:
    with tempfile.TemporaryDirectory() as td:
        per = {"s1": edges_for(POPS, 0.02), "s2": edges_for(POPS, 0.021),
               "s3": edges_for(POPS, 0.024), "s4": edges_for(POPS, 0.025)}
        design = {"s1": {"age": "young"}, "s2": {"age": "young"}, "s3": {"age": "aged"}, "s4": {"age": "aged"}}
        spec = ("age", "age", "young", "aged", {"age": "young"}, {"age": "aged"})
        CP.draw_contrast(per, design, spec, Path(td), "p", weight="prob", group_col="pathway")
finally:
    F.save = _orig_save
bx = _GEOM.get("boxes", [])
gaps = []
for i, (a, ba) in enumerate(bx):
    for b, bb in bx[i + 1:]:
        dx = max(ba.x0 - bb.x1, bb.x0 - ba.x1)
        dy = max(ba.y0 - bb.y1, bb.y0 - ba.y1)
        gaps.append((max(dx, dy), a.get_text(), b.get_text()))
tight = [g for g in gaps if g[0] < 2.0]
ck("the role-shift panel drew its labels", bool(bx), str(bx)[:100])
ck("no two labels come within two pixels of each other", not tight, str(sorted(tight)[:4]))

print("\n" + ("the host's panels answer the eye" if not FAIL else f"{len(FAIL)} FAILED: {FAIL}"))
sys.exit(1 if FAIL else 0)
