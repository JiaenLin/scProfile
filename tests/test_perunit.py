"""Ten defects an adversarial review found after the wave rewrite. One test each.

Nine of the ten live on the PER-UNIT path, and none of them could fire with the kernels in the
tree today: the three `per_unit: sample` plugins are `status: planned` and `run` skips anything
not built. That is exactly the argument for testing them here rather than waiting - the first
built per-unit plugin, in-tree or supplied through $SCPROFILE_KERNELS, meets all nine at once,
and every one of them fails by delivering a document that looks complete.

Run: python tests/test_perunit.py
"""
import inspect
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scprofile import cli, merge, report                                        # noqa: E402

FAIL = []


def ck(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'} {name}" + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        FAIL.append(name)


def _payloads():
    """Three units of one plugin, the third having failed to produce its array output."""
    out = []
    for u in ("s1", "s2", "s3"):
        out.append({
            "kernel": "liana", "unit": u, "dir": f"kernels/liana/{u}",
            "status": "ok", "headline": f"{u}: 812 interactions", "version": "0.1",
            "obs": {"ccc_score": "obs/score.csv"},
            "obsm": {"X_ccc": "arrays/ccc.npy"},
            "tables": ["out/ccc_edges.csv"],
            "figures": [{"path": "figs/dot.png", "vector": "figs/dot.pdf",
                         "source": "figs/dot.csv", "caption": "dotplot"}],
            "caveats": [f"{u} caveat"],
        })
    return out


print("\nper-unit payloads survive folding")
f = merge.fold_payloads(_payloads())
ck("one entry per plugin", set(f) == {"liana"})
ck("every unit is kept", [u["unit"] for u in f["liana"]["units"]] == ["s1", "s2", "s3"],
   f"got {[u['unit'] for u in f['liana']['units']]}")
ck("every unit's figures are kept", len(f["liana"]["figures"]) == 3)
ck("every unit's caveats are kept", len(f["liana"]["caveats"]) == 3)
ck("the headline says it is per unit", "3 unit(s)" in f["liana"]["headline"])

print("\nfigure paths resolve from report/")
paths = [x["path"] for x in f["liana"]["figures"]]
ck("path carries the unit segment", all("/s" in p and p.startswith("kernels/liana/") for p in paths),
   str(paths))
ck("vector and source too",
   all(x["vector"].startswith("kernels/liana/s") and x["source"].startswith("kernels/liana/s")
       for x in f["liana"]["figures"]))
with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    report.write_kernel(d, "liana", f["liana"], [], "")
    html = (d / "report" / "liana.html").read_text()
    ck("rendered src includes the unit", 'src="../kernels/liana/s1/figs/dot.png"' in html,
       "hrefs still guess ../kernels/<name>/")
    ck("no unit-less kernel href survives", '"../kernels/liana/figs' not in html)
    ck("the page has a per-unit section", "Per unit" in html and "s3" in html)

print("\ntable names are the ones actually delivered")
ck("unit-suffixed", sorted(f["liana"]["tables"]) ==
   ["tables/liana_ccc_edges__s1.csv", "tables/liana_ccc_edges__s2.csv",
    "tables/liana_ccc_edges__s3.csv"], str(f["liana"]["tables"]))
ck("copy_tables and link_objects share one rule",
   "delivered_name" in inspect.getsource(merge.copy_tables)
   and "delivered_name" in inspect.getsource(merge.link_objects))
ck("a side-car object is unit-suffixed",
   merge.delivered_name({"kernel": "scenic", "unit": "s2"}, "scenic.loom") == "scenic__s2.loom")

print("\nthe report says what the merge did, not what the plugin declared")
with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    report.write_kernel(d, "liana", f["liana"], [], "", merged={"obs": ["ccc_score"], "obsm": []})
    html = (d / "report" / "liana.html").read_text()
    ck("a dropped obsm is not called merged", "NOT in the object" in html)
    ck("the merged obs still is", html.count("merged into the object by barcode") >= 1)

print("\na plugin that ran on some units and failed on others")
pay = {"ran": ["liana"], "skipped": [{"kernel": "liana", "unit": "s3", "why": ["boom"]},
                                     {"kernel": "liana", "unit": "s2", "why": ["bang"]}],
       "kernels": f, "cannot_show": {"liana": []}, "summaries": {}, "describe": {},
       "status": {"liana": "built"}}
with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    report.write_index(d, pay)
    idx = (d / "report" / "index.html").read_text()
    ck("the index does not call it a plain success", "unit(s) failed" in idx)
    ck("it names the units that are missing", "s3" in idx and "s2" in idx)
    ck("it says those cells are NaN", "NaN" in idx)
ck("every reason is kept, not the last one",
   "accumulate" in inspect.getsource(report.write_index).lower()
   or "setdefault" in inspect.getsource(report.write_index))

print("\nthe README counts plugins, not instances")
with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    (d / "report").mkdir()
    (d / "report" / "index.html").write_text("i")
    (d / "report" / "liana.html").write_text("k")
    cli._write_readme(d, dict(pay, version="0.1", input="x.h5ad", object=str(d / "o.h5ad")))
    md = (d / "README.md").read_text()
    ck("one plugin ran, none failed outright", "**1** plugin(s) ran, **0** did not" in md,
       md.splitlines()[2] if len(md.splitlines()) > 2 else md[:120])
    ck("the partial run is named as such", "not on every unit" in md and "s3" in md)
    ck("the layout section sees report/", "report/" in md)
    n = int(md.split("- ")[2].split(" files")[0])
    ck("the file count includes README.md itself", n == 3, f"counted {n} of 3")

print("\nsingle-instance plugins are unchanged in shape")
one = merge.fold_payloads([{"kernel": "cellcycle", "unit": None, "dir": "kernels/cellcycle",
                            "status": "ok", "headline": "h", "obs": {"phase": "o.csv"},
                            "tables": ["t.csv"], "figures": [{"path": "f.png"}]}])
ck("no per-unit section", not one["cellcycle"]["per_unit"])
ck("headline is the plugin's own", one["cellcycle"]["headline"] == "h")
ck("path is still run-relative", one["cellcycle"]["figures"][0]["path"] == "kernels/cellcycle/f.png")

print("\nthe live defects")
ck("--dry-run reaches refs.fetch", "dry_run=" in inspect.getsource(cli._fetch))
ck("--kernel a,a is deduplicated", cli._split("a,b,a") == ["a", "b"])
src = inspect.getsource(cli._run)
ck("the budget is redivided over what launches", "_budget(live, budget)" in src)
ck("per_unit with no unit key is announced", "per_unit and no unit key" in src.replace("\n", " ")
   or "declare per_unit" in src)
ck("the README is written after the report", src.index("report.write_all") < src.index("_write_readme(out"))

print("\nthe smoke fixture is not a shipped plugin")
from scprofile.kernels import discover                                         # noqa: E402
import os as _os
_os.environ.pop("SCPROFILE_KERNELS", None)
ck("perunit is absent from the default set", "perunit" not in discover(),
   "a fixture that computes nothing must never be discoverable as a method")
_os.environ["SCPROFILE_KERNELS"] = str(Path(__file__).resolve().parent / "smoke")
ck("it IS discoverable when a site asks for it", "perunit" in discover())
_os.environ.pop("SCPROFILE_KERNELS", None)

print("\nthe budget divides once, however many times it is applied")
from scprofile.kernels import _budget                                          # noqa: E402
w = [{"plugin": "velocity", "unit": None, "cores": 8},
     {"plugin": "cellcycle", "unit": None, "cores": 1}] + \
    [{"plugin": "perunit", "unit": f"S{i}", "cores": 1} for i in range(1, 5)]
_budget(w, 4)
first = [i["cores"] for i in w]
_budget(w, 4)
ck("re-budgeting an unfiltered wave changes nothing", [i["cores"] for i in w] == first,
   f"{first} became {[i['cores'] for i in w]}")
ck("velocity keeps its planned share", first[0] == 2, str(first))
live = [i for i in w if i["plugin"] != "perunit"]
_budget(live, 4)
ck("re-budgeting a FILTERED wave gives the survivors more",
   [i["cores"] for i in live] == [3, 1], str([i["cores"] for i in live]))
w2 = [{"plugin": "a", "unit": None, "cores": 2}, {"plugin": "b", "unit": None, "cores": 1}]
_budget(w2, 8)
ck("an under-subscribed wave is left alone", [i["cores"] for i in w2] == [2, 1])

print("\nthe uns payload is writable, checked before write_h5ad")
prov = merge.provenance(f, {"n_obs": 10, "compartment": None}, {"liana": ["x"]},
                        merged={"liana": {"obs": ["ccc_score"], "obsm": [],
                                          "dropped": ["obsm[X_ccc]"]}})
ck("a per-unit plugin's units are strings", prov["kernels"]["liana"]["units"] == ["s1", "s2", "s3"])
ck("a None in describe is normalised, not refused", prov["input"]["compartment"] == "")
ck("produced_obsm reports the merge, not the declaration",
   prov["kernels"]["liana"]["produced_obsm"] == [] and
   prov["kernels"]["liana"]["not_merged"] == ["obsm[X_ccc]"])
one_p = merge.provenance(one, {}, {})
ck("a plugin with no units gets [], never [None]", one_p["kernels"]["cellcycle"]["units"] == [],
   str(one_p["kernels"]["cellcycle"]["units"]))
try:
    merge._uns_safe({"k": ["a", None]})
    ck("a None inside a list is refused", False, "it was accepted")
except merge.MergeError as e:
    ck("a None inside a list is refused", "None" in str(e))

print("\nbarcodes must be unique before any reindex")
ck("there is a precondition", hasattr(merge, "_require_unique_barcodes"))
try:
    class _A:
        class _N:
            is_unique = False

            @staticmethod
            def astype(_):
                return ["a", "a", "b"]
        obs_names = _N()
    merge._require_unique_barcodes(_A())
    ck("it raises", False, "no error on duplicate barcodes")
except merge.MergeError as e:
    ck("it raises MergeError naming the cause", "not unique" in str(e))
except Exception as e:                                                   # noqa: BLE001
    ck("it raises MergeError", False, type(e).__name__)

print("\n" + ("all per-unit checks passed" if not FAIL else f"{len(FAIL)} FAILED: {FAIL}"))
sys.exit(1 if FAIL else 0)
