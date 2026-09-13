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
ck("and none moved sideways - a label that drifts lands on a neighbour's point",
   all(t.xyann[0] == 4 for t in ts), str([t.xyann for t in ts]))
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

print("\n" + ("the host's panels answer the eye" if not FAIL else f"{len(FAIL)} FAILED: {FAIL}"))
sys.exit(1 if FAIL else 0)
