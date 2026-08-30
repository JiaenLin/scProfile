"""Design the evidence from the biology, then resolve it — and keep the two steps apart.

Merged, the question silently becomes "what can we draw?", and the answer is whatever the host
already draws. That is how a cell-cell communication section came to rest on three panels for a
design supporting seven questions.
"""
import importlib.util
from pathlib import Path

from scprofile import evidence as E

ROOT = Path(__file__).resolve().parents[1]


def _plugin(name="cellchat"):
    sp = importlib.util.spec_from_file_location(name, ROOT / "kernels" / f"{name}.py")
    m = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    return m.PLUGIN


def test_the_needs_registry_names_no_method_and_no_panel():
    """DESIGN IS ASKED OF THE BIOLOGY. A need mentioning a tool has already been resolved."""
    banned = ("cellchat", "liana", "netvisual", "seurat", "scanpy", "heatmap", "scatter",
              "barplot", "dotplot", "umap", "panel")
    for nid, (what, why) in E.NEEDS.items():
        text = f"{what} {why}".lower()
        hit = [b for b in banned if b in text]
        assert not hit, f"need {nid!r} names a method or a drawing: {hit}"


def test_every_question_kind_has_needs():
    for kind in ("cohort", "marginal", "simple", "interaction"):
        assert E.needs_for(kind), kind


def test_an_interaction_needs_its_two_halves_shown():
    """An interaction is a statement about two differences."""
    ids = {n for n, _w, _y in E.needs_for("interaction")}
    assert "who_changed" in ids and "what_carries_it" in ids, ids


def test_native_is_preferred_over_host():
    spec = {"report": {"provides_evidence": {"who_changed": ["native:someFn", "host:diff_matrix"]}}}
    route, provider, _ = E.resolve("who_changed", spec)
    assert (route, provider) == ("native", "someFn"), (route, provider)


def test_host_is_used_when_no_native_route_exists():
    spec = {"report": {"provides_evidence": {"who_changed": ["host:diff_matrix"]}}}
    assert E.resolve("who_changed", spec)[:2] == ("host", "diff_matrix")


def test_an_unrouted_need_is_unresolved_and_that_is_an_answer():
    assert E.resolve("who_changed", {})[0] == "unresolved"


def test_a_plugin_declares_its_own_routes_and_the_host_asserts_none():
    """Nothing outside the plugin may claim what the plugin can answer."""
    src = (ROOT / "scprofile" / "evidence.py").read_text()
    assert "netVisual" not in src and "rankNet" not in src, (
        "the host names a wrapped tool's functions; those belong in the plugin's declaration")


def test_cellchat_leaves_abundance_versus_intensity_unresolved():
    """The gap is deliberate and must stay visible: CellChat cannot separate the two.

    Its probability rises with the number of cells expressing a ligand, so a population that
    doubles in abundance signals more with no per-cell change. A declared route here would claim
    an answer the method does not have.
    """
    route, _p, _w = E.resolve("abundance_or_intensity", _plugin())
    assert route == "unresolved", (
        "cellchat now claims to separate abundance from per-cell intensity; if that is real it "
        "needs a citation in UPSTREAM.md, and if it is not it is a false claim in a declaration")


def test_cellchat_covers_most_of_what_a_marginal_effect_needs():
    met, total, unmet = E.coverage("marginal", _plugin())
    assert total >= 6, total
    assert met >= total - 2, (met, total, unmet)


def test_coverage_is_zero_for_a_plugin_declaring_nothing():
    met, total, _u = E.coverage("marginal", {})
    assert met == 0 and total > 0


if __name__ == "__main__":
    import sys
    bad = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  ok   {name}")
            except AssertionError as e:
                bad += 1
                print(f"  FAIL {name}: {str(e)[:180]}")
    sys.exit(1 if bad else 0)
