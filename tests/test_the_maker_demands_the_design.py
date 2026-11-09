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


print("\n5. every STATEMENT of what was contrasted or modelled is a site, answered through the "
      "worksheet and recorded (GAP-C47)")
# FOUND BY W013's VERIFIER: de's runtime caveat said an interaction was "not contrasted" beside
# the row contrasting it, and the sentence was changed with no verb and no worksheet naming the
# site. A plugin's sentence about the design is a claim about the host's decision.
STATED = '''
PLUGIN = {"version": "1.0.0", "inject": {"required": ["design"], "optional": ["contrast", "covariates"]}}

def run(ctx):
    import somelib
    terms = ctx.params["contrast"]["terms"]
    obs, covs = ctx.model_frame(ctx.design_frame(), terms)
    for term in terms:
        levels = ctx.levels(term, obs[term])
        res = somelib.compare(contrast=[term, levels[-1], levels[0]])
    ctx.caveat("the cells of every sample were summed before testing")
    if terms:
        ctx.caveat("THE INTERACTION IS IN THE MODEL AND IS NOT CONTRASTED here")
'''


class Stub2(Stub):
    pass


import json                                                                  # noqa: E402
with tempfile.TemporaryDirectory() as td0:
    f0 = Path(td0) / "stated.py"
    f0.write_text(STATED, encoding="utf-8")
    d0 = V.design_sites(Stub2(f0, {"inject": {"required": ["design"],
                                              "optional": ["contrast", "covariates"]}}))
    st0 = d0.get("statements") or []
    ck("the sentence about the model is named as a statement site, the other is not",
       [x["line"] for x in st0] == [13], [(x["line"], x.get("text")) for x in st0])
    ck("and it is owed until it is answered", d0["owes"]
       and [m for m, _w in d0["missing"]] == ["statement:13"], d0["missing"])
if not hasattr(V, "design_answer"):
    ck("validate.design_answer, design_confirm and design_replay exist", False,
       "no answer mechanism in scprofile/validate.py")
else:
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "stated.py"
        f.write_text(STATED, encoding="utf-8")
        k = Stub2(f, {"inject": {"required": ["design"], "optional": ["contrast", "covariates"]}})
        base = f.read_text(encoding="utf-8")
        ck("a confirmation needs a reason", V.design_confirm(k, 13, "", log=lambda *a: None) == 1)
        ck("confirmed true, by the digest of its syntax, it is answered",
           V.design_confirm(k, 13, "checked against the host", log=lambda *a: None) == 0
           and not V.design_sites(k)["owes"])
        rec = json.loads(V.design_record_path(k).read_text(encoding="utf-8"))
        ck("the confirmation is in the worksheet's own record", any(
            v.get("how") == "confirmed" and v.get("site") == "statement:13"
            for v in rec["statements"].values()), rec)
        f.write_text(base.replace("NOT CONTRASTED here", "not contrasted at all"), "utf-8")
        ck("a sentence changed after it was confirmed owes again", V.design_sites(k)["owes"])
        f.write_text(base, encoding="utf-8")
        V.design_record_path(k).unlink()
        outside = Path(td) / "outside.py"
        outside.write_text(base.replace('"version": "1.0.0", ', '"version": "1.0.0", "x": 1, '),
                           encoding="utf-8")
        lines = []
        ck("an answer changing a line no site names is refused, by line",
           V.design_answer(k, outside, "why", log=lines.append) == 1
           and f.read_text(encoding="utf-8") == base
           and any("line(s) 2" in x and "hand edit" in x for x in lines), lines)
        fixed = Path(td) / "fixed.py"
        fixed.write_text(base.replace(
            '        ctx.caveat("THE INTERACTION IS IN THE MODEL AND IS NOT CONTRASTED here")',
            '        # the interaction is contrasted, as its own row\n'
            '        ctx.caveat("THE INTERACTION IS IN THE MODEL AND IS CONTRASTED, as its own row")'),
            encoding="utf-8")
        ck("an answer at the statement is applied, and the version is the maker's to raise",
           V.design_answer(k, fixed, "it is contrasted", log=lambda *a: None) == 0
           and "IS CONTRASTED, as its own row" in f.read_text(encoding="utf-8")
           and '"version": "1.1.0"' in f.read_text(encoding="utf-8"))
        ck("and the statement it answered is answered", not V.design_sites(k)["owes"])
        rec = json.loads(V.design_record_path(k).read_text(encoding="utf-8"))
        ans = rec["answers"][0] if rec["answers"] else {}
        ck("the record carries the diff, the reason and the sites",
           ans.get("sites") == ["statement:13"] and ans.get("why") == "it is contrasted"
           and "+        # the interaction is contrasted" in ans.get("diff", ""), ans)
        copy = Path(td) / "copy.py"
        copy.write_text(base, encoding="utf-8")
        ck("replayed onto the file it was made against, the record rebuilds the plugin exactly",
           V.design_replay(k, copy, log=lambda *a: None) == 0
           and copy.read_text(encoding="utf-8") == f.read_text(encoding="utf-8"))
        copy.write_text(base + "\n", encoding="utf-8")
        ck("and refuses a file it was not made against",
           V.design_replay(k, copy, log=lambda *a: None) == 1)


print("\n6. the shipped de: every statement answered, and its record replays")
from scprofile.kernels import discover                                      # noqa: E402
_de = discover()["de"]
ck("the worksheet keeps its own record beside the plugin", hasattr(V, "design_record_path")
   and V.design_record_path(_de).is_file())
if hasattr(V, "design_record_path"):
    d = V.design_sites(_de)
    ck("the worksheet names de's statements, and every one is answered",
       len(d.get("statements") or []) >= 10
       and all(x.get("answered") for x in d["statements"]), [
           (x["line"], bool(x.get("answered"))) for x in d.get("statements") or []])
    rec = json.loads(V.design_record_path(_de).read_text(encoding="utf-8")) \
        if V.design_record_path(_de).is_file() else {"answers": []}
    ck("its record holds the answers that changed it, each with a reason and a diff",
       len(rec["answers"]) >= 2 and all(a.get("why") and a.get("diff") for a in rec["answers"]),
       len(rec["answers"]))
    ck("the last answer made the file that ships", bool(rec["answers"])
       and rec["answers"][-1]["after"] == V._sha(
           (ROOT / "kernels" / "de.py").read_text(encoding="utf-8")))


print("\n7. an answer cannot carry a hand edit: narrow fit sites, insertions strictly inside, "
      "the record re-checked on replay (W013 fix-up 2)")
# THE VERIFIER'S THREE PROBES, run against a copy of the shipped plugin. A fit site spanned its
# whole loop or function - 334 of run()'s 532 lines and all of selftest - so a doubled filter
# threshold and a zeroed selftest gate were recorded as a design answer; an insertion just after
# the loop was accepted naming no site; and the replay trusted any diff whose digests matched.
import shutil                                                                 # noqa: E402
if not hasattr(V, "design_answer"):
    ck("the answer mechanism exists", False, "no design_answer")
else:
    with tempfile.TemporaryDirectory() as td:
        de_copy = Path(td) / "de.py"
        shutil.copyfile(ROOT / "kernels" / "de.py", de_copy)
        kd = Stub(de_copy, _de.spec)
        shipped = de_copy.read_text(encoding="utf-8")

        def refused(name, edit):
            prop = Path(td) / f"{name}.py"
            prop.write_text(edit(shipped), encoding="utf-8")
            out = []
            rc = V.design_answer(kd, prop, "x", log=out.append)
            return rc == 1 and de_copy.read_text(encoding="utf-8") == shipped, out

        ok_, out = refused("threshold", lambda t: t.replace(
            'keep = sub.sum(axis=0) >= C["min_counts"]',
            'keep = sub.sum(axis=0) >= 2 * C["min_counts"]', 1))
        ck("a filter threshold three lines from a fit call is not a fit site: refused",
           ok_ and any("hand edit" in x for x in out), out)
        ok_, out = refused("gate", lambda t: t.replace("assert found >= 15, (",
                                                      "assert found >= 0, (", 1))
        ck("a selftest's gate is not a fit site: refused", ok_, out)
        anchor = ('        ctx.log(f"  {pop}: {int(m.sum())} pseudobulk samples, '
                  '{int(keep.sum()):,} genes tested")\n')
        ck("(the probe's anchor is in the shipped plugin)", anchor in shipped)
        ok_, out = refused("edge", lambda t: t.replace(anchor, anchor + "    out = out[:1]\n", 1))
        ck("an insertion just after a site's last line is refused", ok_, out)
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "stated.py"
        f.write_text(STATED, encoding="utf-8")
        k = Stub2(f, {"inject": {"required": ["design"], "optional": ["contrast", "covariates"]}})
        before = STATED
        after = STATED.replace('"version": "1.0.0", ', '"version": "1.0.0", "x": 1, ')
        import difflib
        tampered = {"plugin": "stated", "statements": {}, "answers": [{
            "n": 1, "why": "x", "sites": ["fit:10"], "version": "1.0.0",
            "before": V._sha(before), "after": V._sha(after),
            "diff": "".join(difflib.unified_diff(before.splitlines(keepends=True),
                                                 after.splitlines(keepends=True), "a", "b"))}]}
        V.design_record_path(k).write_text(json.dumps(tampered), encoding="utf-8")
        copy = Path(td) / "copy.py"
        copy.write_text(before, encoding="utf-8")
        out = []
        ck("a record whose diff changes a line outside every site does not replay",
           V.design_replay(k, copy, log=out.append) == 1
           and copy.read_text(encoding="utf-8") == before, out)


print("\n8. one line model; design arguments only, two hops; no added binding (W013 fix-up 3)")
# THE VERIFIER'S ROUTES AT af0f560, against a copy of the shipped plugin. Eleven form feeds (or
# line separators) in an admitted comment shifted every later index of the diff against the `ast`
# line numbers its sites are counted in; a fit site's names came from every argument, so the
# configuration, the gene mask, `refit_cooks` and `alpha` were all answerable; and a statement
# added beside a site line rode in with it. And the other way: two design answers two hops from
# the call - the terms a formula is built from, the column an interaction is picked by - were
# refused.
if hasattr(V, "design_answer"):
    with tempfile.TemporaryDirectory() as td:
        de_copy = Path(td) / "de.py"
        shutil.copyfile(ROOT / "kernels" / "de.py", de_copy)
        kd = Stub(de_copy, _de.spec)
        shipped = de_copy.read_text(encoding="utf-8")

        def verdict(name, edit):
            prop = Path(td) / f"{name}.py"
            with open(prop, "w", encoding="utf-8", newline="") as fh:
                fh.write(edit(shipped))
            out = []
            rc = V.design_answer(kd, prop, "x", log=out.append)
            admitted = rc == 0
            de_copy.write_text(shipped, encoding="utf-8")         # each probe on the shipped file
            rec = V.design_record_path(kd)
            if rec.exists():
                rec.unlink()
            return admitted, " ".join(out)

        def swap(old, new):
            def edit(t):
                assert old in t, old
                return t.replace(old, new, 1)
            return edit

        CONFIG = "    C = ctx.config\n"
        for ch, what in (("\x0c", "form feeds"), ("\u2028", "line separators")):
            ok_, out = verdict("lb", swap(CONFIG, "    C = ctx.config  # " + ch * 11 + "\n"))
            ck(f"eleven {what} in a comment are refused, by name", not ok_
               and "U+" in out, out[-300:])
        ok_, out = verdict("cr", lambda t: t.replace("\n", "\r\n"))
        ck("carriage returns are refused, by name", not ok_ and "carriage return" in out,
           out[-200:])
        _lm = getattr(V, "_lines", None)
        ck("one line model: a line is what `ast` counts", _lm is not None
           and _lm("a\x0cb\nc\u2028d\n") == ["a\x0cb\n", "c\u2028d\n"])
        for name, edit in (
                ("config", swap(CONFIG, '    C = dict(ctx.config, min_counts=2 * '
                                        'ctx.config["min_counts"])\n')),
                ("mask", swap("counts_df = pd.DataFrame(np.rint(sub[:, keep]).astype(int),",
                              'counts_df = pd.DataFrame(np.rint(sub[:, keep & (sub.sum(axis=0) '
                              '>= 2 * C["min_counts"])]).astype(int),')),
                ("refit", swap("refit_cooks=True, min_replicates",
                               "refit_cooks=False, min_replicates")),
                ("alpha", swap('                            alpha=C["alpha"],\n',
                               '                            alpha=0.5,\n')),
                ("added", swap("terms, subset=pop)\n",
                               "terms, subset=pop)  # the host's frame\n"
                               "        C = dict(C, alpha=0.5)\n"))):
            ok_, out = verdict(name, edit)
            ck(f"not a design answer, refused: {name}", not ok_, out[-300:])
        for name, edit in (
                ("terms", swap("use, aliased = _identifiable(ctx, sub_obs, terms)",
                               "use, aliased = _identifiable(ctx, sub_obs, terms + covs)")),
                ("hits", swap('hits = [c for c in cols if ":" in c and a_ in c and b_ in c]',
                              'hits = [c for c in cols if ":" in c and f"{a_}[" in c '
                              'and f"{b_}[" in c]'))):
            ok_, out = verdict(name, edit)
            ck(f"a design answer two hops from the call is admitted: {name}", ok_, out[-300:])
        ck("the depth is stated", getattr(V, "DESIGN_DEPTH", None) == 2
           and "metadata" in getattr(V, "DESIGN_ARGUMENTS", ()))

print()
if FAILS:
    print(f"{len(FAILS)} FAILED")
    raise SystemExit(1)
print("the maker demands the design, and the fixture can tell the answers apart")
