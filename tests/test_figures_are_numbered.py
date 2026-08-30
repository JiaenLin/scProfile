"""A paper numbers its figures, and its text points at them.

THE DEFECT. The composed section named measurements in prose while the figures sat under it in
an unordered block captioned with their FILENAMES. That was the whole of the legend a reader of
the paper got: nothing said what a panel showed, what its colours meant, or which sentence it
belonged to, so not one number in the text could be checked against one picture. The panel had
been made a mechanism and the paper's figure block had not, which is the same disconnection
between the two documents that this project has already fixed once, one level down.

WHAT IS CHECKED, and the order matters:

  1. NUMBERS ARE CONTIGUOUS FROM 1 and every numbered figure exists on disk. A gap means the
     index numbered something the page cannot print, and a reader meets "Figure 5" with four
     pictures above it.
  2. EVERY NUMBERED FIGURE IS CITED IN THE PROSE. A figure the text never points at is a plate
     the run pays for and nobody reads - which is exactly what happened to the differential
     heatmap and the role heatmaps, drawn on every run and placed in no paper.
  3. EVERY CITATION RESOLVES TO A PRINTED FIGURE. The failure that matters most, because it is
     the one a reader cannot detect: "Figure 3" in a sentence and a different plate printed
     under Figure 3 reads exactly like a correct citation.
  4. THE LEGEND IS THE CAPTION, NOT THE FILENAME, and it is printed WHOLE. `CAPTION_LEAD_WORDS`
     splits a caption into a lead and a disclosure, which is right for a page of a hundred
     panels and wrong for a paper: a legend that stops at 32 words is not a legend.
"""
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scprofile import compose as C                                        # noqa: E402
from scprofile import paper as P                                          # noqa: E402

FAILURES = []


def check(c, m):
    if not c:
        FAILURES.append(m)


PLUGIN = "demo"
# A wrapped tool with two of its own functions and a host panel, routed to three needs. Nothing
# here is any real method: the point is that the mechanism is driven by the DECLARATION.
SPEC = {
    "native_plots": {
        "drawNet": {"use": "figures/cmp_net_{count,weight}.png per arm pair"},
        "drawHeat": {"use": "figures/cmp_heat.png per arm pair"},
        "drawRole": {"use": "figures/cmp_role_<pattern>.png per arm pair"},
    },
    "report": {
        "provides_evidence": {
            "who_changed": ["native:drawNet", "native:drawHeat", "host:diff_matrix"],
            # A NEED SERVED ONLY BY THE HOST. `host:` routes were skipped by the composer, so a
            # panel the host drew and the figure panel placed never reached the paper at all.
            "how_much_total": ["host:unit_totals"],
            "what_carries_it": ["native:drawNet"],
            "direction": ["native:drawRole"],
            "presence_or_magnitude": ["host:unit_presence"],
            "specificity": ["native:drawHeat"],
        },
        "unit_network": {"table": "t.csv", "source": "s", "target": "t", "weight": "w",
                         "weight_name": "signal"},
    },
}
LABELS = ("time", "dose")
FIGS = {"cmp_net_count.png": "The differential network. Red is higher in the second arm.",
        "cmp_heat.png": "The same difference pair by pair, so a reader can find one.",
        "cmp_role_outgoing.png": "Outgoing role per population, both arms on a shared maximum."}

tmp = Path(tempfile.mkdtemp(prefix="scp_fignum_"))
try:
    run = tmp / "run"
    (run / "kernels" / PLUGIN / "tables").mkdir(parents=True)
    (run / "report").mkdir(parents=True)
    figdir = run / "kernels" / PLUGIN / "figures"
    figdir.mkdir(parents=True)

    rows = ["contrast,element,from,to,total_from,total_to,raw_from,raw_to,raw_delta,"
            "scales_agree,from_source,to_source"]
    for lab, (a, b) in zip(LABELS, (("early", "late"), ("low", "high"))):
        for i, el in enumerate(("ALPHA", "BETA", "GAMMA")):
            rows.append(f"{lab},{el},{a},{b},10,20,{i + 1},{2 * (i + 1)},{i + 1},True,"
                        f"unit '{a}',unit '{b}'")
    (run / "kernels" / PLUGIN / "tables" / f"{PLUGIN}_two_scale.csv").write_text(
        "\n".join(rows) + "\n", encoding="utf-8")

    native = []
    for lab in LABELS:
        for name, cap in FIGS.items():
            rel = f"kernels/{PLUGIN}/compare/{lab}/figures/{name}"
            (run / rel).parent.mkdir(parents=True, exist_ok=True)
            (run / rel).write_bytes(b"\x89PNG\r\n\x1a\n")
            native.append({"id": name, "path": rel, "caption": f"{lab}: {cap}", "label": lab})
    # A PLATE THE INDEX MUST NOT NUMBER: recorded by the reporter, never written to disk.
    native.append({"id": "ghost",
                   "path": f"kernels/{PLUGIN}/compare/time/figures/cmp_role_incoming.png",
                   "caption": "not on disk", "label": "time"})
    # The host's own cohort panel, recorded the way the reporter records it: an id whose stem
    # is the one `panels.IMPLEMENTED` names, and no contrast label, because it is about the run.
    hrel = f"kernels/{PLUGIN}/figures/{PLUGIN}_P2_unit_totals__cohort.png"
    (run / hrel).write_bytes(b"\x89PNG\r\n\x1a\n")
    cohort = [{"id": "P2_unit_totals", "path": hrel, "label": "",
               "caption": "Edges and total signal per unit, arms and samples on one axis."}]
    (run / "report" / "panels.json").write_text(
        json.dumps({PLUGIN: {"native": native, "cohort": cohort, "contrast": [], "arm": []}}),
        encoding="utf-8")
    (run / "report.json").write_text(
        json.dumps({"design": {}, "kernels": {PLUGIN: {"spec": SPEC}}}), encoding="utf-8")

    idx = C.figure_index(run, PLUGIN, SPEC, {})
    check(bool(idx), "figure_index returned nothing, so no figure in any paper can be numbered")
    check(hrel in idx,
          "a need served only by a `host:` route is numbered by nothing, so a panel the host "
          "drew and the figure panel placed never reaches the paper")

    # 1. contiguous, and every one on disk
    ns = sorted(idx.values())
    check(ns == list(range(1, len(ns) + 1)),
          f"figure numbers are not contiguous from 1: {ns}")
    missing = [p for p in idx if not (run / p).is_file()]
    check(not missing,
          f"the index numbers {len(missing)} figure(s) that are not on disk, so the paper cites "
          f"a number with no picture under it: {missing}")

    text = C.section(run, PLUGIN, spec=SPEC, design={}, run_key="testrun")
    cited = {int(n) for m in re.finditer(r"\(Figures? ([0-9,\s]+)\)", text)
             for n in m.group(1).replace(" ", "").split(",") if n}

    # 2. every numbered figure is pointed at
    uncited = sorted(set(idx.values()) - cited)
    check(not uncited,
          f"figure(s) {uncited} are numbered and never cited in the prose - a plate the run pays "
          f"for and the text never mentions")

    # 3. every citation resolves
    dangling = sorted(cited - set(idx.values()))
    check(not dangling,
          f"the text cites figure(s) {dangling} that the index does not carry, so a reader "
          f"following the citation finds a different plate or none")

    P.ensure_section(run, plugin=PLUGIN, spec=SPEC, design={}, run_key="testrun")
    page = P.render(run, run_key="testrun", plugin=PLUGIN)
    check(page is not None and Path(page).is_file(), "no paper was rendered at all")
    html = Path(page).read_text(encoding="utf-8") if page else ""

    # 4. the legend is the caption, whole, and each figure carries its number
    for path, n in sorted(idx.items(), key=lambda kv: kv[1]):
        check(f"Figure {n}." in html, f"the page prints no legend headed 'Figure {n}.'")
    for path, n in sorted(idx.items(), key=lambda kv: kv[1]):
        cap = next((f["caption"] for f in native + cohort if f["path"] == path), "")
        tail = cap.split()[-1].strip(".")
        check(tail and tail in html,
              f"Figure {n}'s legend does not carry its caption - the page ends at {tail!r} "
              f"missing, so the legend is a filename again")
    check("class=\"sub\"> Source:" in html or "Source:" in html,
          "the page does not say which file each figure came from")
finally:
    shutil.rmtree(tmp, ignore_errors=True)

if FAILURES:
    print("FAIL")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print(f"ok - figures numbered, cited both ways, and captioned with their own legend")
