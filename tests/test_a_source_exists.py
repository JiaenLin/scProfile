"""A plugin's source exists, and its pin is what is built (harness RULES item 18, ROUTE R45; W055).

OFFLINE, WITH THE RECORDED VALUES. `REGISTRY` below is what doi.org answered for each DOI a
converted plugin declares, resolved 2026-11-12 (CSL JSON: the title, and the first date part of
`issued`). The plugins' own `wraps.doi_record` must agree with it, and the check must fail BY NAME
when a DOI does not resolve, when its record's title or year differs, when the DOI is written as a
URL, when the pin is a range, and when the pin is not the version the shipped lock builds.
`scprofile source <plugin> --resolve` asks doi.org itself; this suite never touches the network.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scprofile import source as S  # noqa: E402
from scprofile.kernels import discover  # noqa: E402

REGISTRY = {
    "10.1038/s41467-021-27150-6": {
        "title": "scCODA is a Bayesian model for compositional single-cell data analysis",
        "issued": {"date-parts": [[2021, 11, 25]]}},
    "10.1093/bioinformatics/btad547": {
        "title": "PyDESeq2: a python package for bulk RNA-seq differential expression analysis",
        "issued": {"date-parts": [[2023, 9, 1]]}},
    "10.1186/s13059-014-0550-8": {
        "title": "Moderated estimation of fold change and dispersion for RNA-seq data with DESeq2",
        "issued": {"date-parts": [[2014, 12, 5]]}},
    "10.1038/s41467-021-21246-9": {
        "title": "Inference and analysis of cell-cell communication using CellChat",
        "issued": {"date-parts": [[2021, 2, 17]]}},
    "10.1038/s41596-024-01045-4": {
        "title": "CellChat for systematic analysis of cell–cell communication from "
                 "single-cell transcriptomics",
        "issued": {"date-parts": [[2024, 9, 16]]}},
    # decoupler (autodev W068): resolved at doi.org 2026-11-13, CSL JSON as it answered.
    "10.1093/bioadv/vbac016": {
        "title": "decoupleR: ensemble of computational methods to infer biological activities "
                 "from omics data",
        "issued": {"date-parts": [[2022, 1, 1]]}},
}
CONVERTED = ("abundance", "de", "cellchat", "decoupler")
FAILS = []


def ck(what, ok, detail=""):
    print(f"  {'ok  ' if ok else 'FAIL'} {what}" + ("" if ok else f"\n       {detail}"))
    if not ok:
        FAILS.append(what)


def fetch(doi):
    if doi not in REGISTRY:
        raise LookupError("no such DOI")
    return REGISTRY[doi]


ks = discover()
print("1. each converted plugin declares a source and an exact pin, and they hold")
for name in CONVERTED:
    spec = ks[name].spec
    errs = [m for lvl, m in S.findings(spec, name, ROOT) if lvl in ("ERROR", "WARN")]
    ck(f"{name}: the form and the pin hold offline", not errs, errs)
    res = S.resolve(spec, fetch=fetch)
    ck(f"{name}: every DOI resolves to its recorded title and year",
       res and all(ok for ok, _d, _m in res), res)

print("2. a wrong source fails, by name")
base = json.loads(json.dumps(ks["abundance"].spec, default=str))
doi = S.dois(base)[0]


def variant(**wraps):
    v = json.loads(json.dumps(base))
    v["wraps"].update(wraps)
    return v


r = S.resolve(base, fetch=lambda d: (_ for _ in ()).throw(OSError("404")))
ck("a DOI that does not resolve fails, naming it",
   r and not r[0][0] and doi in r[0][2] and "does not resolve" in r[0][2], r)
rec = {doi: {"title": "scCODA is a Bayesian model for compositional single cell data analysis",
             "year": 2021}}
r = S.resolve(variant(doi_record=rec), fetch=fetch)
ck("a recorded title the record does not give fails, naming the DOI and both titles",
   r and not r[0][0] and doi in r[0][2] and "title" in r[0][2], r)
r = S.resolve(variant(doi_record={doi: {"title": REGISTRY[doi]["title"], "year": 2020}}),
              fetch=fetch)
ck("a recorded year the record does not give fails", r and not r[0][0] and "year" in r[0][2], r)
for bad, why in (("https://doi.org/" + doi, "a URL"), (doi + " ", "trailing whitespace"),
                 ("s41467-021-27150-6", "no directory indicator")):
    f = S.findings(variant(doi=bad), "abundance", ROOT)
    ck(f"a DOI written as {why} is an ERROR", any(lvl == "ERROR" and "is not a DOI" in m
                                                 for lvl, m in f), f)
f = S.findings(variant(doi_record={}), "abundance", ROOT)
ck("a DOI with no record entry is an ERROR", any(lvl == "ERROR" and "no entry" in m
                                                 for lvl, m in f), f)
f = S.findings(variant(doi_record={doi: {"title": "x", "year": "2021"}}), "abundance", ROOT)
ck("a year written as text is an ERROR", any("year" in m for lvl, m in f if lvl == "ERROR"), f)
f = S.findings(variant(doi_record={doi: {"title": "x", "year": 2021, "note": "y"}}), "abundance",
               ROOT)
ck("a record entry with a key beyond title and year is an ERROR", any(
    lvl == "ERROR" and "exactly" in m for lvl, m in f), f)

print("3. the pin is one version, and the one the lock builds")
for rng in (">=1.0,<2", "1.*", "~=1.0.4", "==1.0.4", "1.0.4,<2"):
    f = S.findings(variant(version=rng), "abundance", ROOT)
    ck(f"`wraps.version` {rng!r} is an ERROR", any(
        lvl == "ERROR" and "not one exact version" in m for lvl, m in f), f)
got, where = S.lock_pin(ROOT, "abundance", "pertpy")
ck("the shipped lock holds abundance and pins pertpy", got is not None, where)
f = S.findings(variant(version="1.0.3"), "abundance", ROOT)
ck("a pin the lock does not build is an ERROR naming both versions", any(
    lvl == "ERROR" and "1.0.3" in m and str(got) in m for lvl, m in f), f)
f = S.findings(json.loads(json.dumps({**base, "wraps": {k: v for k, v in base["wraps"].items()
                                                        if k != "version"}})), "abundance", ROOT)
ck("no pin at all is named", any("no exact pin" in m for _l, m in f), f)

print("4. the verb, through the real CLI, answered from a registry file")
with tempfile.TemporaryDirectory() as td:
    reg = Path(td) / "registry.json"
    reg.write_text(json.dumps(REGISTRY), encoding="utf-8")
    for name in CONVERTED:
        p = subprocess.run([sys.executable, "-m", "scprofile.cli", "source", name, "--resolve",
                            "--registry", str(reg)], cwd=ROOT, capture_output=True, text=True)
        ck(f"`scprofile source {name} --resolve` exits 0 on the recorded values",
           p.returncode == 0 and "hold" in p.stdout, (p.stdout + p.stderr)[-500:])
    one = dict(REGISTRY)
    one.pop("10.1038/s41467-021-27150-6")
    reg.write_text(json.dumps(one), encoding="utf-8")
    p = subprocess.run([sys.executable, "-m", "scprofile.cli", "source", "abundance",
                        "--resolve", "--registry", str(reg)], cwd=ROOT, capture_output=True,
                       text=True)
    ck("a DOI the registry does not hold fails the verb, naming it",
       p.returncode == 1 and "10.1038/s41467-021-27150-6 does not resolve" in p.stdout,
       (p.stdout + p.stderr)[-500:])

print(f"{len(FAILS)} failure(s)" + (": " + "; ".join(FAILS) if FAILS else
                                     ": a source exists and its pin is the one built"))
sys.exit(1 if FAILS else 0)
