"""Every figure a run holds is measured and recorded - the host's own panels and the compare phase too.

WHAT THIS CLOSES (harness ADR-0019, step 1). Station 6b read "765 drawn and NOT measured by any
machine (432 recorded by the plugin's companion ..., 333 recorded by nothing)". The 333 were the
compare phase's plates and the host's own composed panels: `_Shim.emit_figure`, `draw_contrast`'s
`_save`, `draw_interaction` and `design_panel.draw` all ended in a plain `savefig` - no column fit,
no audit, no repair, a stamp at a fixed y - and `panels.json` recorded a path and a caption and
nothing about what was measured. Now one audited save serves them all, their records carry the
audit and the repairs, a compare plate's record says the companion drew it, and the station reads
`panels.json` beside `report.json`.

Run: python tests/test_every_figure_is_measured.py
"""
import json
import sys
import tempfile
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                                 # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scprofile import compare_panel as CP                                       # noqa: E402
from scprofile import design_panel as DP                                        # noqa: E402
from scprofile import figure as F                                               # noqa: E402
from scprofile import report as RP                                              # noqa: E402

FAIL = []


def ck(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'} {name}" + (f" — {detail}" if not cond else ""))
    if not cond:
        FAIL.append(name)


def dense():
    """Six numeric ticks on an axis too narrow for them: a collision the repertoire answers."""
    fig = plt.figure(figsize=(6, 2))
    ax = fig.add_axes([0.05, 0.35, 0.16, 0.55])
    ax.barh([0, 1, 2], [1, 1, 1])
    ax.set_xlim(0, 1)
    ax.set_xticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])
    return fig, ax


with tempfile.TemporaryDirectory() as td:
    d = Path(td)

    print("one audited save: the stamp from the rendered box, the audit, the repairs")
    fig, ax = dense()
    ax.set_xticklabels([f"{x:.1f}" for x in [0, 0.2, 0.4, 0.6, 0.8, 1.0]], rotation=90)
    entry = F.save(fig, d, "stamped", caption="a panel whose tick labels reach far below",
                   formats=("png",), stamp="arm A   ·   2 samples pooled", log=lambda *a: None)
    ck("the entry carries an audit list", isinstance(entry.get("audit"), list), str(entry))
    ck("and the file is where it says", Path(entry["path"]).is_file(), str(entry))
    fig, ax = dense()
    entry = F.save(fig, d, "colliding", caption="six ticks on a narrow axis", formats=("png",),
                   log=lambda *a: None)
    ck("a collision the repertoire answers is repaired and the entry says so",
       entry.get("audit") == [] and entry.get("repairs"), str(entry))

    print("\nthe host's own panels go through it")
    got = []
    shim = CP._Shim(d / "figs", "plug", "armA", got, label="arm A", members=("s1", "s2"))
    fig, ax = dense()
    shim.emit_figure("N9_test", fig, caption="a shim-drawn panel with a collision")
    ck("the shim collects a record beside the path",
       len(got) == 1 and len(got[0]) >= 5 and isinstance(got[0][4], dict), str(got))
    ck("and the record carries the audit and the repairs",
       got and got[0][4].get("audit") == [] and got[0][4].get("repairs"), str(got))
    ck("the first four elements are what every reader of the tuple expects",
       got and got[0][0] == "N9_test__armA" and Path(got[0][1]).is_file()
       and got[0][2].startswith("a shim") and got[0][3] == "arm A")

    print("\nthe reporter's record carries what was measured")
    rec = RP._panel_record(("N9_test__armA", got[0][1], "cap", "arm A",
                   {"audit": [{"code": "text_overlap", "detail": "x over y"}],
                    "repairs": [{"code": "tick_thin", "what": "thinned"}]}), out_dir=d / "figs")
    ck("audit and repairs are copied", rec.get("audit") and rec.get("repairs"), str(rec))
    rec2 = RP._panel_record(("NC_x_stem", got[0][1], ("lead", "rest"), "x", "kernels/p/compare/x.png",
                    {"measured": False, "drawn_by": "tool"}), out_dir=d / "figs")
    ck("a compare plate's record says the companion drew it and nothing measured it",
       rec2.get("measured") is False and rec2.get("drawn_by") == "tool", str(rec2))
    rec3 = RP._panel_record(("old", got[0][1], "cap", "x"), out_dir=d / "figs")
    ck("a record with nothing to say says nothing", "audit" not in rec3 and "measured" not in rec3)

    print("\nthe compare phase's plates are recorded from the companion's own account")
    cdir = d / "kernels" / "p" / "compare" / "c1" / "figures"
    cdir.mkdir(parents=True)
    fig, ax = dense()
    fig.savefig(cdir / "nativecmp_thing.png")
    plt.close(fig)
    (cdir / "captions.tsv").write_text("file\tcaption\tdrawn_by\nnativecmp_thing.png\ta plate "
                                       "the tool drew for this contrast\ttool\n")
    items = RP._native_panels(cdir, "c1", {}, d, "lo", "hi")
    ck("one item per plate", len(items) == 1, str(items))
    ck("with a trailing record saying measured: False and who drew it",
       items and isinstance(items[0][-1], dict) and items[0][-1].get("measured") is False
       and items[0][-1].get("drawn_by") == "tool", str(items[0][-1] if items else items))
    ck("and the relative path still where the page reads it",
       items and items[0][4] == "kernels/p/compare/c1/figures/nativecmp_thing.png", str(items))

    print("\nthe design panel returns its record")
    per_sample = {"s1": {"cells": 100.0, "edges": 10.0}, "s2": {"cells": 120.0, "edges": 12.0},
                  "s3": {"cells": 90.0, "edges": 20.0}, "s4": {"cells": 110.0, "edges": 25.0}}
    design = {"s1": {"age": "lo", "diet": "a"}, "s2": {"age": "lo", "diet": "b"},
              "s3": {"age": "hi", "diet": "a"}, "s4": {"age": "hi", "diet": "b"}}
    dest = d / "kernels" / "p" / "figures" / "p_across_design.png"
    dest.parent.mkdir(parents=True, exist_ok=True)
    got_d = DP.draw(per_sample, design, dest)
    ck("draw returns the count and the record",
       isinstance(got_d, tuple) and len(got_d) == 2 and isinstance(got_d[1], dict)
       and isinstance(got_d[1].get("audit"), list), str(got_d)[:200])
    ck("and the file exists", dest.is_file())

print("\nthe station reads panels.json beside report.json")
sys.path.insert(0, str(ROOT / "tests"))
import loop_stations as L                                                       # noqa: E402
with tempfile.TemporaryDirectory() as td:
    run = Path(td) / "20260101T000000Z__scprofile-abc1234__stage"
    figdir = run / "kernels" / "k" / "figures"
    figdir.mkdir(parents=True)
    for f in ("k_N2_chord__a", "nativecmp_x", "F1"):
        (figdir / f"{f}.png").write_bytes(b"\x89PNG")
    (run / "report.json").write_text(json.dumps({"kernels": {"k": {"figures": [
        {"id": "F1", "path": "kernels/k/figures/F1.png", "audit": []}]}}}))
    (run / "report").mkdir()
    (run / "report" / "panels.json").write_text(json.dumps({"k": {
        "cohort": [{"id": "N2_chord__a", "path": "kernels/k/figures/k_N2_chord__a.png",
                    "caption": "c", "label": "a", "audit": [],
                    "repairs": [{"code": "legend_out", "what": "moved"}]}],
        "native": [{"id": "NC_x", "path": "kernels/k/figures/nativecmp_x.png", "caption": "c",
                    "label": "x", "measured": False, "drawn_by": "tool"}]}}))
    led = run / "kernels" / "k" / "FIGURE_REVIEW.jsonl"
    import hashlib
    led.write_text("\n".join(json.dumps({"figure": f"kernels/k/figures/{f}.png",
                                         "sha256": hashlib.sha256(b"\x89PNG").hexdigest(),
                                         "note": f"a look at {f} and what it shows here",
                                         "reviewer": "l", "at": "2026-01-01T00:00:00Z"})
                             for f in ("k_N2_chord__a", "nativecmp_x", "F1")) + "\n")
    state, detail, _ = L.station_drawing([run])
    ck("a host panel recorded in panels.json counts as measured",
       "2 panel(s) measured" in detail, detail)
    ck("a compare plate recorded there counts as recorded by the companion",
       "1 drawn and NOT measured by any machine (1 recorded by the plugin's companion" in detail,
       detail)
    ck("and nothing is recorded by nothing", "0 recorded by nothing" in detail, detail)
    ck("the host's repairs are counted", "the host repaired 1 on 1 panel(s)" in detail, detail)

print("\n" + ("every figure is measured" if not FAIL else f"{len(FAIL)} FAILED: {FAIL}"))
sys.exit(1 if FAIL else 0)
