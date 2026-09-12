"""A composed claim cites the plate that shows the quantity the sentence names.

Found by a cold reviewer (harness docs/blind/0004): 13 of the tool's 24 composed claims stated a
total interaction strength and cited the per-pair network and the per-pathway ranking, on which
no total appears, while the plate that shows the totals - the `how_much_total` route - went
uncited; and 7 claims counting the elements detected in one arm only cited the population
presence plate, a grid of cell populations with no element on it. Every one was narrowed or
withdrawn by a reader who opened the figures. The sentence and its evidence are one claim: the
total cites the totals, and an element detected in one arm cites the plates that show elements
per arm.
"""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scprofile import compose as C                                        # noqa: E402

FAILURES = []


def check(c, m):
    if not c:
        FAILURES.append(m)


PLUGIN = "demo"
SPEC = {
    "native_plots": {
        "drawBars": {"use": "figures/cmp_bars.png per arm pair"},
        "drawNet": {"use": "figures/cmp_net.png per arm pair"},
        "drawRank": {"use": "figures/cmp_rank.png per arm pair"},
        "drawBubble": {"use": "figures/cmp_bubble.png per arm pair"},
    },
    "report": {"provides_evidence": {
        "how_much_total": ["native:drawBars"],
        "who_changed": ["native:drawNet"],
        "what_carries_it": ["native:drawRank"],
        "specificity": ["native:drawBubble"],
        "presence_or_magnitude": ["host:unit_presence"],
    }},
}

with tempfile.TemporaryDirectory() as td:
    run = Path(td) / "run"
    (run / "kernels" / PLUGIN / "tables").mkdir(parents=True)
    (run / "report").mkdir(parents=True)
    rows = ["contrast,element,from,to,total_from,total_to,raw_from,raw_to,raw_delta,"
            "scales_agree,from_source,to_source",
            "time,ALPHA,early,late,10,20,1,2,1,True,unit 'early',unit 'late'",
            "time,BETA,early,late,10,20,0,3,3,True,unit 'early',unit 'late'"]
    (run / "kernels" / PLUGIN / "tables" / f"{PLUGIN}_two_scale.csv").write_text(
        "\n".join(rows) + "\n", encoding="utf-8")
    native = []
    for name in ("cmp_bars", "cmp_net", "cmp_rank", "cmp_bubble"):
        rel = f"kernels/{PLUGIN}/compare/time/figures/{name}.png"
        (run / rel).parent.mkdir(parents=True, exist_ok=True)
        (run / rel).write_bytes(b"\x89PNG")
        native.append({"id": name, "path": rel, "caption": name, "label": "time"})
    hrel = f"kernels/{PLUGIN}/figures/{PLUGIN}_P1_population_presence__cohort.png"
    (run / hrel).parent.mkdir(parents=True, exist_ok=True)
    (run / hrel).write_bytes(b"\x89PNG")
    cohort = [{"id": "P1_population_presence", "path": hrel, "label": "",
               "caption": "which populations each unit holds"}]
    (run / "report" / "panels.json").write_text(json.dumps(
        {PLUGIN: {"native": native, "cohort": cohort, "contrast": [], "arm": []}}))
    (run / "report.json").write_text(json.dumps(
        {"design": {}, "kernels": {PLUGIN: {"spec": SPEC}}}))

    made = {s: cites for s, cites in C.claims(run, PLUGIN, SPEC, {})}
    total = next((c for s, c in made.items() if "times the total" in s), None)
    only = next((c for s, c in made.items() if "detected in" in s), None)
    bars = f"kernels/{PLUGIN}/compare/time/figures/cmp_bars.png"
    rank = f"kernels/{PLUGIN}/compare/time/figures/cmp_rank.png"
    bubble = f"kernels/{PLUGIN}/compare/time/figures/cmp_bubble.png"
    check(total is not None, f"no total sentence was composed: {list(made)}")
    check(total is not None and bars in total,
          f"the total sentence does not cite the plate that shows the totals: {total}")
    check(only is not None, f"no one-arm-only sentence was composed: {list(made)}")
    check(only is not None and hrel not in only,
          f"the one-arm-only sentence cites the population presence plate: {only}")
    check(only is not None and (rank in only or bubble in only),
          f"the one-arm-only sentence cites no plate that shows elements per arm: {only}")

if FAILURES:
    print("FAIL")
    for x in FAILURES:
        print("  -", x)
    raise SystemExit(1)
print("ok: a composed claim cites the plate that shows what it says - the totals for a total, "
      "the per-element plates for an element detected in one arm")
