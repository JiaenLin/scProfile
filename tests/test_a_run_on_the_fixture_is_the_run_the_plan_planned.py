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

print("\n'not ready in this installation' is the environment's sentence, and bundled references need no directory")
# THE SECOND JOB'S SHAPE B (PBS 712313): `plan`, given no --references, marked cellchat's
# reference data UNRESOLVED - CellChatDB ships inside the package - and printed 'PREPARATION:
# 1 plugin(s) are not ready in this installation' over a verdict that had refused for the
# DATA (no sample key was passed to the fixture's plan); the tier accepted the phrase and the
# cohort ran over an unchecked shape. Two rules: a plugin whose references for the organism
# are all bundled or fetched at run time is not 'unknown' for want of a directory; and the
# installation's sentence is printed for the installation's kinds alone.
from scprofile import refs as RF, planner as PL, kernels as K                   # noqa: E402

class _K:
    name = "demo"
    def __init__(self, tiers):
        self._tiers = tiers
    def references(self, organism=None):
        return {f"r{i}": ({"tier": t, "organism": organism or "human", "role": "x"} if t != "fetch"
                          else {"url": "https://x/y.bin", "sha256": "0" * 64, "size": 1,
                                "organism": organism or "human", "role": "x"})
                for i, t in enumerate(self._tiers)}

ck("bundled and runtime references need no directory", not RF.needs_directory(_K(["bundled", "runtime"]), "human"))
ck("a fetched file does", RF.needs_directory(_K(["bundled", "fetch"]), "human"))
ck("no references, no directory", not RF.needs_directory(_K([]), "human"))
src = (ROOT / "scprofile" / "cli.py").read_text(encoding="utf-8")
ck("plan reads it before calling references unknown", "refs.needs_directory(" in src)
_plan_say = [i for i in range(len(src)) if src.startswith("PREPARATION: {len(pend)} plugin(s) are not ready", i)]
ck("the installation's sentence is keyed on the installation's kinds",
   len(_plan_say) == 1 and "_env_kinds" in src[_plan_say[0] - 1500:_plan_say[0]], str(_plan_say))
ck("references not checked have their own sentence", "reference data was not checked" in src)

print("\na promise on an axis the design has no occurrence of is not a promise of that run")
# THE SECOND JOB'S SHAPE A (PBS 712313): cellchat ran on the fixture's one-factor design, drew
# the units and the one contrast, and `--promised` failed the tier on `compareInteractions` -
# a plate on the `interaction` axis, the cross of two factors, which a one-factor design
# never launches. The native accounting promised it whatever the design; the run's own
# directories say which axes occurred (units; `compare/<contrast>`; `compare/_across_arms`
# for the interaction), and a promise on an absent axis is waived and said.
import os
with tempfile.TemporaryDirectory() as td:
    d = Path(td)
    kdir = d / "kernels"
    kdir.mkdir()
    (kdir / "demo.py").write_text(
        'PLUGIN = {"name": "demo", "api": 1, "version": "0.1.0", "summary": "s",\n'
        '          "report": {"figures": [\n'
        '    {"id": "native_ring", "fn": "ringPlot", "drawn_by": "tool", "axis": "unit", "legend": "a"},\n'
        '    {"id": "nativecmp_pair", "fn": "pairPlot", "drawn_by": "tool", "axis": "contrast", "legend": "b"},\n'
        '    {"id": "nativecmp_cross", "fn": "crossPlot", "drawn_by": "tool", "axis": "interaction", "legend": "c"},\n'
        '  ]}}\n\ndef run(ctx):\n    return None\n')
    run = d / "run"
    (run / "kernels" / "demo" / "U1" / "figures").mkdir(parents=True)
    (run / "kernels" / "demo" / "U1" / "figures" / "native_ring.png").write_bytes(b"x")
    (run / "kernels" / "demo" / "compare" / "cond" / "figures").mkdir(parents=True)
    (run / "kernels" / "demo" / "compare" / "cond" / "figures" / "nativecmp_pair.png").write_bytes(b"x")
    env = dict(os.environ, PYTHONPATH=str(ROOT), SCPROFILE_KERNELS=str(kdir))
    p = subprocess.run([sys.executable, "-m", "scprofile.cli", "capacity", "--out", str(run), "--promised"],
                       cwd=str(ROOT), capture_output=True, text=True, env=env)
    out = p.stdout + p.stderr
    ck("a one-factor run keeps its promise: the interaction plate is waived, not owed",
       p.returncode == 0 and "crossPlot" in out and "interaction" in out and "NEVER DRAWN" not in out, out[-700:])
    (run / "kernels" / "demo" / "compare" / "_across_arms" / "figures").mkdir(parents=True)
    p = subprocess.run([sys.executable, "-m", "scprofile.cli", "capacity", "--out", str(run), "--promised"],
                       cwd=str(ROOT), capture_output=True, text=True, env=env)
    out = p.stdout + p.stderr
    ck("with the interaction phase present and the plate absent, the promise is owed",
       p.returncode != 0 and "crossPlot" in out and "NEVER DRAWN" in out, out[-700:])

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
