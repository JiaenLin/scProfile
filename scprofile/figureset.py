"""The figure set: every plate a run keeps, named by what it is, in the order of the argument,
laid into lettered figures with a legend a journal would print (harness ADR-0024, step 3).

WHAT A READER WAS HANDED BEFORE THIS. Plates sat where the drawing side wrote them -
`kernels/<plugin>/compare/dose | time = late/figures/nativecmp_diff_thing.png` - a pipe
and two spaces in the directory, the drawing side's prefix in the name, nothing in either saying
where in the argument the plate belongs. The paper printed one figure per plate, in the order the
sentences happened to cite them, with the run key and the source path under each. A journal
prints lettered figures in the order of the argument, each with a legend that has a title
sentence and one clause per panel.

THE SET IS DERIVED, NEVER DRAWN. Nothing here makes a picture except the composite, which lays
existing plates side by side; every plate is copied from where the run wrote it, and the index
records the source of every panel. It is rebuilt with the report and it is safe to rebuild: the
previous set's own files are the only thing it removes.

THE PATH IS THE PLACE IN THE ARGUMENT:

    report/figures/<axis>/<subject>/<NN>_<what>.png

`axis` is one of the layout's axes - cohort, group, contrast, interaction, sample - `subject` is
the arm, the contrast (`dose_within_late`), the direction of the interaction or the sample, `NN`
the plate's order within its subject and `what` the entry's own name with the drawing side's
prefix and the host's suffix removed. The cohort has one subject, itself, and no subject level.
Nothing here knows any method: the axis comes from where the reporter placed the plate and the
plan entry that claims it, the subject from the design, the name from the entry.
"""
import json
import math
import re
import shutil
from pathlib import Path

#: The main figures, in the order they are read; everything on `SUPPLEMENTARY` axes is numbered
#: S1, S2, ... after them. The cohort is read first because it says what the groups are; the
#: interaction is read last because it is the question the design was built to answer.
AXES_ORDER = ("cohort", "group", "contrast", "interaction")
SUPPLEMENTARY = ("sample",)

#: How many panels one figure carries at most: two rows of three at double-column width.
MAX_PANELS = 6
LETTERS = "abcdefghijklmnopqrstuvwxyz"

#: THE AXIS OF EVERY PANEL THE HOST DRAWS ITSELF, keyed by the kind `panels.IMPLEMENTED` names.
#: The host's own knowledge about its own panels; `tests/` holds it to that registry so a kind
#: the host learns to draw cannot arrive without a place in the argument.
HOST_AXIS = {
    "across_design": "cohort", "unit_presence": "cohort", "unit_totals": "cohort",
    "diff_matrix": "contrast", "flow_compare": "contrast", "role_shift": "contrast",
    "interaction": "interaction",
    "circle": "group", "chord": "group", "matrix": "group", "role_scatter": "group",
    "flow_rank": "group", "role_heatmap": "group", "contribution": "group",
}

#: The order the host's own panels are read in, on any axis, where the plugin declares none.
HOST_ORDER = ("across_design", "unit_presence", "unit_totals", "diff_matrix", "flow_compare",
              "role_shift", "interaction", "circle", "chord", "matrix", "role_scatter",
              "flow_rank", "role_heatmap", "contribution")

_PREFIX = re.compile(r"^(?:native_|nativecmp_|[A-Z]\d*_)")
_UNIT_TAG = re.compile(r"^\s*\[[^\]]+\]\s*")
_PROVENANCE = re.compile(r"\s*Drawn by (?:the tool's own [A-Za-z0-9_.]+\(\)|the wrapped tool|"
                         r"this plugin from [A-Za-z0-9_.]+\(\)'s own numbers, not by "
                         r"[A-Za-z0-9_.]+\(\) itself|this plugin from the tool's own numbers)\.")
_ALONE = re.compile(r"\s*This panel describes \S+ alone and is not a comparison\.")


def index_name(plugin):
    return f"{plugin}_figures.json"


def _clean(s):
    return re.sub(r"_+", "_", "".join(ch if ch.isalnum() or ch in "._-" else "_"
                                      for ch in str(s))).strip("_")


def _raw_slug(label):
    """The suffix the host stamps on its own files for a label: the same rule, not a copy."""
    return "".join(ch if ch.isalnum() else "_" for ch in str(label)).strip("_")


def subject_of_contrast(label):
    """`F | G = g` -> `F_within_g`; `F` -> `F`; anything else cleaned."""
    m = re.match(r"^\s*(\S+)\s*\|\s*(\S+)\s*=\s*(.+?)\s*$", str(label))
    if m:
        return f"{_clean(m.group(1))}_within_{_clean(m.group(3))}"
    return _clean(label)


def _arm_subject(label, design, factors):
    """The unit the run named for an arm label `dose = high, time = late`, or the label cleaned."""
    from . import units as _U

    row = {}
    for part in str(label).split(","):
        k, _, v = part.partition("=")
        if k.strip() and v.strip():
            row[k.strip()] = v.strip()
    name = _U.group_label(row, factors) if factors else None
    return str(name) if name else _clean(label)


def _stems():
    from . import compose as _C
    return _C._stems()


def _host_kind(fid, stems):
    """The kind of a host panel from its id, longest stem first, or ""."""
    fid = str(fid or "")
    for kind, stem in sorted(stems.items(), key=lambda kv: -len(kv[1])):
        if fid.startswith(stem):
            return kind
    return ""


def _what(stem, plugin, suffixes):
    s = str(stem)
    if s.startswith(f"{plugin}_"):
        s = s[len(plugin) + 1:]
    s = _PREFIX.sub("", s)
    for suf in sorted({x for x in suffixes if x}, key=len, reverse=True):
        if s.endswith("__" + suf):
            s = s[:-(len(suf) + 2)]
            break
    if s == "across_design":
        s = "design"
    return _clean(s.replace("__", "_")) or "panel"


def _panel_legend(caption, label=""):
    t = " ".join(str(caption or "").split())
    t = _UNIT_TAG.sub("", t)
    if label and t.startswith(f"{label}: "):
        t = t[len(label) + 2:]
    t = _PROVENANCE.sub("", t)
    t = _ALONE.sub("", t)
    return t.strip()


def _panels_json(run, plugin):
    try:
        return json.loads((Path(run) / "report" / "panels.json").read_text(encoding="utf-8")) \
                   .get(plugin) or {}
    except (OSError, ValueError):
        return {}


def plates(run, plugin, spec, design, pay):
    """[{axis, subject, id, what, source, caption, drawn_by, function, order}] - every plate.

    FROM THE RUN'S OWN RECORDS, three of them: `panels.json` for what the reporter placed (the
    host's own panels and the plates of the comparison phases), and the plugin's manifest in
    `report.json` for the per-unit plates. A plate on disk that none of them records is not in
    the set: a file whose origin cannot be named must not reach a page, which is the rule the
    reporter already keeps.
    """
    from . import declare as _DC
    from . import native as _NAT
    from . import units as _U

    run = Path(run)
    pay = pay or {}
    design = design or {}
    entries = _DC.report_figures(spec)
    order_of = {str(e.get("id") or ""): i for i, e in enumerate(entries)}
    by_id = {str(e.get("id") or ""): e for e in entries}
    declared = _NAT.declared_from(spec)
    factors = _U.biological_factors(design) if design else []
    stems = _stems()
    from . import compose as _C
    _place = _C._positions(spec)
    rep = (spec or {}).get("report") or {}
    host_list = list(_DC.report_get(rep, "host_panels") or []) or list(HOST_ORDER)
    unit_axis = pay.get("unit_axis") or {}
    from . import compare_panel as _CP
    try:
        pairs = _CP.interaction_specs(design, controls=pay.get("controls") or {}) if design else []
    except Exception:                                                     # noqa: BLE001
        pairs = []
    pair_subject = f"{pairs[0][0]}_x_{pairs[0][1]}" if pairs else "interaction"
    contrast_labels = {}
    out, seen = [], set()

    def _add(rec):
        if rec["source"] in seen or not (run / rec["source"]).is_file():
            return
        seen.add(rec["source"])
        # A KIND DRAWN AND NOT WRITTEN FROM (`appendix`) is a supplementary figure: still in
        # the set, still lettered and legended, numbered S1, S2, ... after the main figures.
        rec["position"] = _place(rec["source"]) if rec["drawn_by"] != "host" else "contrast"
        out.append(rec)

    pj = _panels_json(run, plugin)
    for group in ("cohort", "contrast", "arm", "native", "interaction"):
        for f in (pj.get(group) or []):
            rel = str(f.get("path") or "")
            fid = str(f.get("id") or "")
            label = str(f.get("label") or "")
            cap = f.get("caption")
            if isinstance(cap, (list, tuple)):
                cap = " ".join(str(x) for x in cap if x)
            stem = Path(rel).stem
            kind = _host_kind(fid, stems)
            if kind and group != "native":
                axis = HOST_AXIS.get(kind, "cohort")
                rank = host_list.index(kind) if kind in host_list else len(host_list)
                if axis == "contrast":
                    subject = subject_of_contrast(label)
                    contrast_labels[subject] = label
                    suffixes = [_raw_slug(label)]
                elif axis == "group":
                    subject = _arm_subject(label, design, factors)
                    suffixes = [_raw_slug(label)]
                elif axis == "interaction":
                    tail = fid[len(stems[kind]):].lstrip("_")
                    subject = _clean(tail.replace("__x__", "_x_")) or pair_subject
                    suffixes = [tail]
                else:
                    subject, suffixes = "", ["cohort"]
                _add({"axis": axis, "subject": subject, "id": fid.split("__")[0],
                      "what": _what(stem, plugin, suffixes), "source": rel,
                      "caption": _panel_legend(cap, label), "drawn_by": "host", "function": "",
                      "order": (0, rank, stem)})
                continue
            # A PLATE OF A COMPARISON PHASE: the entry that claims it says who drew it.
            fn, eid = _NAT.who_drew(spec, declared, rel)
            e = by_id.get(eid) or {}
            if label:
                axis, subject = "contrast", subject_of_contrast(label)
                contrast_labels[subject] = label
                suffixes = []
            else:
                # ACROSS THE ARMS: a plate named for a direction of the interaction carries it
                # as the last `__` segment of its own name - the plugin's naming, read back the
                # same way the host reads a per-item file - and one that names no direction is
                # the cross itself.
                axis = "interaction"
                tail = stem.split("__")[-1] if "__" in stem else ""
                subject = _clean(tail) if tail else pair_subject
                suffixes = [tail] if tail else []
            _add({"axis": axis, "subject": subject, "id": eid or stem,
                  "what": _what(stem, plugin, suffixes), "source": rel,
                  "caption": _panel_legend(cap, label),
                  "drawn_by": str(e.get("drawn_by") or ("tool" if fn else "plugin")),
                  "function": fn or "",
                  "order": (1, order_of.get(eid, len(entries)), stem)})
    # THE PER-UNIT PLATES, from the plugin's manifest, filed by the unit's axis. A marginal pool
    # draws nothing under a layout; a plate of one is not in the set.
    for f in ((pay.get("kernels") or {}).get(plugin) or {}).get("figures") or []:
        unit = str(f.get("unit") or "")
        rel = str(f.get("path") or "")
        if not unit or not rel:
            continue
        axis = str(unit_axis.get(unit) or "")
        if axis not in ("sample", "group"):
            continue
        stem = Path(rel).stem
        fn, eid = _NAT.who_drew(spec, declared, rel)
        if entries and not eid:
            continue                     # a plan exists and this plate is not on it
        e = by_id.get(eid) or {}
        _add({"axis": axis, "subject": unit, "id": eid or str(f.get("id") or stem),
              "what": _what(stem, plugin, []), "source": rel,
              "caption": _panel_legend(f.get("caption")),
              "drawn_by": str(f.get("drawn_by") or e.get("drawn_by") or ("tool" if fn else "plugin")),
              "function": fn or "", "order": (1, order_of.get(eid, len(entries)), stem)})
    return out, contrast_labels


def _subject_order(axis, subjects, design, pay, contrast_labels):
    """The subjects of one axis in the order they are read."""
    from . import compose as _C

    controls = (pay or {}).get("controls") or {}
    if axis == "group":
        ref = _C.reference_unit(design, controls, subjects)
        return ([ref] if ref in subjects else []) + sorted(s for s in subjects if s != ref)
    if axis == "contrast":
        labels = {contrast_labels.get(s, s): s for s in subjects}
        ordered = _C._order(labels, design, controls) if design else sorted(labels)
        return [labels[l] for l in ordered] + sorted(s for s in subjects
                                                     if s not in {labels[l] for l in ordered})
    if axis == "interaction":
        pair = [s for s in subjects if "_x_" in s]
        return sorted(pair) + sorted(s for s in subjects if s not in pair)
    return sorted(subjects)


def _arm_phrase(unit, design, pay):
    from . import units as _U

    mem = ((pay or {}).get("unit_members") or {}).get(unit) or []
    factors = _U.biological_factors(design) if design else []
    row = (design or {}).get(mem[0]) if mem else None
    if row and factors:
        return " ".join(str(row.get(f)) for f in factors if row.get(f) is not None)
    return str(unit).replace("_", " ")


def _n_phrase(unit, pay):
    mem = ((pay or {}).get("unit_members") or {}).get(unit) or []
    cells = sum((((pay or {}).get("label_by_unit") or {}).get(unit) or {}).values())
    bits = []
    if mem:
        bits.append(f"n = {len(mem)} sample" + ("s" if len(mem) != 1 else ""))
    if cells:
        bits.append(f"{int(cells):,} cells")
    return ", ".join(bits)


def title_for(axis, subject, spec, design, pay, contrast_labels):
    """The legend's title sentence, from the plugin's subject and the design: no method, no reading."""
    from . import compare_panel as _CP

    S = str(((spec or {}).get("report") or {}).get("subject") or "the result").strip()
    S = S[:1].upper() + S[1:]
    pay = pay or {}
    if axis == "cohort":
        return f"{S} across the design.", ""
    if axis == "group":
        return f"{S} in the {_arm_phrase(subject, design, pay)} arm.", _n_phrase(subject, pay)
    if axis == "sample":
        return f"{S} in sample {subject}.", _n_phrase(subject, pay)
    if axis == "contrast":
        label = contrast_labels.get(subject, subject)
        try:
            pairs = _CP.arm_pairs(design, controls=pay.get("controls") or {}) if design else []
        except Exception:                                                 # noqa: BLE001
            pairs = []
        for lab, fac, lo, hi, lo_f, hi_f in pairs:
            if lab == label:
                within = ", ".join(f"{v}" for k, v in sorted(lo_f.items()) if k != fac)
                n_lo, n_hi = len(_CP._members(design, lo_f)), len(_CP._members(design, hi_f))
                return (f"{S}: {hi} versus {lo} {fac}" + (f" within {within}" if within else "")
                        + ".", f"n = {n_hi} versus {n_lo} samples")
        return f"{S}: {label}.", ""
    if axis == "interaction":
        m = re.match(r"^(.+?)_response_by_(.+)$", subject)
        if m:
            return f"{S}: the {m.group(1)} response by {m.group(2)}.", ""
        if "_x_" in subject:
            a, b = subject.split("_x_", 1)
            return f"{S}: the interaction of {a} and {b}.", ""
        return f"{S}: {subject.replace('_', ' ')}.", ""
    return f"{S}: {subject}.", ""


def legend_for(fig):
    """`Figure 3 | Title. n = 3 samples. (a) ... (b) ...` - the legend, as plain text."""
    head = f"{fig['label']} | {fig['title']}"
    if fig.get("n_phrase"):
        head += f" {fig['n_phrase']}."
    parts = [head]
    for p in fig.get("panels") or []:
        leg = str(p.get("legend") or "").strip()
        parts.append(f"({p['letter']}) " + (leg if leg else f"{p.get('what', 'panel')}."))
    return " ".join(parts)


def assemble(run, plugin, spec, design, pay):
    """The index of the set, computed and not written: {plugin, figures: [...]}.

    Every path is decided here so a reader of the index and the writer of the files agree; the
    files come from `build`, which walks this.
    """
    all_plates, contrast_labels = plates(run, plugin, spec, design, pay)
    by, chunks = {}, []
    for p in all_plates:
        by.setdefault((p["axis"], p["subject"]), []).append(p)
    figures, n_main, n_supp = [], 0, 0
    for axis in AXES_ORDER + SUPPLEMENTARY:
        subjects = sorted({s for a, s in by if a == axis})
        for subject in _subject_order(axis, subjects, design, pay, contrast_labels):
            items = sorted(by[(axis, subject)], key=lambda p: p["order"])
            base = f"report/figures/{axis}" + (f"/{subject}" if subject else "")
            for i, p in enumerate(items, 1):
                p["path"] = f"{base}/{i:02d}_{p['what']}.png"
            title, n = title_for(axis, subject, spec, design, pay, contrast_labels)
            main = [p for p in items if axis not in SUPPLEMENTARY and p.get("position") != "appendix"]
            extra = [p for p in items if p not in main]
            for supp, group in ((False, main), (True, extra)):
                for k in range(0, len(group), MAX_PANELS):
                    chunks.append((supp, group[k:k + MAX_PANELS], title, n, axis, subject, base))
    # THE MAIN FIGURES ARE NUMBERED FIRST, in the order of the argument; the supplementary
    # figures after them, in the same order.
    for want in (False, True):
        for supp, chunk, title, n, axis, subject, base in chunks:
            if supp != want:
                continue
            if supp:
                n_supp += 1
                num, label = n_supp, f"Supplementary Figure S{n_supp}"
            else:
                n_main += 1
                num, label = n_main, f"Figure {n_main}"
            figures.append({
                "n": num, "label": label, "supplementary": supp, "axis": axis,
                "subject": subject, "title": title, "n_phrase": n,
                "path": f"{base}/figure_{'S' if supp else ''}{num:02d}.png",
                "panels": [{"letter": LETTERS[j], "path": p["path"], "source": p["source"],
                            "id": p["id"], "what": p["what"], "drawn_by": p["drawn_by"],
                            "function": p["function"], "legend": p["caption"]}
                           for j, p in enumerate(chunk)]})
    return {"plugin": plugin, "figures": figures}


def _composite(run, out, chunk):
    """Lay the panels of one figure side by side, lettered, at journal width."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import gridspec, image as mimg

    from . import figure as _F

    imgs = []
    for p in chunk:
        try:
            imgs.append(mimg.imread(str(Path(run) / p["source"])))
        except Exception:                                                 # noqa: BLE001
            imgs.append(None)
    n = len(imgs)
    cols = 1 if n == 1 else (2 if n in (2, 4) else 3)
    rows = int(math.ceil(n / cols))
    width = _F.SINGLE if cols == 1 else _F.DOUBLE
    pw = width / cols
    heights = []
    for r in range(rows):
        row = [im for im in imgs[r * cols:(r + 1) * cols] if im is not None]
        asp = max((im.shape[0] / float(im.shape[1]) for im in row), default=0.75)
        heights.append(asp * pw + 0.18)
    fig = plt.figure(figsize=(width, sum(heights)))
    gs = gridspec.GridSpec(rows, cols, figure=fig, height_ratios=heights, wspace=0.04,
                           hspace=0.12, left=0.01, right=0.99, top=0.98, bottom=0.01)
    for i, (p, im) in enumerate(zip(chunk, imgs)):
        ax = fig.add_subplot(gs[i // cols, i % cols])
        if im is not None:
            ax.imshow(im, interpolation="lanczos")
        ax.set_axis_off()
        ax.set_title(p["letter"], loc="left", fontweight="bold", fontsize=9, pad=2)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(out), dpi=200, facecolor="white")
    plt.close(fig)


def read(run, plugin):
    """The written index, or None."""
    try:
        return json.loads((Path(run) / "report" / "figures" / index_name(plugin))
                          .read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def build(run, plugin, spec, design, pay, log=print):
    """Write the set: the copies, the composites and the index. Returns the index.

    REBUILT, NOT ACCUMULATED. The previous set's own files - and only those, read from the
    previous index - are removed first, so a rebuild after a plan changed leaves no plate of a
    figure that no longer exists.
    """
    run = Path(run)
    old = read(run, plugin) or {}
    for f in old.get("figures") or []:
        for rel in [f.get("path")] + [p.get("path") for p in (f.get("panels") or [])]:
            if rel and str(rel).startswith("report/figures/"):
                try:
                    (run / rel).unlink()
                except OSError:
                    pass
    idx = assemble(run, plugin, spec, design, pay)
    for f in idx["figures"]:
        for p in f["panels"]:
            dst = run / p["path"]
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(run / p["source"], dst)
        try:
            _composite(run, run / f["path"], f["panels"])
        except Exception as err:                                          # noqa: BLE001
            log(f"  figure {f['n']}: composite not drawn ({err})")
    d = run / "report" / "figures"
    d.mkdir(parents=True, exist_ok=True)
    (d / index_name(plugin)).write_text(json.dumps(idx, indent=1), encoding="utf-8")
    nm = sum(1 for f in idx["figures"] if not f["supplementary"])
    ns = len(idx["figures"]) - nm
    log(f"  figure set: {sum(len(f['panels']) for f in idx['figures'])} plate(s) in {nm} figure(s)"
        + (f" and {ns} supplementary" if ns else "") + f" under report/figures/")
    return idx


def index_or_assemble(run, plugin, spec, design, pay=None):
    """The index, written if it is, computed if it is not - one shape either way."""
    got = read(run, plugin)
    if got and got.get("figures"):
        return got
    if pay is None:
        try:
            pay = json.loads((Path(run) / "report.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pay = {}
    try:
        return assemble(run, plugin, spec, design if design is not None else pay.get("design"), pay)
    except Exception:                                                     # noqa: BLE001
        return {"plugin": plugin, "figures": []}


def citation_maps(idx):
    """({source: figure number} for the main figures, {source: (supp, number, letter)} for all)."""
    numbers, panels = {}, {}
    for f in (idx or {}).get("figures") or []:
        for p in f.get("panels") or []:
            panels[p["source"]] = (bool(f.get("supplementary")), int(f["n"]), p["letter"])
            if not f.get("supplementary"):
                numbers[p["source"]] = int(f["n"])
    return numbers, panels


def cite(panels, paths):
    """`" (Fig. 3b,c; Supplementary Fig. S1a)"` for these plates, or `""`."""
    by = {}
    for p in paths or ():
        got = panels.get(p)
        if got:
            by.setdefault((got[0], got[1]), set()).add(got[2])
    if not by:
        return ""
    bits = []
    for (supp, n), letters in sorted(by.items()):
        bits.append(("Supplementary Fig. S" if supp else "Fig. ") + str(n)
                    + ",".join(sorted(letters)))
    return " (" + "; ".join(bits) + ")"


def figure_labels(idx, *, axis=None, subject=None, supplementary=None):
    """The labels of the figures on one axis or subject, joined for a sentence, or ""."""
    figs = [f for f in (idx or {}).get("figures") or []
            if (axis is None or f["axis"] == axis) and (subject is None or f["subject"] == subject)
            and (supplementary is None or bool(f.get("supplementary")) == supplementary)]
    if not figs:
        return ""
    supp = bool(figs[0].get("supplementary"))
    ns = [f["n"] for f in figs]
    head = "Supplementary Fig. S" if supp else "Fig. "
    if len(ns) == 1:
        return f"{head}{ns[0]}"
    if ns == list(range(ns[0], ns[-1] + 1)):
        return f"{head}{ns[0]}" + ("–" if not supp else "–S") + f"{ns[-1]}"
    return ", ".join(f"{head}{n}" for n in ns)
