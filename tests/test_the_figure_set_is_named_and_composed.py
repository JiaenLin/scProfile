"""The figure set: every plate a run keeps, named by what it is, in reading order, laid into
lettered figures with a legend a journal would print (harness ADR-0024, step 3).

WHAT A READER WAS HANDED. A run's plates sat where the tool and the plugin wrote them -
`kernels/<plugin>/compare/dose | time = late/figures/nativecmp_diff_thing.png` - with a
pipe and two spaces in the directory, the drawing side's prefix in the name, and nothing in
either saying where in the argument the plate belongs. The paper printed one figure per plate,
numbered in the order the sentences happened to cite them, with the legend the run key and the
source path attached. A journal prints lettered figures, in the order of the argument, each with
a legend that has a title sentence and one clause per panel; every plate is a panel of one.

Every check here is against the mechanism on a run invented for the purpose, so nothing passes
by recognising a real method's names. Run: python tests/test_the_figure_set_is_named_and_composed.py
"""
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

import matplotlib
matplotlib.use("Agg")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

FAIL = []


def ck(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'} {name}" + (f" — {detail}" if not cond else ""))
    if not cond:
        FAIL.append(name)


PLUGIN = "demo"
SUBJECT = "widget signalling"
SPEC = {
    "name": PLUGIN,
    "wraps": {"tool": "WidgetTool", "cite": "Someone et al., 2020"},
    "report": {
        "subject": SUBJECT,
        "unit_network": {"table": "t.csv", "source": "s", "target": "t", "weight": "w",
                         "weight_name": "signal"},
        "comparison_stats": {"table": "tables/x.csv", "element": "name", "pvalue": "p",
                             "test": "a rank test between the two arms"},
        "provides_evidence": {
            "who_changed": ["native:drawDiff", "host:diff_matrix"],
            "how_much_total": ["host:unit_totals"],
            "what_carries_it": ["native:drawFlow"],
            "direction": ["plan:own_dir"],
            "presence_or_magnitude": ["host:unit_presence"],
            "specificity": ["native:drawDiff"],
        },
        "figures": [
            {"id": "native_ring", "kind": "circle", "drawn_by": "tool", "fn": "drawRing",
             "axis": "unit", "position": "contrast",
             "legend": "Every population is a node on a ring; edge width is total signal."},
            {"id": "own_power", "kind": "unit_presence", "drawn_by": "plugin",
             "axis": "sample", "position": "appendix",
             "legend": "Cells, genes above the floor, and what was sent and received."},
            {"id": "native_roles", "kind": "role_scatter", "drawn_by": "tool", "fn": "drawRoles",
             "axis": "group", "position": "contrast",
             "legend": "Each population placed by how much it sends and receives."},
            {"id": "nativecmp_diff", "kind": "diff_matrix", "drawn_by": "tool", "fn": "drawDiff",
             "axis": "contrast", "position": "contrast", "items": "c('count', 'weight')",
             "at_most": 2,
             "legend": "Senders down the rows, receivers across; red is higher in the second arm."},
            {"id": "nativecmp_flow", "kind": "flow_compare", "drawn_by": "tool", "fn": "drawFlow",
             "axis": "contrast", "position": "contrast",
             "legend": "Every pathway ranked by its share of the total, one bar per arm."},
            {"id": "own_dir", "kind": "role_shift", "drawn_by": "plugin",
             "axis": "contrast", "position": "appendix",
             "legend": "Where each population moved between the arms; an arrow per population."},
            {"id": "nativecmp_inter", "kind": "interaction", "drawn_by": "plugin",
             "axis": "interaction", "position": "conclusion", "at_most": 2,
             "legend": "Does the response to one factor depend on the other; one point per pathway."},
            {"id": "nativecmp_totals", "kind": "unit_totals", "drawn_by": "tool",
             "fn": "drawTotals", "axis": "interaction", "position": "overview",
             "legend": "Total signal per arm, one bar per arm."},
        ],
    },
}

DESIGN = {"S1": {"dose": "low", "time": "early"}, "S2": {"dose": "low", "time": "early"},
          "S3": {"dose": "low", "time": "late"}, "S4": {"dose": "high", "time": "early"},
          "S5": {"dose": "high", "time": "late"}, "S6": {"dose": "high", "time": "late"}}
CONTROLS = {"dose": "low", "time": "early"}
ARMS = {"low_early": ["S1", "S2"], "low_late": ["S3"], "high_early": ["S4"],
        "high_late": ["S5", "S6"]}
MARGINS = {"low": ["S1", "S2", "S3"], "high": ["S4", "S5", "S6"],
           "early": ["S1", "S2", "S4"], "late": ["S3", "S5", "S6"]}
CONTRASTS = ["dose", "dose | time = early", "dose | time = late", "time", "time | dose = low",
             "time | dose = high"]


def _png(path, w=60, h=40):
    import numpy as np
    from matplotlib import image as _im
    path.parent.mkdir(parents=True, exist_ok=True)
    arr = np.zeros((h, w, 3))
    arr[..., 0] = np.linspace(0, 1, w)[None, :]
    _im.imsave(str(path), arr)


def _raw(label):
    return "".join(ch if ch.isalnum() else "_" for ch in label).strip("_")


def make_run(root):
    run = root / "run"
    kd = run / "kernels" / PLUGIN
    (run / "report").mkdir(parents=True)
    manifest, native, cohort, contrast, arm = [], [], [], [], []
    unit_axis, unit_members = {}, {}
    for s in DESIGN:
        unit_axis[s], unit_members[s] = "sample", [s]
        for fid in ("native_ring", "own_power"):
            rel = f"kernels/{PLUGIN}/{s}/figures/{fid}.png"
            _png(run / rel)
            manifest.append({"id": fid, "path": rel, "unit": s,
                             "caption": f"[{s}] {fid} legend for {s}. Drawn by the tool's own "
                                        f"drawRing().",
                             "drawn_by": "tool" if fid.startswith("native") else "plugin"})
    for g, mem in ARMS.items():
        unit_axis[g], unit_members[g] = "group", mem
        for fid in ("native_ring", "native_roles"):
            rel = f"kernels/{PLUGIN}/{g}/figures/{fid}.png"
            _png(run / rel)
            manifest.append({"id": fid, "path": rel, "unit": g,
                             "caption": f"[{g}] {fid} legend for {g}.", "drawn_by": "tool"})
    # A MARGINAL POOL: fitted for the marginal contrasts, and under the layout it draws nothing.
    # A stray plate in its directory must not enter the set.
    for g, mem in MARGINS.items():
        unit_axis[g], unit_members[g] = "margin", mem
        rel = f"kernels/{PLUGIN}/{g}/figures/native_ring.png"
        _png(run / rel)
        manifest.append({"id": "native_ring", "path": rel, "unit": g,
                         "caption": f"[{g}] stray", "drawn_by": "tool"})
    for lab in CONTRASTS:
        cdir = f"kernels/{PLUGIN}/compare/{lab}/figures"
        for stem in ("nativecmp_diff_count", "nativecmp_diff_weight", "nativecmp_flow", "own_dir"):
            rel = f"{cdir}/{stem}.png"
            _png(run / rel)
            native.append({"id": f"NC_{lab}_{stem}", "path": rel, "label": lab,
                           "caption": f"{lab}: {stem} legend. Drawn by the tool's own drawDiff()."})
        rel = f"kernels/{PLUGIN}/figures/{PLUGIN}_C1_diff_count__{_raw(lab)}.png"
        _png(run / rel)
        contrast.append({"id": f"C1_diff_count__{_raw(lab)}", "path": rel, "label": lab,
                         "caption": f"Change in significant interactions, {lab}."})
    for direction in ("dose_response_by_time", "time_response_by_dose"):
        for stem in (("nativecmp_inter_count", "nativecmp_inter_weight")
                     + (("nativecmp_inter_flow", "nativecmp_inter_flow_log", "nativecmp_inter_lr",
                         "nativecmp_inter_lr_scatter", "nativecmp_inter_prob")
                        if direction == "dose_response_by_time" else ())):
            rel = f"kernels/{PLUGIN}/compare/_across_arms/figures/{stem}__{direction}.png"
            _png(run / rel)
            native.append({"id": f"NC_{stem}__{direction}", "path": rel, "label": "",
                           "caption": f"{stem} by {direction}."})
    rel = f"kernels/{PLUGIN}/compare/_across_arms/figures/nativecmp_totals.png"
    _png(run / rel)
    native.append({"id": "NC_nativecmp_totals", "path": rel, "label": "",
                   "caption": "Totals per arm."})
    rel = f"kernels/{PLUGIN}/figures/{PLUGIN}_C5_interaction__dose__x__time.png"
    _png(run / rel)
    cohort.append({"id": "C5_interaction__dose__x__time", "path": rel, "label": "dose × time",
                   "caption": "The interaction of dose and time."})
    for stem, cap in (("P1_population_presence__cohort", "Which populations each unit has."),
                      ("P2_unit_totals__cohort", "Edges and total signal per unit."),
                      ("across_design", "Every unit laid over the design.")):
        rel = f"kernels/{PLUGIN}/figures/{PLUGIN}_{stem}.png"
        _png(run / rel)
        cohort.append({"id": stem, "path": rel, "label": "" if stem[0] == "P" else "cohort",
                       "caption": cap})
    # THE ARM PANELS THE HOST DREW: under the layout they are gone, and here they stay to prove
    # the set files them under the arm's own unit name rather than the label with spaces.
    for g, mem in ARMS.items():
        lab = ", ".join(f"{k} = {v}" for k, v in sorted(DESIGN[mem[0]].items()))
        rel = f"kernels/{PLUGIN}/figures/{PLUGIN}_N1_circle__{_raw(lab)}.png"
        _png(run / rel)
        arm.append({"id": f"N1_circle__{_raw(lab)}", "path": rel, "label": lab,
                    "caption": f"The pooled network of {lab}."})
    (run / "report" / "panels.json").write_text(json.dumps(
        {PLUGIN: {"native": native, "cohort": cohort, "contrast": contrast, "arm": arm}}),
        encoding="utf-8")
    pay = {"design": DESIGN, "controls": CONTROLS, "unit_axis": unit_axis,
           "unit_members": unit_members,
           "label_by_unit": {u: {"A": 100, "B": 50} for u in unit_axis},
           "kernels": {PLUGIN: {"spec": SPEC, "figures": manifest, "version": "1.0.0",
                                "caveats": []}}}
    (run / "report.json").write_text(json.dumps(pay), encoding="utf-8")
    (kd / "tables").mkdir(parents=True, exist_ok=True)
    rows = ["contrast,element,from,to,total_from,total_to,raw_from,raw_to,raw_delta,"
            "scales_agree,from_source,to_source"]
    for lab in CONTRASTS:
        for i, el in enumerate(("ALPHA", "BETA")):
            rows.append(f"{lab},{el},x,y,10,20,{i + 1},{2 * (i + 1)},{i + 1},True,"
                        f"unit 'x',unit 'y'")
    (kd / "tables" / f"{PLUGIN}_two_scale.csv").write_text("\n".join(rows) + "\n",
                                                            encoding="utf-8")
    return run, pay


from scprofile import figureset as FS                                          # noqa: E402
from scprofile import compose as C                                             # noqa: E402
from scprofile import paper as P                                               # noqa: E402

tmp = Path(tempfile.mkdtemp(prefix="scp_figset_"))
try:
    run, pay = make_run(tmp)
    idx = FS.build(run, PLUGIN, SPEC, DESIGN, pay)
    ck("the set is built and indexed", isinstance(idx, dict) and idx.get("figures"),
       str(idx)[:200])
    figs = idx.get("figures") or []
    plates = [p for f in figs for p in f["panels"]]

    print("\nevery plate is named by what it is, under its axis and subject")
    NAME = re.compile(r"^report/figures/(cohort|group|contrast|interaction|sample)/"
                      r"(?:([A-Za-z0-9_.-]+)/)?(\d\d)_([A-Za-z0-9_.-]+)\.png$")
    bad = [p["path"] for p in plates if not NAME.match(p["path"])]
    ck("every set path is figures/<axis>/<subject>/<NN>_<what>.png", not bad, str(bad[:4]))
    ck("no space, pipe or drawing-side prefix survives in a set path",
       not [p["path"] for p in plates
            if " " in p["path"] or "|" in p["path"]
            or re.search(r"/\d\d_(native_|nativecmp_|[A-Z]\d_)", p["path"])],
       str([p["path"] for p in plates if re.search(r"/\d\d_(native|nativecmp|[A-Z]\d_)",
                                                    p["path"])][:4]))
    ck("every set file exists and names an existing source",
       all((run / p["path"]).is_file() and (run / p["source"]).is_file() for p in plates))
    by_subject = {}
    for p in plates:
        m = NAME.match(p["path"])
        by_subject.setdefault((m.group(1), m.group(2)), []).append(int(m.group(3)))
    ck("the numbers run from 01 without a gap inside every subject",
       all(sorted(v) == list(range(1, len(v) + 1)) for v in by_subject.values()),
       str({k: sorted(v) for k, v in by_subject.items() if sorted(v) != list(range(1, len(v) + 1))}))
    subjects = {k[1] for k in by_subject if k[0] == "contrast"}
    ck("a conditional contrast is filed as <factor>_within_<level>",
       "dose_within_late" in subjects and "time_within_high" in subjects, str(sorted(subjects)))
    ck("a marginal contrast is filed under the factor alone", "dose" in subjects, str(sorted(subjects)))
    ck("an arm is filed under the unit the run named, not the label with spaces",
       {k[1] for k in by_subject if k[0] == "group"} == set(ARMS),
       str({k[1] for k in by_subject if k[0] == "group"}))
    ck("a sample is filed under its own name",
       {k[1] for k in by_subject if k[0] == "sample"} == set(DESIGN))
    inter = {k[1] for k in by_subject if k[0] == "interaction"}
    ck("the interaction is filed per direction, the cross under the pair",
       inter == {"dose_response_by_time", "time_response_by_dose", "dose_x_time"}, str(inter))
    ck("the cohort's plates sit directly under the axis",
       all(k[1] is None for k in by_subject if k[0] == "cohort"), str([k for k in by_subject if k[0] == "cohort"]))
    ck("a marginal pool's stray plate is not in the set",
       not any(p["source"].split("/")[2] in MARGINS for p in plates))
    whats = {p["path"].rsplit("/", 1)[-1][3:-4] for p in plates}
    ck("the what is the entry's own name without the drawing side's prefix",
       {"ring", "own_power", "roles", "diff_count", "diff_weight", "flow", "own_dir", "design",
        "population_presence", "unit_totals", "interaction", "circle", "totals", "inter_count",
        "inter_weight"} <= whats,
       str(sorted(whats)))
    ck("the host's panel loses the contrast suffix the host stamped on its file",
       "diff_count" in whats and not any(w.startswith("diff_count__") or w.endswith("_late")
                                         for w in whats if w.startswith("diff_count")))

    print("\nthe figures are lettered, bounded and numbered in the order of the argument")
    ck("no figure carries more than the panel ceiling",
       all(1 <= len(f["panels"]) <= FS.MAX_PANELS for f in figs))
    ck("panels are lettered a, b, c in order",
       all([p["letter"] for p in f["panels"]] == list("abcdefghijklmnopqrstuvwxyz"[:len(f["panels"])])
           for f in figs))
    main = [f for f in figs if not f.get("supplementary")]
    supp = [f for f in figs if f.get("supplementary")]
    ck("main figures are numbered 1..N contiguously",
       [f["n"] for f in main] == list(range(1, len(main) + 1)), str([f["n"] for f in main]))
    ck("supplementary figures are numbered S1..SM",
       [f["label"] for f in supp] == [f"Supplementary Figure S{i}" for i in range(1, len(supp) + 1)],
       str([f["label"] for f in supp][:3]))
    axes_seq = [f["axis"] for f in main]
    order = {"cohort": 0, "group": 1, "contrast": 2, "interaction": 3}
    ck("the cohort is read first, then the arms, the contrasts, the interaction last",
       axes_seq == sorted(axes_seq, key=order.get), str(axes_seq))
    ck("the per-sample figures are supplementary", any(f["axis"] == "sample" for f in supp)
       and supp)
    # A KIND DRAWN AND NOT WRITTEN FROM: `position: appendix` is a supplementary figure, still
    # in the set with its letter and legend, and never in the main numbering.
    apx = [p for f in figs for p in f["panels"] if p["id"] == "own_dir"]
    ck("an appendix-position plate is in the set", len(apx) == len(CONTRASTS), str(len(apx)))
    ck("and it is a supplementary figure, not a main one",
       all(f.get("supplementary") for f in figs for p in f["panels"] if p["id"] == "own_dir")
       and not any(p["id"] == "own_dir" for f in main for p in f["panels"]))
    ck("a subject keeps its main figure when only some of its plates are appendix",
       any(f["axis"] == "contrast" for f in main))
    grp = [f["subject"] for f in main if f["axis"] == "group"]
    ck("the reference arm's figure comes before the others", grp and grp[0] == "low_early", str(grp))
    con = [f["subject"] for f in main if f["axis"] == "contrast"]
    ck("the contrasts are read in the design's order, the control stratum first",
       con.index("dose_within_early") < con.index("dose_within_late"), str(con))
    ck("every composite exists as its own file",
       all((run / f["path"]).is_file() and f["path"].startswith("report/figures/") for f in figs))
    ck("a composite is not a panel of itself",
       not any(p["path"] == f["path"] for f in figs for p in f["panels"]))
    # BALANCED, NOT GREEDY (found on the first run with the set): seven plates of one direction
    # of the interaction became a figure of six and a figure of one.
    sizes = [len(f["panels"]) for f in figs if f["axis"] == "interaction"
             and f["subject"] == "dose_response_by_time"]
    ck("a subject's plates are laid into figures of nearly equal size",
       max(sizes) - min(sizes) <= 1 if sizes else True, str(sizes))
    ck("the balance keeps the ceiling", all(s <= FS.MAX_PANELS for s in sizes))
    ck("a seven-plate subject becomes four and three", FS._chunks(7) == [4, 3] and FS._chunks(13) == [5, 4, 4]
       and FS._chunks(6) == [6] and FS._chunks(1) == [1] and FS._chunks(12) == [6, 6], str(FS._chunks(7)))

    print("\nthe legend has a title sentence and one clause per panel")
    legs = [FS.legend_for(f) for f in figs]
    ck("every legend opens with the figure's label and a title sentence",
       all(l.startswith(f["label"] + " | ") and ". " in l for f, l in zip(figs, legs)),
       (legs[0][:80] if legs else ""))
    ck("every panel's letter heads its clause",
       all(f"({p['letter']}) " in l for f, l in zip(figs, legs) for p in f["panels"]))
    ck("the unit tag the page prefixed is not in the legend",
       not any(re.search(r"\[(S\d|low|high)", l) for l in legs))
    ck("the provenance sentence is not in the legend; it is in the record",
       not any("Drawn by the tool" in l for l in legs)
       and any(p.get("function") == "drawRing" for p in plates))
    ck("a legend names the subject the plugin declared",
       all(SUBJECT.split()[0] in l.lower() or "Widget" in l for l in legs[:1]))
    ck("the arm's legend says how many samples were pooled",
       any("n = 2 samples" in l for f, l in zip(figs, legs)
           if f["axis"] == "group" and f["subject"] == "high_late"),
       str([l[:120] for f, l in zip(figs, legs) if f["axis"] == "group"][:2]))
    ck("no legend says 'this run' or names a run key",
       not any("this run" in l.lower() or re.search(r"\d{8}T\d{6}Z", l) for l in legs))
    # THE REPORT'S COLOUR-KEY SENTENCE (found on the second run's page): the report stamps
    # "Population colours are the run's own map (key ...); ... every panel of this run" on a
    # caption, which is the record's business; a legend says it in the register, and only on
    # a plate that colours by population.
    legacy = ("Senders down the rows. Population colours are the run's own map (key 2380b7e8d228); "
              "the same label is the same colour in every panel of this run.")
    ck("a legend drops the colour-key sentence on a plate that colours by a scale",
       FS._panel_legend(legacy, kind="diff_matrix") == "Senders down the rows.",
       FS._panel_legend(legacy, kind="diff_matrix"))
    ck("and says it in the register on a plate that colours by population",
       FS._panel_legend(legacy, kind="circle") == "Senders down the rows. Populations keep one colour across every panel.",
       FS._panel_legend(legacy, kind="circle"))
    ck("a plate of no known kind keeps the sentence, in the register",
       "this run" not in FS._panel_legend(legacy) and "one colour" in FS._panel_legend(legacy))
    con_t = [f["title"] for f in figs if f["axis"] == "contrast" and f["subject"] == "dose_within_late"]
    ck("a contrast's title names the levels, the factor in brackets and the stratum",
       con_t and con_t[0] == "Widget signalling: high versus low (dose) within late.", str(con_t[:1]))
    coh = [f for f in figs if f["axis"] == "cohort"]
    ck("the cohort's legend says how many samples in how many arms",
       coh and "n = 6 samples in 4 arms" in FS.legend_for(coh[0]), FS.legend_for(coh[0])[:120] if coh else "")

    print("\nthe prose cites figure and panel, through the same index")
    fi = C.figure_index(run, PLUGIN, SPEC, DESIGN)
    ck("figure_index numbers every plate of the main figures by its composite",
       all(fi.get(p["source"]) == f["n"] for f in main for p in f["panels"]),
       str([(p["source"], fi.get(p["source"]), f["n"]) for f in main for p in f["panels"]
            if fi.get(p["source"]) != f["n"]][:3]))
    src = [p["source"] for p in main[2]["panels"][:2]]
    c = C.cite(fi, src, panels=C.figure_panels(run, PLUGIN, SPEC, DESIGN))
    ck("a citation names the figure and its panels", re.fullmatch(r" \(Fig\. \d+[a-z](,[a-z])*\)", c),
       repr(c))
    ck("an appendix plate is not in the main index and is cited as supplementary",
       not any(p["source"] in fi for p in apx)
       and C.cite(fi, [apx[0]["source"]], panels=C.figure_panels(run, PLUGIN, SPEC, DESIGN))
              .startswith(" (Supplementary Fig. S"))
    text = C.section(run, PLUGIN, spec=SPEC, design=DESIGN, run_key="testrun")
    cited = set()
    for m in re.finditer(r"Fig\. (\d+)(?:\u2013(\d+))?", text):
        cited |= set(range(int(m.group(1)), int(m.group(2) or m.group(1)) + 1))
    ck("every main figure is cited somewhere in the composed section",
       set(f["n"] for f in main) <= cited, str(sorted(set(f["n"] for f in main) - cited)))
    ck("the composed section is headed Results, in register",
       text.splitlines()[2].startswith("# Results") if len(text.splitlines()) > 2 else False,
       text.splitlines()[2] if len(text.splitlines()) > 2 else "")
    ck("no composed heading carries a raw contrast label or a design tag",
       not [l for l in text.splitlines() if l.startswith("#") and ("|" in l or "SIMPLE" in l)],
       str([l for l in text.splitlines() if l.startswith("#") and "|" in l][:2]))
    ck("the composed section does not say 'this run'", "this run" not in text.lower())
    ck("the interaction of two factors is headed once, as one pair",
       "## Interaction of dose and time" in text and "; time and dose" not in text,
       str([l for l in text.splitlines() if l.startswith("## Interaction")]))

    print("\nthe page prints the figures, lettered, with their legends and nothing of the run")
    P.ensure_section(run, plugin=PLUGIN, spec=SPEC, design=DESIGN, run_key="testrun")
    page = P.render(run, run_key="20260101T000000Z__demo__run", plugin=PLUGIN)
    html = Path(page).read_text(encoding="utf-8") if page else ""
    ck("a page was rendered", bool(html))
    ck("every main figure is printed with its label",
       all(f"Figure {f['n']} |" in html for f in main))
    ck("the supplementary figures are printed after the main ones",
       html.find("Supplementary Figure S1 |") > html.find(f"Figure {len(main)} |") > 0)
    ck("the page embeds the composites, not the plates",
       all(f["path"].rsplit("/", 1)[-1] in html for f in figs)
       and not any(p["path"].rsplit("/", 1)[-1] in html for p in plates[:5]))
    ck("the run key is not visible on the page",
       "20260101T000000Z" not in re.sub(r"<!--.*?-->", "", html, flags=re.S))
    ck("the page does not print a source path under each figure",
       not re.search(r"<figcaption>[^<]*(?:<[^>]+>[^<]*)*Source:", html))
    ck("the page carries a Methods section", "<h2>Methods</h2>" in html or ">Methods<" in html)
    meth = C.methods(run, PLUGIN, spec=SPEC, design=DESIGN, pay=pay)
    ck("the Methods name the comparisons with the factor bracketed, as the legends do",
       "high versus low (dose) within late" in meth, meth[:400])
    ck("and the declared test, the tool and its citation",
       "a rank test between the two arms" in meth and "WidgetTool" in meth and "Someone et al." in meth)

    print("\na section carried in must be in a manuscript's register")
    words = " ".join(["word"] * 250)
    for bad, why in (("In this run the effect was large. " + words, "this run"),
                     ("Run 20260101T000000Z__demo__run showed it. " + words, "a run key"),
                     ("## SIMPLE dose | time = late\n\n" + words, "a raw label heading"),
                     ("The plugin drew the network. " + words, "the apparatus")):
        try:
            P.write_draft(run, bad, author="w", plugin=PLUGIN)
            ck(f"a draft naming {why} is refused", False, "accepted")
        except P.Refused as err:
            ck(f"a draft naming {why} is refused", "register" in str(err), str(err)[:100])
    try:
        P.write_draft(run, "## Effect of dose within late\n\nSignal rose (Fig. 3b). " + words,
                      author="w", plugin=PLUGIN)
        ck("a draft in register is carried in", True)
    except P.Refused as err:
        ck("a draft in register is carried in", False, str(err)[:120])

    print("\na citation is checked by panel, not by the whole figure")
    # THE WRITER OF THE SECOND RUN wrote around four whole figures because one panel of each
    # carried a finding and the check keyed on the number: `Fig. 4b` was refused for `Fig. 4a`.
    from scprofile import review as RV
    tgt = main[1]                       # the first arm's figure: panels a.. from the plan
    flagged, clean = tgt["panels"][0]["source"], tgt["panels"][1]["source"]
    RV.record(run, flagged, "the ring's colours collide and the legend cannot key them apart",
              reviewer="eye", plugin=PLUGIN, defect=True)
    n = tgt["n"]
    try:
        P.write_draft(run, f"## Effect of dose\n\nSignal rose (Fig. {n}b). " + words, author="w",
                      plugin=PLUGIN)
        ck("a clean panel of a figure with a flagged sibling can be cited", True)
    except P.Refused as err:
        ck("a clean panel of a figure with a flagged sibling can be cited", False, str(err)[:160])
    try:
        P.write_draft(run, f"## Effect of dose\n\nSignal rose (Fig. {n}a). " + words, author="w",
                      plugin=PLUGIN)
        ck("the flagged panel itself is refused", False, "accepted")
    except P.Refused as err:
        ck("the flagged panel itself is refused", "open" in str(err), str(err)[:120])
    try:
        P.write_draft(run, f"## Effect of dose\n\nSignal rose (Fig. {n}). " + words, author="w",
                      plugin=PLUGIN)
        ck("the whole figure, cited without a panel, is refused while any panel is flagged", False, "accepted")
    except P.Refused as err:
        ck("the whole figure, cited without a panel, is refused while any panel is flagged", "open" in str(err))

    print("\nbuilding twice leaves one set")
    idx2 = FS.build(run, PLUGIN, SPEC, DESIGN, pay)
    files = sorted(str(p.relative_to(run)) for p in (run / "report" / "figures").rglob("*.png"))
    want = sorted({p["path"] for f in idx2["figures"] for p in f["panels"]}
                  | {f["path"] for f in idx2["figures"]})
    ck("the second build writes the same files and nothing else", files == want,
       str(sorted(set(files) ^ set(want))[:4]))
finally:
    shutil.rmtree(tmp, ignore_errors=True)

if FAIL:
    print(f"\n{len(FAIL)} FAILED: " + ", ".join(FAIL))
    sys.exit(1)
print("\nall ok")
