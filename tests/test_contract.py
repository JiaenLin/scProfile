#!/usr/bin/env python3
"""The contract, tested with the standard library only.

`manifest` and `kernels` are stdlib-only BY DESIGN - a kernel in a pinned environment imports
`manifest`, and a host that could not enumerate its kernels without pyyaml would fail at exactly
the moment a user is trying to work out why nothing runs. This file holds that line: it runs on a
bare interpreter, so if it ever needs numpy the design has drifted.

    python3 tests/test_contract.py
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scprofile import manifest                                            # noqa: E402
from scprofile.kernels import Kernel, discover, order, undeclared, unmet   # noqa: E402

FAILED = []


def check(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'} {name}" + (f"   {detail}" if detail and not cond
                                                      else ""))
    if not cond:
        FAILED.append(name)


def test_contract_roundtrip(tmp):
    print("\ncontract round-trip")
    p = tmp / "in.json"
    manifest.write_input(p, h5ad=tmp / "x.h5ad", out_dir=tmp / "k", keys={"label": "cell_type"},
                         organism="mouse", assay="nucleus",
                         upstream={"velocity": tmp / "k" / "velocity"},
                         params={"mode": "dynamical"})
    d = manifest.read_input(p)
    check("upstream survives", d["upstream"] == {"velocity": str((tmp / "k" / "velocity").resolve())})
    check("sentinels defaulted", d["sentinels"] == list(manifest.DEFAULT_SENTINELS))
    check("params survive", d["params"] == {"mode": "dynamical"})
    check("paths absolute", Path(d["h5ad"]).is_absolute())


def test_old_kernel_reads_new_input(tmp):
    """A kernel written against 1.0 must still run: only the MAJOR is compared."""
    print("\na 1.0 kernel against a 1.1 host")
    p = tmp / "in10.json"
    payload = json.loads((tmp / "in.json").read_text())
    payload["contract"] = "1.0"
    p.write_text(json.dumps(payload))
    try:
        d = manifest.read_input(p)
        check("1.0 in.json still readable", True)
        check("missing 1.1 fields default", d.get("upstream") is not None)
    except manifest.ContractError as e:
        check("1.0 in.json still readable", False, str(e))


def test_objects_slot(tmp):
    print("\nthe objects slot")
    out = tmp / "vel"
    out.mkdir(parents=True, exist_ok=True)
    obj = out / "velocity.h5ad"
    obj.write_bytes(b"not really an h5ad, but it exists")
    manifest.write_output(out, kernel="velocity", version="0.1.0", status="ok",
                          objects={"velocity_h5ad": obj}, caveats=["synthetic"])
    d = manifest.read_output(out)
    check("objects declared and found", d["objects"] == {"velocity_h5ad": "velocity.h5ad"})
    check("path is RELATIVE to out_dir", not Path(d["objects"]["velocity_h5ad"]).is_absolute())
    check("no unknown keys", manifest.unknown_keys(d) == [], str(manifest.unknown_keys(d)))


def test_captioned_figures(tmp):
    """A figure entry may be a bare path or a mapping with caption, vector copy and source data.
    Every file it names is validated, because a report linking a missing PDF is a report that
    looks complete and is not."""
    print("\ncaptioned figures")
    out = tmp / "figs"
    (out / "figures" / "source_data").mkdir(parents=True, exist_ok=True)
    png = out / "figures" / "F1.png"; png.write_bytes(b"png")
    pdf = out / "figures" / "F1.pdf"; pdf.write_bytes(b"pdf")
    csv = out / "figures" / "source_data" / "F1.csv"; csv.write_text("a,b\n1,2\n")
    bare = out / "figures" / "F2.png"; bare.write_bytes(b"png")
    manifest.write_output(
        out, kernel="k", status="ok",
        figures=[{"path": png, "vector": pdf, "source": csv, "caption": "what it shows"},
                 bare])
    d = manifest.read_output(out)
    f0, f1 = d["figures"]
    check("caption survives", f0["caption"] == "what it shows")
    check("vector recorded", f0.get("vector") == "figures/F1.pdf", str(f0))
    check("source recorded", f0.get("source") == "figures/source_data/F1.csv", str(f0))
    check("subdirectory kept in the path", f0["path"] == "figures/F1.png", str(f0))
    check("a bare path still works", f1 == {"path": "figures/F2.png", "caption": ""}, str(f1))
    check("figure_paths finds every file", len(manifest.figure_paths(d)) == 4,
          str(manifest.figure_paths(d)))

    # A vector copy named but not written must be caught: the report would link it.
    out2 = tmp / "figs2"
    (out2 / "figures").mkdir(parents=True, exist_ok=True)
    (out2 / "figures" / "F1.png").write_bytes(b"png")
    import json as _j
    (out2 / "out.json").write_text(_j.dumps({
        "contract": manifest.CONTRACT_VERSION, "kernel": "k", "status": "ok",
        "figures": [{"path": "figures/F1.png", "vector": "figures/F1.pdf", "caption": ""}]}))
    try:
        manifest.read_output(out2)
        check("a missing vector copy is caught", False)
    except manifest.ContractError as e:
        check("a missing vector copy is caught", "F1.pdf" in str(e))


def test_figure_conventions():
    """The settings that decide whether a figure is publishable rather than merely readable."""
    print("\npublication conventions")
    from scprofile import figure
    check("vector text stays live (fonttype 42)", figure.RC["pdf.fonttype"] == 42,
          "type 3 converts glyphs to paths; journals reject it and you find out at resubmission")
    check("raster output is print resolution", figure.RC["savefig.dpi"] >= 300)
    check("journal column widths", round(figure.SINGLE * 25.4) == 85
          and round(figure.DOUBLE * 25.4) == 174)
    check("colourblind-safe palette", len(figure.OKABE_ITO) >= 8)
    pal = figure.palette(["Beta", "Alpha"])
    check("colour per label is order-independent", pal == figure.palette(["Alpha", "Beta"]),
          "a legend meaning one thing in panel A and another in panel B is worse than none")


def test_declared_but_absent_is_refused(tmp):
    """The one failure this contract exists to catch: a kernel naming a file it did not write."""
    print("\na declared output that does not exist")
    out = tmp / "liar"
    out.mkdir(parents=True, exist_ok=True)
    (out / "out.json").write_text(json.dumps({
        "contract": manifest.CONTRACT_VERSION, "kernel": "liar", "status": "ok",
        "objects": {"thing": "nowhere.h5ad"}}))
    try:
        manifest.read_output(out)
        check("refuses a promise", False, "it merged a file that does not exist")
    except manifest.ContractError as e:
        check("refuses a promise", "nowhere.h5ad" in str(e))
        check("names the offending path", "objects[thing]" in str(e), str(e))


def test_velocity_declaration():
    print("\nvelocity's own declaration")
    k = Kernel(Path(__file__).resolve().parents[1] / "kernels" / "velocity")
    slots = k.declared_slots()
    check("declares the side-car object", "velocity_h5ad" in slots.get("objects", set()))
    check("declares no layers", "layers" not in slots,
          "velocity layers are on a SELECTED gene set and must not be merged into the full object")
    check("needs both layers", set(k.needs_layers) == {"spliced", "unspliced"})
    check("ships a guard", k.guard is not None)
    check("ships a lock", (k.path / "lock.yml").exists())
    check("ships a selftest", (k.path / "selftest.py").exists())
    check("declares its limits", len(k.cannot_show) >= 6, f"{len(k.cannot_show)}")

    # The lock exists to STOP the resolver picking today's versions. A lock with no `==` is a
    # lock in name only, and this is the exact failure it was written for.
    lock = (k.path / "lock.yml").read_text()
    pins = [ln.strip() for ln in lock.splitlines()
            if ln.strip().startswith("- ") and "==" in ln]
    check("lock pins exactly", len(pins) >= 10, f"only {len(pins)} `==` pins")
    check("scvelo is pinned", any("scvelo==" in p for p in pins))
    check("pandas is pinned", any("pandas==" in p for p in pins),
          "scvelo declares pandas>=1.1.1, which today resolves to pandas 3")

    # A wildcard in `produces` must still HOLD the kernel to a shape.
    ok = {"kernel": "velocity", "obsm": {"velocity_scanvi": "a.npy"},
          "objects": {"velocity_h5ad": "v.h5ad"}}
    check("glob accepts the runtime basis", undeclared(k, ok) == [], str(undeclared(k, ok)))
    bad = {"kernel": "velocity", "obsm": {"something_else": "a.npy"}}
    check("glob still catches an undeclared output", undeclared(k, bad) == ["obsm[something_else]"],
          str(undeclared(k, bad)))


def test_lock_is_read_not_delegated():
    """The lock is parsed here, not handed to conda. Sites run conda 4.10; `env create --yes`
    does not exist there, and a pip section conda runs as a second resolve reports its failures
    as a warning."""
    print("\nthe lock, as the installer reads it")
    from scprofile.runner import lock_spec
    k = Kernel(Path(__file__).resolve().parents[1] / "kernels" / "velocity")
    s = lock_spec(k)
    check("pins the interpreter", s["python"] == "3.11", str(s["python"]))
    check("reads every pip pin", len(s["pip"]) >= 15, f"{len(s['pip'])}")
    check("every pip entry is pinned", all("==" in x for x in s["pip"]),
          str([x for x in s["pip"] if "==" not in x]))
    check("no stray conda deps", s["conda"] == [], str(s["conda"]))
    check("channel declared", s["channels"] == ["conda-forge"], str(s["channels"]))
    check("`pip` itself is not a pin", "pip" not in s["conda"])

    # A lock with no interpreter pin is not a lock: wheels are built per minor version.
    import tempfile as _tf
    with _tf.TemporaryDirectory() as td:
        d = Path(td) / "bad"
        d.mkdir()
        (d / "kernel.yml").write_text("name: bad\nentry: run.py\n")
        (d / "lock.yml").write_text("dependencies:\n  - pip\n")
        try:
            lock_spec(Kernel(d))
            check("refuses a lock with no python pin", False)
        except ValueError as e:
            check("refuses a lock with no python pin", "python" in str(e).lower())


def test_unmet_names_the_fix():
    print("\nunmet prerequisites name their fix")
    ks = discover()
    k = ks["velocity"]

    # velocity declares can_source_layers, so the HOST must not block it on a missing layer: the
    # kernel goes and looks, and refuses with a list of everywhere it searched. Blocking here
    # would mean the search never runs and the user is told "layers absent" about files that are
    # sitting on disk beside the object.
    check("host does not block a kernel that can source its own layers",
          unmet(k, obs=set(), obsm=set(), layers={"counts"}, ran=()) == [])
    check("velocity declares it", k.can_source_layers)
    check("it still declares WHAT it needs, for doctor",
          set(k.needs_layers) == {"spliced", "unspliced"})
    check("it ships the finder", (k.path / "sources.py").exists())

    # A kernel that cannot source its own inputs is still blocked, and still names the fix.
    import types
    fake = types.SimpleNamespace(
        needs_obs=["phase"], needs_obsm=[], needs_layers=["spliced"], needs_kernels=[],
        needs_design=False, can_source_layers=False, name="fake")
    probs = unmet(fake, obs=set(), obsm=set(), layers=set(), ran=())
    check("a non-sourcing kernel is still blocked", len(probs) == 2, str(probs))
    check("and names its producer", any("cellcycle" in p for p in probs), " | ".join(probs))
    check("and says spliced cannot be derived",
          any("aligner" in p.lower() for p in probs), " | ".join(probs))


def test_ordering():
    print("\nordering")
    ks = discover()
    names = sorted(ks)
    o = order(names, ks)
    check("orders every kernel exactly once", sorted(o) == names, str(o))
    for n in names:
        for dep in ks[n].needs_kernels:
            if dep in o:
                check(f"{dep} before {n}", o.index(dep) < o.index(n))


def test_no_project_data():
    """This repository is public. Nothing from any particular dataset belongs in it.

    Checked because it has happened in a sibling repo: a worked example carried a real cell type
    and a real cell count as sample output. Example output is the SHAPE of a table, never a result.
    """
    import re
    print("\nno dataset-specific content")
    pat = re.compile(r"cardiomyo|matrifibro|endocardial|pericyte|celescope|cellbender"
                     r"|\bsambo\b|wangyb|duke-nus|aging_hfd|young_hfd", re.I)
    bad = []
    for f in list(root.glob("*.md")) + list(root.glob("docs/**/*.md")) \
            + list(root.glob("scprofile/*.py")) + list(root.glob("kernels/**/*.py")) \
            + list(root.glob("kernels/**/*.yml")):
        for i, ln in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if pat.search(ln):
                bad.append(f"{f.relative_to(root)}:{i}")
    check("no dataset-specific content anywhere", not bad, ", ".join(bad[:6]))


def test_wrapping_plugins_record_upstream():
    """A plugin that wraps someone else's tool must carry that tool's own instructions.

    Not a documentation nicety. The defaults that matter are the ones that do not error: LIANA+
    defaults to a HUMAN ligand-receptor resource and returns a small plausible table on mouse data;
    scanpy's score_genes defaults to `use_raw=None`, meaning use `.raw` if present, so the same
    plugin scores different values on two objects that differ only in whether an upstream step
    left one behind. Both were found by reading the documentation and writing it down, and neither
    would have been found by reading the plugin.
    """
    print("\nwrapping plugins record upstream")
    for name, k in sorted(discover().items()):
        w = k.spec.get("wraps") or {}
        if not w:
            continue
        up = k.path / "UPSTREAM.md"
        check(f"{name}: UPSTREAM.md present", up.exists())
        if not up.exists():
            continue
        s = up.read_text(encoding="utf-8")
        check(f"{name}: records the licence", bool(w.get("license")))
        check(f"{name}: records a citation", bool(w.get("cite")))
        check(f"{name}: names the defaults it changes", "default" in s.lower())
        check(f"{name}: records what it does NOT use", "not used" in s.lower()
              or "under-use" in s.lower())
        check(f"{name}: links the upstream docs", "http" in s)


def main():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        test_contract_roundtrip(tmp)
        test_old_kernel_reads_new_input(tmp)
        test_objects_slot(tmp)
        test_captioned_figures(tmp)
        test_declared_but_absent_is_refused(tmp)
    test_figure_conventions()
    test_velocity_declaration()
    test_lock_is_read_not_delegated()
    test_unmet_names_the_fix()
    test_ordering()
    test_wrapping_plugins_record_upstream()
    print()
    if FAILED:
        print(f"{len(FAILED)} FAILED: {', '.join(FAILED)}")
        return 1
    print("all contract checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
