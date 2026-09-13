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


# THE PLATE OF THE QUANTITY THE SENTENCE IS ABOUT (harness ADR-0020, step 3; found by the
# reviewer of blind 0006): one function draws a count plate and a strength plate, the route for
# `how_much_total` names the function, and the composed sentence about total STRENGTH cited the
# count plate first - so a writer's claim copied from it was withdrawn for the figure. A sentence
# about a quantity cites the plate that shows that quantity first.
SPEC2 = {
    "native_plots": {"drawBars": {"use": "figures/cmp_bars_<measure>.png per arm pair"}},
    "report": {"unit_network": {"weight_name": "interaction strength"},
               "provides_evidence": {"how_much_total": ["native:drawBars"]}},
}
with tempfile.TemporaryDirectory() as td:
    run = Path(td) / "run"
    (run / "kernels" / PLUGIN / "tables").mkdir(parents=True)
    (run / "report").mkdir(parents=True)
    (run / "kernels" / PLUGIN / "tables" / f"{PLUGIN}_two_scale.csv").write_text(
        "\n".join(rows) + "\n", encoding="utf-8")
    native = []
    for name in ("cmp_bars_count", "cmp_bars_weight"):
        rel = f"kernels/{PLUGIN}/compare/time/figures/{name}.png"
        (run / rel).parent.mkdir(parents=True, exist_ok=True)
        (run / rel).write_bytes(b"\x89PNG")
        native.append({"id": name, "path": rel, "caption": name, "label": "time"})
    (run / "report" / "panels.json").write_text(json.dumps(
        {PLUGIN: {"native": native, "cohort": [], "contrast": [], "arm": []}}))
    (run / "report.json").write_text(json.dumps(
        {"design": {}, "kernels": {PLUGIN: {"spec": SPEC2}}}))
    made2 = {s: cites for s, cites in C.claims(run, PLUGIN, SPEC2, {})}
    total2 = next((c for s, c in made2.items() if "times the total" in s), None)
    check(total2 is not None and len(total2) >= 2,
          f"the total sentence should cite both plates of the function: {total2}")
    check(total2 is not None and total2 and "weight" in total2[0],
          f"a sentence about total strength cites the strength plate first: {total2}")

# THE PLATE ON THE SENTENCE'S OWN BASIS (harness ADR-0021, step 1; found by the reviewer of
# blind 0007): the ratio sentence's totals are the host's, over the elements the two arms share;
# the plugin's `how_much_total` plate totals each arm over the pool of every arm, so the same arm
# showed a different number on the plate than in the sentence and all six composed ratio claims
# were narrowed. The host's own contrast plates state the shared-basis totals in their caption.
# The ratio sentence cites, first, a plate whose caption states its totals.
SPEC3 = {
    "native_plots": {"drawBars": {"use": "figures/cmp_bars.png per arm pair"}},
    "report": {"unit_network": {"weight_name": "interaction strength"},
               "provides_evidence": {"how_much_total": ["native:drawBars"]}},
}
with tempfile.TemporaryDirectory() as td:
    run = Path(td) / "run"
    (run / "kernels" / PLUGIN / "tables").mkdir(parents=True)
    (run / "report").mkdir(parents=True)
    (run / "kernels" / PLUGIN / "tables" / f"{PLUGIN}_two_scale.csv").write_text(
        "\n".join(rows) + "\n", encoding="utf-8")
    rel = f"kernels/{PLUGIN}/compare/time/figures/cmp_bars.png"
    (run / rel).parent.mkdir(parents=True, exist_ok=True)
    (run / rel).write_bytes(b"\x89PNG")
    native = [{"id": "cmp_bars", "path": rel, "caption": "totals over every arm's pool",
               "label": "time"}]
    hrel = f"kernels/{PLUGIN}/figures/{PLUGIN}_C1_diff_strength__time.png"
    (run / hrel).parent.mkdir(parents=True, exist_ok=True)
    (run / hrel).write_bytes(b"\x89PNG")
    contrast = [{"id": "C1_diff_strength__time", "path": hrel, "label": "time",
                 "caption": "Change per pair. The two arms' raw totals (10 and 20, 2.00x) are "
                            "not comparable and every weight here is that arm's own share."}]
    (run / "report" / "panels.json").write_text(json.dumps(
        {PLUGIN: {"native": native, "cohort": [], "contrast": contrast, "arm": []}}))
    (run / "report.json").write_text(json.dumps(
        {"design": {}, "kernels": {PLUGIN: {"spec": SPEC3}}}))
    made3 = {s: cites for s, cites in C.claims(run, PLUGIN, SPEC3, {})}
    sent3, total3 = next(((s, c) for s, c in made3.items() if "times the total" in s), (None, None))
    check(total3 is not None and total3 and total3[0] == hrel,
          f"the ratio sentence does not cite the plate whose caption states its totals first: {total3}")
    check(total3 is not None and rel in total3,
          f"the route's plate is still cited, after: {total3}")
    caps = {x["path"]: x["caption"] for x in native + contrast}
    check(sent3 is not None and total3 and C.caption_states(caps.get(total3[0], ""), [10.0, 20.0]),
          f"the first cited plate's caption does not state the sentence's totals: {total3}")

if FAILURES:
    print("FAILED:", *FAILURES, sep="\n  ")
    raise SystemExit(1)
print("ok - a composed claim cites what shows it, the plate of its quantity first, on its basis")
