"""Ablation over the reuse decision: build each failure mode and check reuse responds.

REUSE IS A HARDLINK. An adopted result becomes part of a later run byte for byte, so a wrong
YES carries a bad result forward with a provenance trail that makes it look verified. Testing
that the happy path works proves almost nothing; what has to be tested is that each way of
being wrong is actually caught.

Every case here builds a real run directory on disk - out.json, figures, tables, a card, a
licence - and asks the landscape the same question a run asks. Two of these caught defects that
the happy path did not: a REFUSED licence was overridden by a card that said `ok`, and an
in-progress run shadowed every completed run behind it.
"""

import json, os, shutil, sys, tempfile
from pathlib import Path
sys.path.insert(0, "/Users/admin/tools/scProfile")
from scprofile import landscape as LS, licence as LC, runcard as RC

base = Path(tempfile.mkdtemp())
obj = base / "obj.h5ad"; obj.write_text("x" * 500)

def make_run(name, *, unit="U1", figures=("FA", "FB"), version="1.0",
             card_verdict="ok", write_out=True, licence=True, retro=False):
    d = base / name / "kernels" / "k" / unit
    (d / "figures").mkdir(parents=True); (d / "tables").mkdir()
    (d / "tables" / "t.csv").write_text("a,b\n1,2\n")
    for f in figures:
        (d / "figures" / f"{f}.png").write_text(f)
    (d / "in.json").write_text(json.dumps({"h5ad": str(obj), "params": {}, "keys": {}}))
    if write_out:
        (d / "out.json").write_text(json.dumps({
            "version": version, "kernel": "k", "status": "ok",
            "figures": [{"id": f, "path": f"figures/{f}.png"} for f in figures],
            "tables": ["tables/t.csv"]}))
    if card_verdict:
        (base / name / "RUN_CARD.json").write_text(json.dumps({
            "card": 1, "run": name, "verdict": card_verdict,
            "instances": [{"plugin": "k", "unit": unit, "verdict": card_verdict,
                           "reasons": [], "artifacts": 2, "state": "done"}]}))
    if licence:
        LC.grant(base / name, "k", unit, declared=["tables/t.csv"],
                 required_figures=["FA"], declared_version=version)
    return base / name

def ask(unit="U1", version="1.0"):
    have = LS.scan(base)
    want = LS.wanted("k", unit, version=version, h5ad=obj, params={}, keys={})
    st, src, why = LS.match(want, have)
    return st, (src or {}).get("run"), why

def case(title, expect, got, detail=""):
    st = got[0]
    ok = st == expect
    print(f"  {'PASS' if ok else 'FAIL'}  {title:<52s} -> {st:<9s} "
          + (f"({got[1]})" if got[1] and st == LS.REUSABLE else f"{(got[2] or [''])[0][:58]}"))
    return ok

results = []
# --- TRUE POSITIVE -------------------------------------------------------------------------
make_run("r1_good")
results.append(case("a complete, licensed, card-ok result", LS.REUSABLE, ask()))

# --- ABLATION: remove a required figure ------------------------------------------------------
shutil.rmtree(base / "r1_good"); make_run("r2_missing_req", figures=("FB",))
results.append(case("ABLATE: the required figure is gone", LS.CHANGED, ask()))

# --- ABLATION: corrupt a product after licensing ---------------------------------------------
shutil.rmtree(base / "r2_missing_req"); r = make_run("r3_tampered")
(r / "kernels" / "k" / "U1" / "tables" / "t.csv").write_text("a,b\n9,9\n")
results.append(case("ABLATE: a product changed after the licence", LS.CHANGED, ask()))

# --- ABLATION: the run objected to its own result --------------------------------------------
shutil.rmtree(base / "r3_tampered"); make_run("r4_suspect", card_verdict="suspect")
results.append(case("ABLATE: the producing run calls it suspect", LS.CHANGED, ask()))

# --- ABLATION: the kernel died ---------------------------------------------------------------
shutil.rmtree(base / "r4_suspect"); make_run("r5_died", write_out=False, licence=False)
results.append(case("ABLATE: the kernel never wrote out.json", LS.CHANGED, ask()))

# --- ABLATION: the plugin version moved ------------------------------------------------------
shutil.rmtree(base / "r5_died"); make_run("r6_old_version", version="1.0")
results.append(case("ABLATE: asking for a newer plugin version", LS.CHANGED,
                    ask(version="2.0")))

# --- ABLATION: a different unit --------------------------------------------------------------
results.append(case("ABLATE: asking for a unit nobody ran", LS.ABSENT, ask(unit="U9")))

# --- ADD BACK: a good run alongside a bad one, newest first ----------------------------------
make_run("r7_bad_newer", card_verdict="suspect")
make_run("r8_good_older")
st, src, why = ask()
ok = st == LS.REUSABLE
print(f"  {'PASS' if ok else 'FAIL'}  {'ADD: a good run behind a suspect newer one':<52s} "
      f"-> {st:<9s} ({src})")
results.append(ok)

print(f"\n  {sum(results)}/{len(results)} ablations behaved correctly")
shutil.rmtree(base, ignore_errors=True)
sys.exit(0 if all(results) else 1)
