"""What the fixture run needs from the tool, found by running the fixture tiers on the
workstation before any job (harness ADR-0026, the open items).

TWO THINGS THE FIRST LOCAL RUN SAID. (1) `run` on a plugin whose environment is not built
launched twenty instances that each failed "no environment at ..." where `plan` refuses at its
door with "are not ready in this installation" - the fixture tier accepts the phrase and not the
crash, and a workstation ladder would have gone red on every shape for a reason that is the
installation's. `run` refuses at its door now, in the plan's words, before any instance. (2) The
fixture's design table carries batch, subject and a covariate beside the condition - hazards for
tools that model designs - and `run` read every column as a factor: nine marginal pools and
five arms over a numeric age where the study has one factor. `--factor NAME` names the factors
a run is about; the table's other columns stay for the panels that state confounds.

Run: python tests/test_a_run_on_the_fixture_is_the_run_the_plan_planned.py
"""
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

FAIL = []


def ck(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'} {name}" + (f" — {detail}" if not cond else ""))
    if not cond:
        FAIL.append(name)


print("the factors a run is about, when the table carries more columns than factors")
from scprofile import inputs as I                                               # noqa: E402

with tempfile.TemporaryDirectory() as td:
    p = Path(td) / "design.csv"
    p.write_text("sample,condition,batch,subject,age_weeks\n"
                 "S1,ctrl,chipA,D1,51.0\nS2,treated,chipB,D2,60.0\n")
    tab, key, factors = I.read_design(p)
    ck("every column is a factor when none is named",
       factors == ["condition", "batch", "subject", "age_weeks"], str(factors))
    tab, key, factors = I.read_design(p, factors=["condition"])
    ck("the named factor is the only factor", factors == ["condition"], str(factors))
    # THE ROWS TOO (found by the first job's fixture run): the unit resolver reads the table's
    # columns, not the factors list, so a table that kept batch, subject and age beside the
    # named factor still resolved nine marginal pools and five arms - twenty units for nine.
    # What a run is about is the table it is given; the panels that state confounds read the
    # design file itself, in the plugin's process, and see every column there.
    ck("the row carries the named factor only",
       tab["S1"] == {"condition": "ctrl"}, str(tab["S1"]))
    from scprofile import units as U
    plan, _why = U.resolve(tab, sample_key=key, samples=sorted(tab))
    ck("so the units resolve over that factor alone",
       all(set(p_.get("factors") or [p_.get("factor")] or []) <= {"condition", None}
           for p_ in plan) and not any("age" in str(p_) or "D1" in str(p_) for p_ in plan),
       str(plan)[:300])
    try:
        I.read_design(p, factors=["arm"])
        ck("a factor the table lacks is refused by name", False, "no refusal")
    except I.Refuse as e:
        ck("a factor the table lacks is refused by name", "arm" in str(e) and "condition" in str(e), str(e))
    tab, key, factors, src = I.design_or_derive(p, factors=["condition"])
    ck("design_or_derive passes it through", factors == ["condition"] and src == "table", str(factors))

print("\nthe table's sample column is the run's --sample-key when the table has it")
# SHAPE B PASSED IN TWO SECONDS (found by the first job's fixture run): the table's sample
# column is `library_id`, the guess list did not know it, `plan` reported the design NOT
# AVAILABLE and pointed at a `--design-sample-col` that does not exist, and the tier accepted
# the refusal that followed. The run is TOLD the sample column (`--sample-key`); a table that
# has that column is keyed on it, and one that has neither it nor a name the list knows is
# refused naming --sample-key.
with tempfile.TemporaryDirectory() as td:
    p = Path(td) / "design.csv"
    p.write_text("library_id,arm,chip\nS1,ctrl,chipA\nS2,treated,chipB\n")
    tab, key, factors = I.read_design(p, sample_col="library_id")
    ck("keyed on the column the run names", key == "library_id" and factors == ["arm", "chip"], f"{key} {factors}")
    tab, key, factors, src_ = I.design_or_derive(p, sample_key="library_id")
    ck("design_or_derive passes the run's sample key as the table's when the table has it",
       key == "library_id" and src_ == "table", f"{key} {src_}")
    p.write_text("sample,arm\nS1,ctrl\nS2,treated\n")
    tab, key, factors, src_ = I.design_or_derive(p, sample_key="library_id")
    ck("and falls back to the names the list knows when the table lacks it", key == "sample", key)
    p.write_text("mouse,arm\nS1,ctrl\nS2,treated\n")
    try:
        I.design_or_derive(p, sample_key="library_id")
        ck("neither: refused naming --sample-key", False, "no refusal")
    except I.Refuse as e:
        ck("neither: refused naming --sample-key", "--sample-key" in str(e) and "design-sample-col" not in str(e), str(e))

psrc = (ROOT / "scprofile" / "plugin.py").read_text(encoding="utf-8")
ck("the plugin-side reading is keyed the same way",
   'read_design(\n                        self.design, sample_col=self.keys.get("sample"))' in psrc)

src = (ROOT / "scprofile" / "cli.py").read_text(encoding="utf-8")
ck("`run` and `plan` take --factor", src.count('add_argument("--factor"') >= 2, str(src.count('add_argument("--factor"')))
ck("and pass it to the design", src.count("factors=getattr(a, \"factor\"") >= 4,
   str(src.count("factors=getattr(a, \"factor\"")))

print("\n`run` refuses at its door, in the plan's words, a plugin whose environment is not built")
try:
    import anndata  # noqa: F401
    import numpy as np
except Exception:                                                              # noqa: BLE001
    print("  skipped: anndata is not importable here (this check runs where the arrays are)")
    anndata = None
if anndata is not None:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        import anndata as ad
        import pandas as pd
        n = 60
        A = ad.AnnData(X=np.random.default_rng(0).poisson(1.0, size=(n, 30)).astype("float32"))
        A.obs["cell_type"] = pd.Categorical(["a", "b", "c"] * (n // 3))
        A.obs["sample"] = pd.Categorical(["S1", "S2"] * (n // 2))
        A.layers["counts"] = A.X.copy()
        A.layers["lognorm"] = np.log1p(A.X)
        A.obsm["X_pca"] = np.random.default_rng(1).normal(size=(n, 5)).astype("float32")
        A.var_names = [f"G{i}" for i in range(30)]
        A.write_h5ad(d / "x.h5ad")
        (d / "prefix").mkdir()
        p = subprocess.run([sys.executable, "-m", "scprofile.cli", "run", "--h5ad", str(d / "x.h5ad"),
                            "--out", str(d / "run"), "--kernel", "cellchat", "--prefix", str(d / "prefix"),
                            "--label-key", "cell_type", "--sample-key", "sample", "--counts-layer", "counts",
                            "--lognorm-layer", "lognorm", "--embedding", "X_pca", "--organism", "human"],
                           cwd=str(ROOT), capture_output=True, text=True)
        out = p.stdout + p.stderr
        ck("non-zero, in the plan's words", p.returncode != 0 and "not ready in this installation" in out,
           out[-600:])
        ck("and no instance was launched", "=== wave" not in out and not (d / "run" / "kernels" / "cellchat" / "S1").exists(),
           out[-400:])

if FAIL:
    print(f"\n{len(FAIL)} FAILED: " + ", ".join(FAIL))
    sys.exit(1)
print("\na run on the fixture is the run the plan planned")
