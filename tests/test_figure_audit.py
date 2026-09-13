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

# THE FALSE POSITIVE IT SHIPPED WITH. A provenance stamp is placed below the figure so the tight
# bbox grows to hold it, and `Text.clip_on` is True by default at figure level - so the first
# version reported every correctly-stamped panel as clipped, on all 223 of a real run.
ck("a figure-level stamp below the canvas is NOT called clipped",
   "off_canvas" not in codes(lambda ax, f: f.text(0.0, -0.006, "unit · one sample · n = 1,000",
                                                  fontsize=5.2)))

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
ck("emit_figure runs the audit, and the repairs before it", "_FA.audit_and_repair(fig)" in src)
ck("and records it on the figure entry", '"audit"' in src)
ck("and it REPORTS rather than refusing",
   "raise" not in src.split("_FA.audit_and_repair(fig)")[1][:400],
   "a gate that blocks a run over a stray label is one somebody removes")

print("\nand it survives the trip from the plugin into the run")
# IT RAN ON 223 PANELS AND NONE OF IT ARRIVED. The manifest serialiser copies a fixed set of keys
# - which is right, a plugin must not inject arbitrary keys into the payload - and the new one
# was not on the list. A measurement that does not reach the run is a measurement nobody has.
from scprofile import manifest as _M                                            # noqa: E402
_e = _M._figure({"id": "F1", "path": "figures/F1.png", "caption": "c",
                 "audit": [{"code": "text_overlap", "detail": "a over b"}]},
                rel=lambda x: str(x))
ck("the serialiser carries the audit", bool(_e.get("audit")), str(_e))
ck("and drops nothing else it used to carry",
   {"id", "path", "caption"} <= set(_e))

# THE CHECK THAT STOPS A THIRD TIME. Twice now a key `emit_figure` writes has been dropped by the
# serialiser's whitelist - the figure id, then the drawing audit - and both were found on a real
# run long after shipping. The whitelist is right; what was missing is anything comparing the two
# ends. This reads the keys the emit point actually writes and asserts the serialiser carries
# each one, so the NEXT key is caught at commit rather than on a cohort.
import ast as _ast, inspect as _insp                                            # noqa: E402
from scprofile import plugin as _P                                              # noqa: E402

_src = _insp.getsource(_P.Context.emit_figure)
_written = set()
for _n in _ast.walk(_ast.parse(_src.lstrip())):
    if isinstance(_n, _ast.Call) and getattr(_n.func, "attr", "") == "append" and _n.args:
        if isinstance(_n.args[0], _ast.Dict):
            _written = {k.value for k in _n.args[0].keys
                        if isinstance(k, _ast.Constant) and isinstance(k.value, str)}
_probe = {k: ("x" if k not in ("audit",) else [{"code": "c", "detail": "d"}])
          for k in _written}
_probe["path"] = "figures/F.png"
_carried = set(_M._figure(_probe, rel=lambda x: str(x)))
_lost = sorted(_written - _carried - {"vector", "source"})   # those two are re-keyed, not lost
# CLEAN IS NOT UNMEASURED. Writing the key only when something was found made a panel that
# measured clean indistinguishable from one made before the audit existed - and the loop station
# reading it reported "no panel carries an audit" for a run where every panel had been measured
# and every panel was fine. The absence-is-not-one-thing defect, in this tool's own metadata,
# committed while correcting it on four panels.
_clean = _M._figure({"id": "F", "path": "figures/F.png", "audit": []}, rel=lambda x: str(x))
_old = _M._figure({"id": "F", "path": "figures/F.png"}, rel=lambda x: str(x))
ck("a panel that measured clean carries an empty audit", _clean.get("audit") == [])
ck("and one never measured carries no audit key at all", "audit" not in _old)

ck("every key emit_figure writes is one the serialiser carries",
   not _lost, f"dropped between the plugin and the run: {_lost}")


print("\nthe audit repairs what it can, then records what is left (harness ADR-0018)")
# EVERY COLLISION ON THE RUN THIS WAS WRITTEN AGAINST WAS THE HOST'S OR THE DATA'S: the canvas
# shrank to the column after the plugin finished and the type did not; the stamp sat at a fixed
# y; a data-placed label landed on a legend. A fix in the plugin holds for one dataset. So the
# host repairs the classes it can, generically, where the artists are still live, and re-audits.
import numpy as _np                                                             # noqa: E402
from matplotlib.ticker import FixedLocator as _Fixed                             # noqa: E402


def repaired(build, figsize=(3.3, 2.4)):
    """(codes before, codes after, repair codes) for a panel `build` draws."""
    fig, ax = plt.subplots(figsize=figsize)
    build(ax, fig)
    before, after, reps = F.audit_and_repair(fig)
    plt.close(fig)
    return ({c for c, _d in before}, {c for c, _d in after}, [c for c, _w in reps])


def _twin_axes(ax, fig):
    """Two x axes on the bottom, the twin's spine not offset: F1's shape after the shrink."""
    ax.barh([0, 1, 2], [4000, 3000, 1000])
    ax.set_xlim(0, 4000)
    ax2 = ax.twiny()
    ax2.set_xlim(0, 100)
    ax2.set_xticks([0, 25, 50, 75, 100])
    ax2.xaxis.set_ticks_position("bottom")
    ax2.xaxis.set_label_position("bottom")
    ax2.spines["bottom"].set_position(("outward", 0))


b, a, r = repaired(_twin_axes)
ck("two axes' ticks on one side collide before", "text_overlap" in b, str(b))
ck("and the twin's spine is moved outward until they do not", "text_overlap" not in a, str(a))
ck("and the repair is named", "axis_offset" in r, str(r))


def _corner(ax, fig):
    """A log x axis whose first tick meets the y axis's origin label: F2's shape."""
    ax.set_xscale("log")
    ax.set_xlim(1e10, 1e12)
    ax.set_ylim(0, 1)
    ax.plot([1e10, 1e12], [0, 1])
    ax.set_yticks([0.0, 0.5, 1.0])
    ax.tick_params(labelsize=12, pad=0, length=0)


b, a, r = repaired(_corner, figsize=(2.2, 1.6))
ck("a corner collision between an x tick and a y tick is found", "text_overlap" in b, str(b))
ck("and the x labels are moved down, every label kept", "text_overlap" not in a, str(a))
ck("and the repair is named", "tick_pad" in r or "corner_hide" in r, str(r))


def _dense(ax, fig):
    """Six numeric ticks on an axis too narrow for them."""
    ax.set_position([0.05, 0.35, 0.16, 0.55])
    ax.barh([0, 1, 2], [1, 1, 1])
    ax.set_xlim(0, 1)
    ax.set_xticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])


b, a, r = repaired(_dense, figsize=(6, 2))
ck("ticks of one axis run together before", "text_overlap" in b, str(b))
ck("and the axis is thinned until they read", "text_overlap" not in a, str(a))
ck("and the repair is named", "tick_thin" in r, str(r))


def _categorical(ax, fig):
    """Long category names on a narrow x axis: rotation is the repair, not thinning."""
    names = [f"population {i} with a long name" for i in range(6)]
    ax.bar(range(6), [1, 2, 3, 2, 1, 2])
    ax.xaxis.set_major_locator(_Fixed(range(6)))
    ax.set_xticklabels(names, fontsize=7)


b, a, r = repaired(_categorical, figsize=(3.3, 2.4))
ck("category labels run together before", "text_overlap" in b, str(b))
ck("and are rotated rather than dropped", "text_overlap" not in a and "tick_rotate" in r,
   f"after {a}, repairs {r}")


def _duplicate(ax, fig):
    """The same tick labels drawn twice at one place: a twin whose ticks sit on the host's side."""
    ax.plot([0, 1], [0, 1])
    ax.set_yticks([0.0, 0.5, 1.0])
    ax2 = ax.twinx()
    ax2.set_ylim(ax.get_ylim())
    ax2.set_yticks([0.0, 0.5, 1.0])
    ax2.yaxis.tick_left()


b, a, r = repaired(_duplicate)
ck("a duplicated tick label is found", "text_overlap" in b, str(b))
ck("and the later copy is hidden", "text_overlap" not in a and "tick_dedupe" in r,
   f"after {a}, repairs {r}")


def _label_on_legend(ax, fig):
    """A data-placed annotation under a legend drawn inside the axes: F6's shape."""
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.plot([0.1, 0.9], [0.1, 0.9], label="significant edges")
    ax.legend(loc="upper left")
    ax.annotate("Vascular endothelial", (0.1, 0.9), fontsize=8, xytext=(0, 0),
                textcoords="offset points")


b, a, r = repaired(_label_on_legend)
ck("a label over a legend's text is found", "text_overlap" in b, str(b))
ck("and the legend is moved outside the axes", "text_overlap" not in a and "legend_out" in r,
   f"after {a}, repairs {r}")


def _two_annotations(ax, fig):
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.scatter([0.5, 0.52], [0.5, 0.5])
    ax.annotate("first label", (0.5, 0.5), fontsize=8, xytext=(3, 0), textcoords="offset points")
    ax.annotate("second label", (0.52, 0.5), fontsize=8, xytext=(3, 0),
                textcoords="offset points")


b, a, r = repaired(_two_annotations)
ck("two annotations on one point collide before", "text_overlap" in b, str(b))
ck("and are separated by the declutter the plugins already use",
   "text_overlap" not in a and "annotations_apart" in r, f"after {a}, repairs {r}")


def _label_on_ytick(ax, fig):
    """A placed label over a y tick label at the axes' left edge: the residue the first cohort run
    left (a pathway name over a colour-bar tick, twice; a population name over an axis tick)."""
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_yticks([0.0, 0.5, 1.0])
    ax.tick_params(labelsize=9)
    ax.scatter([0.02], [0.5])
    ax.annotate("PECAM1", (0.02, 0.5), fontsize=9, xytext=(-20, 0), textcoords="offset points",
                ha="left", va="center")


b, a, r = repaired(_label_on_ytick)
ck("a placed label over a y tick label is found", "text_overlap" in b, str(b))
ck("and the label is moved inward, off the axis's own text",
   "text_overlap" not in a and "annotation_inward" in r, f"after {a}, repairs {r}")


def _label_on_xtick(ax, fig):
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_xticks([0.0, 0.5, 1.0])
    ax.tick_params(labelsize=9)
    ax.scatter([0.5], [0.02])
    ax.annotate("APP", (0.5, 0.02), fontsize=9, xytext=(0, -12), textcoords="offset points",
                ha="center", va="top")


b, a, r = repaired(_label_on_xtick)
ck("a placed label over an x tick label is found", "text_overlap" in b, str(b))
ck("and moved up, inward", "text_overlap" not in a and "annotation_inward" in r,
   f"after {a}, repairs {r}")


def _residue(ax, fig):
    """Two texts placed in DATA coordinates: moving either changes what it says. Left alone."""
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.text(0.5, 0.5, "first label here", fontsize=8)
    ax.text(0.52, 0.5, "second label here", fontsize=8)


b, a, r = repaired(_residue)
ck("a collision the repertoire does not answer stays a finding", "text_overlap" in a, str(a))
ck("and no repair is claimed for it", not r, str(r))

# NOTHING SHRINKS, NOTHING WIDENS, NOTHING MOVES A NUMBER. The repertoire is bounded so it can be
# read in one table, and the bounds are checked here rather than trusted.
_fig, _ax = plt.subplots(figsize=(3.3, 2.4))
_dense(_ax, _fig)
_w0 = _fig.get_size_inches()[0]
_sizes = {float(t.get_fontsize()) for t in _ax.get_xticklabels()}
F.audit_and_repair(_fig)
ck("a repair never changes a font size",
   {float(t.get_fontsize()) for t in _ax.get_xticklabels()} <= _sizes)
ck("nor widens the canvas", _fig.get_size_inches()[0] <= _w0 + 1e-6)
ck("nor the axis limits", _ax.get_xlim() == (0.0, 1.0))
plt.close(_fig)

print("\nthe host's own stamp sits below everything, whatever the ticks do")
# SIX PANELS OF ONE RUN carried a bottom tick label through the provenance stamp: the stamp was
# placed at a fixed y before the canvas was shrunk to the column, and the tick labels, in points,
# then reached further below the box. Placed from the rendered box, after the fit, it cannot.
import tempfile as _tmp                                                          # noqa: E402
with _tmp.TemporaryDirectory() as _td:
    _ctx = _P.Context(None, keys={}, out=_td, unit="Aging1", unit_members=["Aging1"])
    _fig, _ax = plt.subplots(figsize=(3.3, 2.4))
    _ax.bar(range(6), [1, 2, 3, 2, 1, 2])
    _ax.set_xticks(range(6))
    _ax.set_xticklabels([f"a long population name {i}" for i in range(6)], rotation=90,
                        fontsize=7)
    _png = _ctx.emit_figure("stamped", _fig, caption="a panel whose tick labels reach far "
                                                     "below the axes on purpose", close=False)
    _fig.canvas.draw()
    _r = _fig.canvas.get_renderer()
    _stamp = [t for t in _fig.texts if getattr(t, "_scprofile_provenance", False)]
    ck("the panel is stamped", len(_stamp) == 1)
    _low = min(t.get_window_extent(_r).y0 for t in _ax.get_xticklabels())
    ck("and the stamp's top is below the lowest tick label",
       bool(_stamp) and _stamp[0].get_window_extent(_r).y1 <= _low + 0.5,
       f"stamp top {(_stamp[0].get_window_extent(_r).y1 if _stamp else None)}, lowest tick "
       f"{_low}")
    _rec = _ctx._figures[-1]
    ck("and no collision with the stamp is recorded",
       not any("sample" in str(a.get("detail")) for a in _rec.get("audit") or []),
       str(_rec.get("audit")))
    plt.close(_fig)

print("\nit is wired where every figure passes, and the record carries both halves")
ck("emit_figure repairs before it records", "_FA.audit_and_repair(fig)" in src)
ck("and so does figure.save, the other save path",
   "audit_and_repair(fig)" in _insp.getsource(F.save))
_e2 = _M._figure({"id": "F1", "path": "figures/F1.png", "caption": "c", "audit": [],
                  "repairs": [{"code": "tick_thin", "what": "x thinned to 4"}]},
                 rel=lambda x: str(x))
ck("the serialiser carries the repairs", _e2.get("repairs") == [{"code": "tick_thin",
                                                                 "what": "x thinned to 4"}],
   str(_e2))
ck("and a panel that needed none carries no repairs key", "repairs" not in _clean)

print("\n" + ("the audit holds" if not FAIL else f"{len(FAIL)} FAILED: {FAIL}"))
sys.exit(1 if FAIL else 0)
