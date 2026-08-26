"""A fixture plugin that needs a design and takes the contrast the planner decides.

rule-one: no-removal — this plugin subsets, filters and drops nothing. It reads a sample column,
maps it through the design table to an arm label, and writes that label back as a per-cell
column. Every cell it is given appears in its output; the only "[...]" here are a column lookup
and a five-column slice of a matrix for a side-car, neither of which removes an observation.

IT EXISTS BECAUSE A THREE-HOUR RUN FOUND THIS AND NOTHING BEFORE IT DID. The planner computed
`~ age + diet + age:diet`, printed it in the plan and in the run log, handed it to the two
plugins that read `ctx.params["contrast"]` - and both refused the entire run with `no such
parameter ['contrast']`, because a `config` key is a knob the USER sets, an injected capability
is something the HOST hands the plugin, and the resolver validated the whole mapping as though
it were all config.

Every check that could have caught it runs in one second on a workstation. None of them did,
because the smoke test had no design table, no design-testing plugin, and a fixture with four
samples - which cannot express a 2x2 with replication, so the interaction branch was unreachable
even in principle.

This plugin computes nothing. It asserts the channel: that a design reaches it, and that the
contrast the planner decided arrives with it.
"""
from __future__ import annotations

PLUGIN = {
    "name": "contrastee",
    "version": "0.1.0",
    "summary": "a site plugin that proves the plan's decision reaches a plugin that needs one",
    "language": "python",
    "needs_env": False,
    "design_aware": True,
    "sees": ["obs[sample]"],
    "inject": {"required": ["sample", "design"], "optional": ["contrast"]},
    "executor": {"cost": "trivial", "cores": 1},
    "produces": ["obs[contrastee_arm]"],
    "report": {
        "figures": [
            {"id": "F1_terms", "shows": "diagnostic",
             "question": "which terms did the plan decide this run should test, and did they "
                         "arrive at the plugin the plan decided them for?",
             "source": "figures/F1_terms.csv", "required": True},
        ],
    },
    "cannot_show": [
        "It computes nothing biological. It asserts that a decision made in the plan reaches "
        "the plugin the plan made it for.",
    ],
}


def run(ctx):
    import pandas as pd

    con = ctx.params.get("contrast") or {}
    terms = list(con.get("terms") or [])
    if not con:
        # A REFUSAL, NOT AN EXCEPTION. The host records a refusal as a result, and this one names
        # exactly which link of the chain is broken.
        return ctx.refuse(
            "the contrast the planner decided",
            "no `contrast` arrived in params. The planner decides one for any plugin declaring "
            "`design` in inject.required and `contrast` in inject.optional, and delivers it "
            "through params. Nothing arrived, so either the decision was not made, was not "
            "delivered, or was dropped by the config resolver on the way.")

    ctx.log(f"contrast {con.get('kind')!r}: {con.get('formula')}")
    frame = pd.DataFrame({"term": terms,
                          "kind": [con.get("kind", "")] * len(terms),
                          "formula": [con.get("formula", "")] * len(terms)}).set_index("term")

    fig, ax = ctx.figure.SINGLE()
    ax.barh(range(len(terms)), [1] * len(terms))
    ax.set_yticks(range(len(terms)))
    ax.set_yticklabels(terms)
    ax.set_xlabel("delivered")
    ctx.emit_figure("F1_terms", fig, source=frame.reset_index(),
                    caption=f"The terms the planner decided and this plugin received: "
                            f"{con.get('formula')}. An empty panel would mean the decision was "
                            f"made and did not arrive.")

    # A per-cell column, so the host's across-the-design section has something to split. Every
    # cell gets a label; a cell whose sample is absent from the design table gets an empty one
    # rather than being dropped.
    first = terms[0] if terms else None
    des = ctx.design() if callable(getattr(ctx, "design", None)) else None
    if first and des:
        skey = (getattr(ctx, "keys", None) or {}).get("sample")
        try:
            lookup = {k: str(r.get(first, "")) for k, r in des.items()}
            arm = ctx.adata.obs[skey].astype(str).map(lookup).fillna("")
            ctx.emit_obs("contrastee_arm", arm.values)
        except Exception as e:                                            # noqa: BLE001
            ctx.log(f"  no per-cell arm column ({type(e).__name__}: {e})")

    ctx.headline = (f"{con.get('kind')} contrast delivered: {con.get('formula')} "
                    f"({len(terms)} term(s))")
    ctx.caveat("This plugin tests nothing biological. It reports whether the plan's decision "
               "reached the run, which is a fact about the tooling and not about the cohort.")


def selftest(ctx):
    """The channel, without a run: whatever is in params must reach the plugin."""
    import pandas as pd

    con = ctx.params.get("contrast") or {}
    fig, ax = ctx.figure.SINGLE()
    ax.barh([0], [1])
    ctx.emit_figure("F1_terms", fig,
                    source=pd.DataFrame({"term": list(con.get("terms") or ["none"])}),
                    caption="selftest")
    ctx.headline = f"selftest saw contrast={bool(con)}"
