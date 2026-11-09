"""The maker asks a design-aware plugin for the design, and its fixture can tell the answers apart.

FOUND BY A BLIND TEST OF THE MAKER (docs/MIGRATIONS.md 1, `de` at f5175ea). The plugin chose a
contrast's reference by sort order and could not be handed a covariate, and the maker read every
build stage of it done over both: no stage asked a design-aware plugin how it orders a factor or
what it adjusts for. And the ladder's value axis - the fixture's shape b, whose control sorts
last, built to catch exactly that (harness ADR-0027) - was handed `--control <factor>=ctrl`, shape
a's literal, on both shapes: shape b has no such level, so a plugin that took the declared control
and one that sorted could not be told apart there, and the fixture's covariate column was dropped
by `--factor` without a word.

WHAT THIS HOLDS, each failing on f5175ea:
  1. the fixture command hands each shape ITS OWN control (`{control}`) and declares the fixture's
     covariate, in the plan and in the run;
  2. the kernel point declares a BUILD stage `design` whose command is the maker's check;
  3. the check names each site where a design-aware plugin builds a model or takes a contrast,
     owes until the plugin asks the host for its frame and its order and declares `covariates`,
     and has nothing to say to a plugin that is not design-aware;
  4. the shipped `de` answers it.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FAILS = []


def ck(name, ok, detail=""):
    print(("  ok   " if ok else "  FAIL ") + name + ("" if ok else f"\n         {detail}"))
    if not ok:
        FAILS.append(name)


print("1. the fixture hands each shape its own control, and its covariate")
# READ AS TEXT, as every suite here reads DEVPOINTS: the host depends on numpy and pandas only.
dev = (ROOT / "DEVPOINTS.yaml").read_text(encoding="utf-8")
fixture = dev[dev.index("\nfixture:"):dev.index("\nbaseline_dir:")]
code = "\n".join(l.split("#", 1)[0] for l in fixture.splitlines())
ck("plan and run are told the shape's control, not a literal",
   code.count('"--control", "{role_condition}={control}"') == 2, code[-900:])
ck("both declare the fixture's covariate",
   code.count('"--covariate", "{role_covariate}"') == 2, code[-900:])
ck("no fixture command names a level of either shape",
   "=ctrl" not in code and "=untreated" not in code)


print("\n2. the kernel point declares the design stage, a build stage with a command")
stages = dev[dev.index("      stages:"):]
names = [l.split("- name:", 1)[1].strip() for l in stages.splitlines() if "- name:" in l]
ck("a stage named design exists", "design" in names, names)
blk = stages[stages.index("- name: design"):] if "design" in names else ""
blk = blk[:blk.index("- name:", 5)] if "- name:" in blk[5:] else blk
ck("it is a build stage", "phase: build" in blk, blk[:200])
ck("its command is the maker's check",
   'command: ["{python}", "-m", "scprofile.cli", "design", "{name}"]' in blk, blk[:600])
ck("it says how to finish it", "model_frame" in blk and "ctx.levels" in blk)
ck("after the contract, before the judgement",
   "design" in names and names.index("contract") < names.index("design") < names.index("judgement"),
   names)


print("\n3. the check names the sites, and owes until the host's model is taken")
from scprofile import validate as V                                          # noqa: E402

FITS = '''
PLUGIN = {"inject": {"required": ["design"], "optional": ["contrast"%s]}}

def run(ctx):
    import somelib
    terms = ctx.params["contrast"]["terms"]
%s
    fit = somelib.Model(data=obs, design="~ " + " + ".join(terms))
    for term in terms:
%s
        res = fit.compare(contrast=[term, levels[-1], levels[0]])
'''
OWN = ('    obs = ctx.design_frame()', '        levels = sorted(obs[term].unique())')
HOST = ('    obs, covs = ctx.model_frame(ctx.design_frame(), terms)',
        '        levels = ctx.levels(term, obs[term])')


class Stub:
    def __init__(self, path, spec):
        self.path, self.spec, self.name = str(path), spec, Path(path).stem


if not hasattr(V, "design_sites"):
    ck("validate.design_sites exists", False, "no design_sites in scprofile/validate.py")
else:
    with tempfile.TemporaryDirectory() as td:
        own = Path(td) / "own.py"
        own.write_text(FITS % ("", OWN[0], OWN[1]), encoding="utf-8")
        d = V.design_sites(Stub(own, {"inject": {"required": ["design"],
                                                 "optional": ["contrast"]}}))
        ck("a plugin ordering its own levels is design-aware and owes", d["design_aware"]
           and d["owes"], d)
        ck("each site is named with its line",
           [(ln, nm) for ln, nm, _k in d["sites"]] == [(8, "Model"), (11, "compare")], d["sites"])
        ck("and what is owed: the frame, the order, the covariates",
           [m for m, _w in d["missing"]] == ["model_frame", "levels", "covariates"], d["missing"])
        host = Path(td) / "host.py"
        host.write_text(FITS % (', "covariates"', HOST[0], HOST[1]), encoding="utf-8")
        d = V.design_sites(Stub(host, {"inject": {"required": ["design"],
                                                  "optional": ["contrast", "covariates"]}}))
        ck("one that takes the host's frame and order and declares covariates owes nothing",
           d["design_aware"] and not d["owes"] and len(d["sites"]) == 2, d)
        plain = Path(td) / "plain.py"
        plain.write_text("PLUGIN = {}\n\ndef run(ctx):\n    f(formula='x')\n", encoding="utf-8")
        d = V.design_sites(Stub(plain, {"inject": {"required": ["counts"]}}))
        ck("one that is not design-aware has nothing to answer",
           not d["design_aware"] and not d["owes"] and not d["sites"], d)


print("\n4. the shipped de answers the worksheet")
r = subprocess.run([sys.executable, "-m", "scprofile.cli", "design", "de"], capture_output=True,
                   text=True, cwd=str(ROOT), timeout=120)
ck("scprofile design de exits 0", r.returncode == 0, (r.stdout + r.stderr)[-800:])

print()
if FAILS:
    print(f"{len(FAILS)} FAILED")
    raise SystemExit(1)
print("the maker demands the design, and the fixture can tell the answers apart")
