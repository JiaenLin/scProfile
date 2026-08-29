"""Redraw the host's panels from a finished run's tables, so you can LOOK at them.

WHY THIS IS COMMITTED. Every panel fixed in this tool was fixed by opening the image, and every
time that needed a harness - pull the per-unit tables, build a design, call the drawing code -
the harness was typed into a shell and thrown away. It was rebuilt from memory perhaps a dozen
times. The need is real and recurring, so it is a script, in the repository, and
`DEVELOPMENT.md` names it: use the CLI, or commit the script.

WHAT IT IS FOR, AND WHAT IT IS NOT. It draws into a directory OF YOUR CHOOSING from a run's
existing tables. It changes nothing in the run, promotes nothing, and its output is a VIEW - if
you want the panels a run delivers, they are already in that run. Use this while changing a
drawing function, to see the change on real data before it goes near a cluster.

    python tests/preview_panels.py --out RUNDIR --plugin cellchat --to /somewhere
    python tests/preview_panels.py --out RUNDIR --plugin cellchat --to /somewhere --arms-only

The design is read from the run's own report.json, so the arms and the confound audit are the
ones the run actually used rather than ones invented here.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", required=True, type=Path, help="a finished run directory")
    ap.add_argument("--plugin", required=True, help="which plugin's tables to draw from")
    ap.add_argument("--to", required=True, type=Path, help="where to write the preview")
    ap.add_argument("--arms-only", action="store_true",
                    help="skip the per-contrast panels and draw only each arm's own")
    a = ap.parse_args()

    try:
        import pandas as pd
    except ImportError:
        print("preview needs pandas; run it with an interpreter that has the run extra.",
              file=sys.stderr)
        return 2

    from scprofile import compare_panel as CP, figure as F
    F.use()

    pay = json.loads((a.out / "report.json").read_text(encoding="utf-8"))
    design = pay.get("design") or {}
    axis = pay.get("unit_axis") or {}
    spec = (((pay.get("report_spec") or {}).get(a.plugin)) or {}).get("unit_network") or {}
    if not spec:
        # THE DECLARATION IS READ FROM THE RUN, NOT FROM THE INSTALLED PLUGIN. A preview drawn
        # against today's declaration of a run made under yesterday's is a picture of neither.
        print(f"no unit_network declared for {a.plugin} in this run's report.json — that plugin "
              f"draws no host panels.", file=sys.stderr)
        return 2

    tbl = spec.get("table")
    per = {}
    for u, kind in sorted(axis.items()):
        f = a.out / "kernels" / a.plugin / u / tbl
        if not f.is_file():
            continue
        df = pd.read_csv(f)
        need = [spec.get("source", "source"), spec.get("target", "target"),
                spec.get("weight", "prob")]
        if not set(need) <= set(df.columns):
            continue
        per[u] = df.rename(columns=dict(zip(need, ("source", "target", "prob"))))
    if len(per) < 2:
        print(f"found {len(per)} unit table(s) under {a.out}/kernels/{a.plugin}; need at least 2.",
              file=sys.stderr)
        return 2

    a.to.mkdir(parents=True, exist_ok=True)
    made = []
    pairs = CP.arm_pairs(design)
    if not a.arms_only:
        for sp in pairs:
            made += CP.draw_contrast(per, design, sp, a.to, a.plugin,
                                     group_col=spec.get("group"),
                                     weight_scale=spec.get("weight_scale", "per_object"))
        for isp in CP.interaction_specs(design):
            made += CP.draw_interaction(per, design, isp, a.to, a.plugin,
                                        group_col=spec.get("group"),
                                        weight_scale=spec.get("weight_scale", "per_object"))
    made += CP.draw_arm_networks(per, design, CP.arms_in(design, pairs), a.to, a.plugin,
                                 group_col=spec.get("group"), member_col=spec.get("member"),
                                 weight_scale=spec.get("weight_scale", "per_object"))
    print(f"{len(made)} panel(s) drawn from {len(per)} unit(s) into {a.to}")
    for fid, path, cap, _label in made:
        lead = cap[0] if isinstance(cap, (list, tuple)) else cap
        print(f"  {fid}\n      {' '.join(str(lead).split())[:140]}")
    print("\nOPEN THEM. A drawing defect does not look like a defect, it looks like a finding.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
