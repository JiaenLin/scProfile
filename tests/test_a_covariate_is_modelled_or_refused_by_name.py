"""A covariate is MODELLED or REFUSED BY NAME - never dropped, never read as a factor (GAP-040).

THE DEFECT. The host had no word for a covariate. A design table's covariate column was either
removed from the run's rows by `--factor` without a sentence, or - without `--factor` - read as a
factor, so a numeric age became as many arms as it had values. No plugin could be handed one, and
DE fitted its terms alone while the user's table carried the column they meant to adjust for. The
design's other columns were absent from the model and named nowhere. Found again by the blind
record of `de` (docs/MIGRATIONS.md 1): the fixture's covariate was dropped and no caveat said so.

WHAT THIS HOLDS, each part failing on f5175ea:
  1. `--covariate` is resolved against the contrast: modelled (numeric or categorical, with its
     per-sample values) or refused with the reason - not a column, a term, one value, the sample
     under another name, collinear with the terms; design columns that are neither a term nor a
     declared covariate are named as not in the model;
  2. a plugin that cannot receive covariates is not handed them, and is SAID not to model them;
  3. a numeric covariate is one column of a design matrix, not one dummy per value;
  4. the host adds a modelled covariate to the plugin's frame, typed, and says what it did;
  5. `scprofile plan --covariate` prints the decision and refuses a name that is not a column;
  6. DE, run here: the covariate is in the fitted formula and named as modelled; a refused one
     is named with its reason and is not in the formula.
"""
import importlib.util
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scprofile import inputs, planner as PL                                  # noqa: E402

FAILS = []


def ck(name, ok, detail=""):
    print(("  ok   " if ok else "  FAIL ") + name + ("" if ok else f"\n         {detail}"))
    if not ok:
        FAILS.append(name)


class K:
    name, needs_design = "k", True
    injects_required, injects_optional = ["design"], ["contrast", "covariates"]


class NoCov(K):
    name, injects_optional = "nocov", ["contrast"]


# One factor, four per arm. `age` varies within both arms; `site` splits the samples exactly as
# f1 does; `run_id` differs for every sample; `const` takes one value; `batch` is a design factor
# with a singleton arm, so it is not a term of any contrast.
SAMPLES = [f"S{i}" for i in range(8)]
F1 = ["untreated"] * 4 + ["treated"] * 4
DESIGN = {s: {"f1": f, "batch": ("b1" if i < 7 else "b2")} for i, (s, f) in
          enumerate(zip(SAMPLES, F1))}
COV = {"age": {s: str(40 + 3 * i + (i % 3)) for i, s in enumerate(SAMPLES)},
       "site": {s: ("north" if f == "untreated" else "south") for s, f in zip(SAMPLES, F1)},
       "run_id": {s: f"r{i}" for i, s in enumerate(SAMPLES)},
       "const": {s: "same" for s in SAMPLES},
       "f1": {s: f for s, f in zip(SAMPLES, F1)}}


def decide(names, kernel=K):
    try:
        fx = PL.design_facts(DESIGN, ["f1", "batch"], "sample", SAMPLES,
                             controls={"f1": "untreated"},
                             covariates={n: COV.get(n, {}) for n in names})
    except TypeError as e:                    # f5175ea: no covariates
        return None, repr(e)
    return fx, PL.decisions_for(kernel(), fx)


print("1. each declared covariate is modelled or refused, with the reason")
fx, dec = decide(["age", "site", "run_id", "const", "f1"])
ck("design_facts takes the declared covariates", fx is not None, dec)
cov = (dec or {}).get("covariates") if isinstance(dec, dict) else None
ck("the decision carries a covariates block", isinstance(cov, dict), dec)
cov = cov or {}
mod = {c["name"]: c for c in cov.get("modelled") or []}
ref = {c["name"]: c["why"] for c in cov.get("refused") or []}
ck("a numeric covariate that varies within the arms is MODELLED, as numeric",
   mod.get("age", {}).get("kind") == "numeric", cov)
ck("with its per-sample values, so the plugin needs no second reading of the table",
   mod.get("age", {}).get("values", {}).get("S3") == COV["age"]["S3"], mod.get("age"))
ck("a covariate that splits the samples as the term does is refused as collinear",
   "collinear" in ref.get("site", ""), ref)
ck("one with a different value for every sample is refused as the sample itself",
   "sample under another name" in ref.get("run_id", ""), ref)
ck("one with a single value is refused", "one value" in ref.get("const", ""), ref)
ck("the contrast's own term is refused as a covariate", "a term of the contrast" in
   ref.get("f1", ""), ref)
ck("a design column that is neither a term nor declared is named as not in the model",
   [c["name"] for c in cov.get("not_modelled") or []] == ["batch"], cov.get("not_modelled"))
probs = PL.declared_problems(PL.design_facts(DESIGN, ["f1", "batch"], "sample", SAMPLES,
                                             covariates={"nope": {}})) \
    if hasattr(PL, "declared_problems") and fx is not None else ["(no refusal)"]
ck("a covariate that is not a column is refused before anything runs",
   any("nope" in p and "not a column" in p for p in probs), probs)


print("\n2. a plugin that cannot receive covariates is not handed them, and is said not to model them")
fx2, dec2 = decide(["age"], NoCov)
ck("not handed", isinstance(dec2, dict) and "covariates" not in dec2, dec2)
said = PL.covariates_not_taken(NoCov(), fx2) if hasattr(PL, "covariates_not_taken") and fx2 \
    else ""
ck("and named as NOT MODELLED, with what it would take", "NOT MODELLED" in said
   and "age" in said and "covariates" in said, said)
ck("a plugin that can receive them is not named", fx2 is not None
   and hasattr(PL, "covariates_not_taken") and PL.covariates_not_taken(K(), fx2) == "")


def _arrays():
    try:
        import anndata  # noqa: F401
        import numpy  # noqa: F401
        import pandas  # noqa: F401
        return True
    except Exception:                                                        # noqa: BLE001
        return False


print("\n3. a numeric covariate is one column of the design, not one dummy per value")
if not _arrays():
    print("  SKIP the array stack is not importable here")
else:
    import pandas as pd
    frame = pd.DataFrame({"f1": F1, "age": [float(COV["age"][s]) for s in SAMPLES]})
    ck("f1 + age is estimable on eight samples", inputs.estimable(frame, ["f1", "age"]),
       "dummy-coding eight ages asks for seven coefficients")
    frame["flat"] = 5.0
    ck("a covariate with one value is not", not inputs.estimable(frame, ["f1", "flat"]))


print("\n4. the host adds a modelled covariate to the plugin's frame, typed, and says so")
if _arrays() and isinstance(dec, dict):
    import pandas as pd
    from scprofile.plugin import Context
    with tempfile.TemporaryDirectory() as td:
        ctx = Context(None, keys={}, out=Path(td), cores=1, params=dec, log=lambda *a, **k: None)
        if not hasattr(ctx, "model_frame"):
            ck("ctx.model_frame exists", False, "no Context.model_frame")
        else:
            obs = pd.DataFrame({"sample": SAMPLES, "f1": F1})
            fr, added = ctx.model_frame(obs, ["f1"])
            ck("the modelled covariate is added, and only it", added == ["age"], added)
            ck("as a float", str(fr["age"].dtype).startswith("float")
               and float(fr["age"].iloc[3]) == float(COV["age"]["S3"]), fr.dtypes.to_dict())
            text = " ".join(ctx.caveats)
            ck("the caveats name it as modelled", "COVARIATES IN THE MODEL: age (numeric)" in text,
               text[:400])
            ck("and each refused one with its reason", "COVARIATE REFUSED: site" in text
               and "collinear" in text, text[:600])
            ck("and the design columns not in the model", "NOT IN THE MODEL: batch" in text,
               text[:600])


def _write_object(td, f1, age, site):
    import anndata as ad
    import numpy as np
    import pandas as pd
    rng = np.random.default_rng(11)
    n_per, n_genes = 24, 50
    base = rng.uniform(4, 20, size=n_genes)
    rows, smp = [], []
    for s, f in zip(SAMPLES, f1):
        mult = np.ones(n_genes)
        if f == "treated":
            mult[:8] *= 4.0
        rows.append(rng.poisson(base * mult * rng.uniform(0.9, 1.1), size=(n_per, n_genes)))
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
    dsn = Path(td) / "design.csv"
    with open(dsn, "w", encoding="utf-8") as fh:
        fh.write("sample,f1,age,site\n")
        for s, f in zip(SAMPLES, f1):
            fh.write(f"{s},{f},{age[s]},{site[s]}\n")
    return a, h5, dsn


print("\n5. `scprofile plan --covariate` prints the decision and refuses a name that is no column")
if not _arrays():
    print("  SKIP the array stack is not importable here")
else:
    with tempfile.TemporaryDirectory() as td:
        _a, h5, dsn = _write_object(td, F1, COV["age"], COV["site"])
        base = [sys.executable, "-m", "scprofile.cli", "plan", "--h5ad", str(h5),
                "--kernel", "de", "--design", str(dsn), "--prefix", str(Path(td) / "pfx"),
                "--label-key", "cell_type", "--sample-key", "sample", "--factor", "f1",
                "--counts-layer", "counts", "--organism", "human", "--assay", "cell"]
        env = dict(os.environ, PYTHONPATH=str(ROOT))
        r = subprocess.run(base + ["--covariate", "age", "--covariate", "site"],
                           capture_output=True, text=True, env=env, cwd=str(ROOT), timeout=300)
        out = r.stdout + r.stderr
        ck("the plan accepts --covariate", "unrecognized arguments" not in out, out[-300:])
        ck("and prints each covariate modelled or refused, by name",
           "MODELLED age (numeric)" in out and "REFUSED site" in out, out[-1500:])
        r = subprocess.run(base + ["--covariate", "nope"], capture_output=True, text=True,
                           env=env, cwd=str(ROOT), timeout=300)
        out = r.stdout + r.stderr
        ck("a covariate that is not a column is refused, naming it",
           r.returncode != 0 and "REFUSED" in out and "nope" in out, out[-600:])


print("\n6. DE, run here: the covariate is in the fitted formula, the refused one is named")
try:
    import pydeseq2  # noqa: F401
    _have = _arrays() and isinstance(dec, dict)
except Exception:                                                            # noqa: BLE001
    _have = False
if not _have:
    print("  SKIP pydeseq2 is not importable in this interpreter, or part 1 failed")
else:
    import matplotlib
    import pandas as pd
    matplotlib.use("Agg")
    from scprofile import declare
    from scprofile.kernels import discover
    from scprofile.plugin import Context
    with tempfile.TemporaryDirectory() as td:
        adata, h5, dsn = _write_object(td, F1, COV["age"], COV["site"])
        k = discover()["de"]
        fx = PL.design_facts({s: {"f1": f} for s, f in zip(SAMPLES, F1)}, ["f1"], "sample",
                             SAMPLES, controls={"f1": "untreated"},
                             covariates={"age": COV["age"], "site": COV["site"]})
        params = PL.decisions_for(k, fx)
        ck("DE declares it can receive covariates", "covariates" in params, sorted(params))
        spec = importlib.util.spec_from_file_location("de_kernel_cov", ROOT / "kernels" / "de.py")
        de = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(de)
        cfg = declare.resolve_config(de.PLUGIN, params, "de")
        ctx = Context(adata, keys={"counts": "counts", "label": "cell_type", "sample": "sample"},
                      out=Path(td) / "out", cores=1, params=params, design=str(dsn), config=cfg,
                      log=lambda *a, **k: None)
        de.run(ctx)
        text = " ".join(ctx.caveats)
        ck("the formula fitted carries the covariate", "`~ f1 + age`" in text,
           [c[:200] for c in ctx.caveats if "FITTED PER POPULATION" in c])
        ck("the covariate is named as modelled", "COVARIATES IN THE MODEL: age" in text)
        ck("the refused one is named with its reason, and is not in the formula",
           "COVARIATE REFUSED: site" in text and "site`" not in text, text[:800])
        t = pd.read_csv(Path(td) / "out" / "tables" / "de_by_population.csv")
        ck("only the design term is contrasted - a covariate is adjusted for, never tested",
           sorted(set(t.term)) == ["f1"] and set(t.contrast) == {"treated vs untreated"},
           sorted(set(zip(t.term, t.contrast))))


print("\n7. under --factor, every other column of the table is still NAMED as not in the model")
# FOUND BY W013's VERIFIER: `--factor` narrows the run's factors, and the columns it left out
# were neither modelled, refused nor named - the plan printed "none declared, and no other column
# of the design" over a table that had them.
try:
    fx7 = PL.design_facts({s: {"f1": f} for s, f in zip(SAMPLES, F1)}, ["f1"], "sample",
                          SAMPLES, controls={"f1": "untreated"},
                          covariates={"age": COV["age"]}, columns=["f1", "age", "site", "batch"])
    dec7 = PL.decisions_for(K(), fx7)
except TypeError as e:                       # 0f4ff9e: design_facts records no columns
    fx7, dec7 = None, {}
    ck("design_facts records the design table's columns", False, repr(e))
nm = [c["name"] for c in ((dec7 or {}).get("covariates") or {}).get("not_modelled") or []]
ck("every column that is neither a term nor a declared covariate is named", nm == ["batch", "site"],
   nm)
ck("and the sentence claiming there is no other column is gone",
   PL.describe_covariates({}) == "no covariate declared", PL.describe_covariates({}))
if _arrays():
    with tempfile.TemporaryDirectory() as td:
        _a, h5, dsn = _write_object(td, F1, COV["age"], COV["site"])
        base = [sys.executable, "-m", "scprofile.cli", "plan", "--h5ad", str(h5),
                "--kernel", "de", "--design", str(dsn), "--prefix", str(Path(td) / "pfx"),
                "--label-key", "cell_type", "--sample-key", "sample", "--factor", "f1",
                "--counts-layer", "counts", "--organism", "human", "--assay", "cell"]
        env = dict(os.environ, PYTHONPATH=str(ROOT))
        r = subprocess.run(base, capture_output=True, text=True, env=env, cwd=str(ROOT),
                           timeout=300)
        out = r.stdout + r.stderr
        ck("the plan names the columns --factor left out", "not in the model: age, site" in out,
           out[-1200:])
        ck("and never says there is no other column", "no other column of the design" not in out)
        r = subprocess.run(base + ["--covariate", "age"], capture_output=True, text=True,
                           env=env, cwd=str(ROOT), timeout=300)
        out = r.stdout + r.stderr
        ck("with one declared, the other is still named", "MODELLED age (numeric)" in out
           and "not in the model: site" in out, out[-1200:])

print()
if FAILS:
    print(f"{len(FAILS)} FAILED")
    raise SystemExit(1)
print("a covariate is modelled or refused by name")
