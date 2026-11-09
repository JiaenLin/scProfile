"""Every contrast is read against the control the run DECLARED - in the plan, in the host, in DE.

THE DEFECT (GAP-039; harness ADR-0027, P1; the blind record of `de`, docs/MIGRATIONS.md 1). The
host resolved a control per factor for its own panels and handed a plugin the TERMS alone. DE
chose each reference as `sorted(levels)[0]`, so on a design whose control sorts LAST every fold
change in its table ran the other way from every panel beside it - under a correctly-labelled
`contrast` column - and on a crossed design the interaction coefficient came back with its sign
reversed as well, because a formula's treatment coding takes the first level as its base. The
plan had no `--control` at all; a misspelt one on `run` was recorded and resolved to nothing.

WHAT THIS HOLDS, each part failing on the commit the blind record was taken at (f5175ea):
  1. the plan's contrast decision carries each term's control, its basis and the level order;
  2. a declared control the design does not have is refused by name;
  3. the host hands a plugin the order (`ctx.levels`) and a frame whose categories put the
     control first (`ctx.model_frame`);
  4. `scprofile plan` takes `--control`, prints the reference, and refuses a misspelt one;
  5. DE itself, run in this process on a 2x2 whose controls BOTH sort last: each main effect is
     `<treated level> vs <control>` with the planted genes positive, the interaction is named on
     the treated levels, and no caveat says the interaction was not contrasted.

NOBODY'S VOCABULARY: the factors are `f1` and `f2`, the levels the fixture's own words.
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scprofile import planner as PL                                          # noqa: E402

FAILS = []


def ck(name, ok, detail=""):
    print(("  ok   " if ok else "  FAIL ") + name + ("" if ok else f"\n         {detail}"))
    if not ok:
        FAILS.append(name)


class K:
    """A design-aware plugin as the planner sees one: it can be handed a contrast."""
    name, needs_design, injects_required, injects_optional = "k", True, ["design"], ["contrast"]


# Both controls sort LAST: "untreated" after "treated", "low" after "high".
CELLS = [("treated", "high"), ("treated", "low"), ("untreated", "high"), ("untreated", "low")]
DESIGN = {f"S{i}{j}": {"f1": a, "f2": b} for i, (a, b) in enumerate(CELLS) for j in (1, 2)}
CTRL = {"f1": "untreated", "f2": "low"}


def facts(controls=None):
    return PL.design_facts(DESIGN, ["f1", "f2"], "sample", sorted(DESIGN), controls=controls)


print("1. the plan's decision carries each term's control, its basis and the order")
try:
    con = PL.decisions_for(K(), facts(CTRL)).get("contrast") or {}
except TypeError as e:                       # f5175ea: design_facts takes no controls
    con = {}
    ck("design_facts takes the declared controls", False, repr(e))
ck("the contrast is the interaction of the two crossed factors",
   con.get("kind") == "interaction" and con.get("terms") == ["f1", "f2"], con)
ck("each term's control is the DECLARED one, though it sorts last",
   con.get("controls") == CTRL, con.get("controls"))
ck("and the basis says it was declared",
   all((con.get("control_basis") or {}).get(t) == "declared" for t in CTRL),
   con.get("control_basis"))
ck("the order a contrast reads them in puts the control first",
   con.get("levels") == {"f1": ["untreated", "treated"], "f2": ["low", "high"]},
   con.get("levels"))
try:
    con0 = PL.decisions_for(K(), facts()).get("contrast") or {}
except TypeError:
    con0 = {}
ck("undeclared, a level that reads as a control is recommended and the basis says so",
   (con0.get("controls") or {}).get("f1") == "untreated"
   and "recommended" in (con0.get("control_basis") or {}).get("f1", ""), con0)


print("\n2. a declared control the design does not have is refused, by name")
probs = (PL.declared_problems(facts({"f1": "ctrl", "dose": "zero"}))
         if hasattr(PL, "declared_problems") else None)
ck("the planner has the refusal", probs is not None, "no planner.declared_problems")
probs = probs or []
ck("a level the factor does not have is named, with the levels it does have",
   any("f1" in p and "'ctrl'" in p and "treated" in p and "untreated" in p for p in probs), probs)
ck("a factor the run is not about is named", any("dose" in p for p in probs), probs)
ck("a correct declaration is not refused",
   hasattr(PL, "declared_problems") and PL.declared_problems(facts(CTRL)) == [])


print("\n3. the host hands a plugin the order and a frame whose base is the control")
from scprofile.plugin import Context                                          # noqa: E402
import pandas as pd                                                           # noqa: E402
with tempfile.TemporaryDirectory() as td:
    ctx = Context(None, keys={}, out=Path(td), cores=1, params={"contrast": con},
                  log=lambda *a, **k: None)
    ck("ctx.levels exists", hasattr(ctx, "levels") and hasattr(ctx, "model_frame"))
    if hasattr(ctx, "levels"):
        ck("the order is the decision's, control first",
           ctx.levels("f2", ["high", "low"]) == ["low", "high"], ctx.levels("f2", ["high", "low"]))
        ck("over the levels a subset has", ctx.levels("f1", ["treated"]) == ["treated"])
        obs = pd.DataFrame({"sample": sorted(DESIGN),
                            "f1": [DESIGN[s]["f1"] for s in sorted(DESIGN)],
                            "f2": [DESIGN[s]["f2"] for s in sorted(DESIGN)]})
        fr, covs = ctx.model_frame(obs, ["f1", "f2"])
        ck("each term is a categorical whose first category is the control",
           list(fr["f1"].cat.categories) == ["untreated", "treated"]
           and list(fr["f2"].cat.categories) == ["low", "high"],
           (list(fr["f1"].cat.categories), list(fr["f2"].cat.categories)))
        ck("no covariate is added when none was modelled", covs == [])
        ck("and the run says which level each contrast is read against, once",
           sum("READ AGAINST ITS CONTROL" in c for c in ctx.caveats) == 1, ctx.caveats)
    bare = Context(None, keys={}, out=Path(td), cores=1, params={}, log=lambda *a, **k: None)
    if hasattr(bare, "levels"):
        ck("with no decision delivered the host's resolver decides, and says so",
           bare.levels("f1", ["treated", "untreated"]) == ["untreated", "treated"]
           and any("CHOSEN HERE" in c for c in bare.caveats), bare.caveats)


def _arrays():
    try:
        import anndata  # noqa: F401
        import numpy  # noqa: F401
        return True
    except Exception:                                                        # noqa: BLE001
        return False


def _write_object(td, design, planted):
    """Counts with a planted effect: genes 0-9 up in the treated level of f1 (both f2 arms)."""
    import anndata as ad
    import numpy as np
    rng = np.random.default_rng(7)
    n_per, n_genes = 24, 60
    samples = sorted(design)
    base = rng.uniform(4, 20, size=n_genes)
    rows, smp = [], []
    for s in samples:
        mult = np.ones(n_genes)
        for (fac, lvl), genes in planted.items():
            if design[s].get(fac) == lvl:
                mult[genes] *= 4.0
        rate = base * mult * rng.uniform(0.9, 1.1)
        rows.append(rng.poisson(rate, size=(n_per, n_genes)))
        smp += [s] * n_per
    X = np.vstack(rows).astype(np.float32)
    a = ad.AnnData(X=X)
    a.var_names = [f"g{j}" for j in range(n_genes)]
    a.obs_names = [f"c{i}" for i in range(a.n_obs)]
    a.obs["sample"] = pd.Categorical(smp)
    a.obs["cell_type"] = pd.Categorical(["popA"] * a.n_obs)
    a.layers["counts"] = X.copy()
    h5 = Path(td) / "obj.h5ad"
    a.write_h5ad(h5)
    cols = sorted({k for r in design.values() for k in r})
    with open(Path(td) / "design.csv", "w", encoding="utf-8") as fh:
        fh.write(",".join(["sample"] + cols) + "\n")
        for s in samples:
            fh.write(",".join([s] + [str(design[s][c]) for c in cols]) + "\n")
    return a, h5, Path(td) / "design.csv"


print("\n4. `scprofile plan` takes --control, prints the reference, and refuses a misspelt one")
if not _arrays():
    print("  SKIP the array stack is not importable here")
else:
    with tempfile.TemporaryDirectory() as td:
        _a, h5, dsn = _write_object(td, DESIGN, {})
        base = [sys.executable, "-m", "scprofile.cli", "plan", "--h5ad", str(h5),
                "--kernel", "de", "--design", str(dsn), "--prefix", str(Path(td) / "pfx"),
                "--label-key", "cell_type", "--sample-key", "sample",
                "--counts-layer", "counts", "--organism", "human", "--assay", "cell"]
        env = dict(os.environ, PYTHONPATH=str(ROOT))
        good = subprocess.run(base + ["--control", "f1=untreated", "--control", "f2=low"],
                              capture_output=True, text=True, env=env, cwd=str(ROOT), timeout=300)
        out = good.stdout + good.stderr
        ck("the plan accepts --control", "unrecognized arguments" not in out, out[-400:])
        ck("and prints each term's reference with its basis",
           "f1=untreated: declared" in out and "f2=low: declared" in out, out[-1500:])
        bad = subprocess.run(base + ["--control", "f1=ctrl"], capture_output=True, text=True,
                             env=env, cwd=str(ROOT), timeout=300)
        out = bad.stdout + bad.stderr
        ck("a control the design does not have is refused, naming it",
           bad.returncode != 0 and "'ctrl'" in out and "REFUSED" in out, out[-800:])


print("\n5. DE, run here on a 2x2 whose controls both sort last")
try:
    import pydeseq2  # noqa: F401
    _have_deseq = _arrays()
except Exception:                                                            # noqa: BLE001
    _have_deseq = False
if not _have_deseq:
    print("  SKIP pydeseq2 is not importable in this interpreter (it lives in the plugin's "
          "environment); the part above holds the host")
else:
    import matplotlib
    matplotlib.use("Agg")
    from scprofile import declare
    from scprofile.kernels import discover
    with tempfile.TemporaryDirectory() as td:
        adata, h5, dsn = _write_object(td, DESIGN, {("f1", "treated"): list(range(10))})
        k = discover()["de"]
        fx = facts(CTRL)
        params = PL.decisions_for(k, fx)
        spec = importlib.util.spec_from_file_location("de_kernel_under_test",
                                                      ROOT / "kernels" / "de.py")
        de = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(de)
        cfg = declare.resolve_config(de.PLUGIN, params, "de")
        log = []
        ctx = Context(adata, keys={"counts": "counts", "label": "cell_type", "sample": "sample"},
                      out=Path(td) / "out", cores=1, params=params, design=str(dsn),
                      config=cfg, log=log.append)
        de.run(ctx)
        t = pd.read_csv(Path(td) / "out" / "tables" / "de_by_population.csv")
        got = dict(t.groupby("term")["contrast"].first())
        ck("the f1 contrast is the treated level against its control",
           got.get("f1") == "treated vs untreated", got)
        ck("the f2 contrast is the other level against its control",
           got.get("f2") == "high vs low", got)
        ck("the interaction is named on the treated levels - the control is the base",
           got.get("f1:f2") == "f1[T.treated]:f2[T.high]", got)
        up = t[(t.term == "f1") & t.gene.isin([f"g{j}" for j in range(10)])]
        ck("the genes planted UP in the treated level come back positive",
           len(up) == 10 and (up.log2FoldChange > 0).all(),
           up[["gene", "log2FoldChange"]].to_string())
        ck("no caveat says the interaction was not contrasted",
           not any("IS NOT TESTED HERE" in c or "is not contrasted" in c for c in ctx.caveats),
           [c[:120] for c in ctx.caveats if "INTERACTION" in c])
        ck("the run says which level each contrast is read against",
           any("READ AGAINST ITS CONTROL" in c for c in ctx.caveats))


print("\n6. a subset with no sample at the control is not contrasted against another level "
      "(GAP-C48)")
# FOUND BY W013's VERIFIER: with three levels, a population lacking the declared control got its
# own levels only, so `levels[-1] vs levels[0]` read `mid vs alpha` - under the host's caveat that
# every contrast is read against the control. The host's frame now keeps the control as an empty
# level there, and the population's replication check refuses the contrast, by name.
if not _have_deseq:
    print("  SKIP pydeseq2 is not importable in this interpreter")
else:
    import anndata as ad
    import numpy as np
    from scprofile import declare
    from scprofile.kernels import discover
    D3 = {f"T{lv}{j}": {"f1": lv} for lv in ("alpha", "mid", "ctl") for j in (1, 2)}
    with tempfile.TemporaryDirectory() as td:
        rng = np.random.default_rng(5)
        rows, smp, pop = [], [], []
        for s_, r_ in sorted(D3.items()):
            for p_ in ("popA", "popB"):
                if p_ == "popB" and r_["f1"] == "ctl":
                    continue                       # popB has no sample at the control
                rows.append(rng.poisson(rng.uniform(5, 20, 40), size=(20, 40)))
                smp += [s_] * 20
                pop += [p_] * 20
        X = np.vstack(rows).astype(np.float32)
        A3 = ad.AnnData(X=X)
        A3.var_names = [f"g{j}" for j in range(40)]
        A3.obs_names = [f"c{i}" for i in range(A3.n_obs)]
        A3.obs["sample"] = pd.Categorical(smp)
        A3.obs["cell_type"] = pd.Categorical(pop)
        A3.layers["counts"] = X.copy()
        dsn3 = Path(td) / "design.csv"
        dsn3.write_text("sample,f1\n" + "".join(f"{k_},{v_['f1']}\n" for k_, v_ in
                                                 sorted(D3.items())), encoding="utf-8")
        fx3 = PL.design_facts(D3, ["f1"], "sample", sorted(D3), controls={"f1": "ctl"})
        k3 = discover()["de"]
        params3 = PL.decisions_for(k3, fx3)
        spec3 = importlib.util.spec_from_file_location("de_kernel_c48", ROOT / "kernels" / "de.py")
        de3 = importlib.util.module_from_spec(spec3)
        spec3.loader.exec_module(de3)
        ctx3 = Context(A3, keys={"counts": "counts", "label": "cell_type", "sample": "sample"},
                       out=Path(td) / "out", cores=1, params=params3, design=str(dsn3),
                       config=declare.resolve_config(de3.PLUGIN, params3, "de"),
                       log=lambda *a, **k: None)
        de3.run(ctx3)
        t3 = pd.read_csv(Path(td) / "out" / "tables" / "de_by_population.csv")
        got3 = sorted(set(map(tuple, t3[["population", "contrast"]].drop_duplicates().values)))
        ck("the population with the control is read against it", got3 == [("popA", "mid vs ctl")],
           got3)
        ck("the one without it is not contrasted at all - no `mid vs alpha`",
           "popB" not in set(t3.population), got3)
        ck("and is named as not tested, with the host's reason",
           any("Not tested" in c and "popB" in c for c in ctx3.caveats)
           and any("HAS NO SAMPLE IN A SUBSET" in c for c in ctx3.caveats),
           [c[:110] for c in ctx3.caveats])

print()
if FAILS:
    print(f"{len(FAILS)} FAILED")
    raise SystemExit(1)
print("every contrast is read against the declared control")
