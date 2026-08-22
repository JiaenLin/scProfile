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
        up = k.path / "UPSTREAM.md" if k.path.is_dir() else k.path
        # EITHER SHAPE. A one-file plugin carries its upstream record in PLUGIN["upstream"],
        # where it cannot drift from the code it describes; a directory plugin carries
        # UPSTREAM.md beside the wrapper. What is checked is that the record EXISTS and says the
        # things that matter - not which file it lives in.
        inline = dict(k.spec.get("upstream") or {})
        check(f"{name}: an upstream record exists", up.exists() or bool(inline))
        if inline:
            check(f"{name}: records the licence", bool(w.get("license")))
            check(f"{name}: records a citation", bool(w.get("cite")))
            check(f"{name}: links the upstream docs", bool(inline.get("docs")))
            check(f"{name}: names the defaults it changes", bool(inline.get("defaults_changed")))
            check(f"{name}: records what it does NOT use", bool(inline.get("not_used")))
            continue
        if not up.exists():
            continue
        s = up.read_text(encoding="utf-8")
        check(f"{name}: records the licence", bool(w.get("license")))
        check(f"{name}: records a citation", bool(w.get("cite")))
        check(f"{name}: names the defaults it changes", "default" in s.lower())
        check(f"{name}: records what it does NOT use", "not used" in s.lower()
              or "under-use" in s.lower())
        check(f"{name}: links the upstream docs", "http" in s)
        # A scaffolded template contains the required section headings and nothing in them, so
        # every check above passes on a file that records no reading at all. A plugin that has
        # graduated to `wraps:` is claiming the reading happened.
        todos = s.count("TODO")
        check(f"{name}: UPSTREAM.md is filled in, not the template", todos == 0,
              f"{todos} TODO marker(s) remain")


def test_schedule():
    """Waves come from the DEPENDENCY GRAPH, not from a wave index, and the budget is not exceeded.

    A wave is not a barrier unless the graph says so: a plugin must wait only on what it declares
    it needs. Waiting on whatever else happened to be scheduled beside it is the difference between
    a plan and a queue.
    """
    print("\nschedule")
    import types
    from scprofile.kernels import schedule

    def fake(name, cost="medium", cores=1, needs=(), unit=None):
        return types.SimpleNamespace(
            name=name, needs_kernels=list(needs), per_unit=unit,
            executor={"cost": cost, "cores": cores, "memory_gb_per_100k": None})

    ks = {"a": fake("a", "trivial", 1),
          "b": fake("b", "high", 8),
          "c": fake("c", "medium", 4, needs=["a"]),
          "d": fake("d", "low", 2, unit="sample")}
    plan = schedule(["a", "b", "c", "d"], ks, budget_cores=16, units=["s1", "s2", "s3"])

    check("two waves, split by the one real dependency", len(plan) == 2, str(len(plan)))
    w1 = [i["plugin"] for i in plan[0]]
    check("c waits for a", "c" not in w1 and "c" in [i["plugin"] for i in plan[1]])
    check("b, d do NOT wait for a", {"b", "d"} <= set(w1), str(w1))
    check("longest pole first", w1[0] == "b", str(w1))
    check("per_unit fans out over units", w1.count("d") == 3, str(w1))
    for wave in plan:
        used = sum(i["cores"] for i in wave)
        check(f"budget respected ({used} <= 16)", used <= 16)
        check("every instance gets at least one core", all(i["cores"] >= 1 for i in wave))

    solo = schedule(["b"], {"b": fake("b", "high", 64)}, budget_cores=8)
    check("a plugin wanting more than the budget runs alone at the budget",
          solo[0][0]["cores"] == 8, str(solo))


def test_key_map_is_resolved():
    """`needs` names KEYS, so every consumer of it must resolve them.

    The format requires a plugin to name `{label}` rather than a real column — a plugin naming a
    column has bound itself to one project. `unmet()` checked for a column literally called
    `{label}`, which no object has, so every correctly-written plugin failed its own prerequisite
    check. The failure read as a property of the dataset rather than of the resolver, which is why
    it survived: seven plugins reported "would refuse: obs['{label}'] is absent" against an object
    that had the column.
    """
    print("\nkey map")
    import types
    from scprofile.kernels import resolve_keys, unmet

    keys = {"label": "cell_type", "counts": "counts", "lognorm": "lognorm"}
    check("placeholders substitute",
          resolve_keys(["obs/{label}", "layers/{counts}"], keys)
          == ["obs/cell_type", "layers/counts"])
    check("an unknown key is left intact, not dropped",
          resolve_keys(["{nosuch}"], keys) == ["{nosuch}"],
          "it must surface as a missing capability naming the key")

    k = types.SimpleNamespace(
        needs_obs=["{label}"], needs_obsm=[], needs_layers=["{counts}"], needs_kernels=[],
        needs_design=False, can_source_layers=False, name="x")
    check("resolved needs are satisfied",
          unmet(k, obs={"cell_type"}, layers={"counts"}, keys=keys) == [])
    got = unmet(k, obs=set(), layers=set(), keys=keys)
    check("and an absence names the RESOLVED column", any("cell_type" in p for p in got),
          " | ".join(got))


def test_scaffold_cannot_produce_a_running_noop():
    """A scaffold must refuse to run until its method call is written.

    A scaffold that produced a runnable no-op would produce EMPTY RESULTS THAT LOOK LIKE REAL
    ONES — a plugin reporting nothing found, merged into the object, rendered in the report, with
    nothing anywhere saying it was never implemented. That is the failure this whole tool is
    arranged against, arriving through the door marked convenience.
    """
    print("\nscaffold refuses")
    from scprofile import scaffold as SC
    check("run.py raises before writing output",
          "raise SystemExit(" in SC.RUN_PY
          and SC.RUN_PY.index("raise SystemExit(") < SC.RUN_PY.index("manifest.write_output"))
    check("selftest fails until written", "return 1" in SC.SELFTEST)
    check("lock has no versions to inherit", "==X.Y.Z" in SC.LOCK or "TODO" in SC.LOCK)
    check("UPSTREAM template is not presented as complete", SC.UPSTREAM.count("TODO") >= 4)
    check("references template warns against remembered URLs",
          "from memory" in SC.REFERENCES)


def test_validate_catches_what_got_through():
    """Every check in the validator exists because something got through.

    Asserted against synthetic defects rather than against the real plugins, so the checks keep
    firing once the real plugins are clean — a check that only ever passes is a check nobody knows
    is broken.
    """
    print("\nvalidate")
    import tempfile
    from scprofile import validate as V
    from scprofile.kernels import Kernel

    with tempfile.TemporaryDirectory() as td:
        d = Path(td) / "bad"
        d.mkdir()
        (d / "kernel.yml").write_text(
            "name: bad\nsummary: a plugin with every defect\nstatus: built\n"
            "language: python\nentry: run.py\nneeds_env: true\n"
            "wraps:\n  tool: something\nproduces:\n  - obs[x]\n")
        (d / "run.py").write_text(
            "import os\nn = os.cpu_count()\nlab = adata.obs['cell_type']\n")
        (d / "lock.yml").write_text(
            "name: x\nchannels:\n  - conda-forge\ndependencies:\n  - python=3.11\n  - pip\n"
            "  - pip:\n      - numpy\n")
        (d / "UPSTREAM.md").write_text("# Upstream\n\nTODO\n")
        f = V.validate_plugin(Kernel(d))
        got = {x.check for x in f}

        def has(frag):
            return any(frag in c for c in got)

        check("empty cannot_show", has("cannot_show is empty"))
        check("os.cpu_count()", has("os.cpu_count()"))
        check("hard-coded column name", has("hard-coded domain name"))
        check("unpinned dependency", has("unpinned dependencies"))
        check("missing selftest", has("no selftest"))
        check("UPSTREAM still the template", has("still the template"))
        check("licence not recorded", has("wraps.license"))

        # a channel is not a dependency: counting it trains a reader to ignore the check
        loose = [x for x in f if "unpinned" in x.check]
        check("channels are not reported as unpinned",
              all("conda-forge" not in (x.detail or "") for x in loose),
              str([x.detail for x in loose]))

    # references
    with tempfile.TemporaryDirectory() as td:
        d = Path(td) / "refs"
        d.mkdir()
        (d / "kernel.yml").write_text("name: refs\nsummary: s\ncannot_show:\n  - x\n")
        (d / "references.yml").write_text(
            "db:\n  url: https://example.org/db.feather\n  sha256: notahash\n")
        f = V.validate_references(Kernel(d))
        got = {x.check for x in f}
        check("a bad checksum is caught", any("not a 64-char hex" in c for c in got), str(got))
        check("a missing size is caught", any("declares no size" in c for c in got), str(got))

        # The regression that made this necessary: _mini_yaml gained nested mappings and
        # references() silently stopped parsing anything. A references.yml that parses to NOTHING
        # gives a plugin zero declared references — and resolve() then finds nothing missing and
        # PASSES. The plugin runs with no reference data and reports success.
        refs = Kernel(d).references()
        check("references.yml actually parses", set(refs) == {"db"}, str(refs))
        check("and its fields survive", refs.get("db", {}).get("url", "").startswith("https://"),
              str(refs))


def test_r_lock_section():
    """An R plugin's method may be distributed only from git, and the lock has to say so exactly.

    Every check here is a way the section could look pinned while not being pinned - which is the
    failure mode a lock exists to prevent, and the one that leaves no trace in the environment it
    produced.
    """
    print("\nthe r: section of a lock")
    from scprofile.runner import install, lock_spec, r_pin_kind
    root = Path(__file__).resolve().parents[1]
    k = Kernel(root / "kernels" / "cellchat")
    s = lock_spec(k)
    check("cellchat's lock parses", len(s["conda"]) > 40, f"{len(s['conda'])} conda pins")
    check("every conda line is pinned", all("=" in x for x in s["conda"]),
          str([x for x in s["conda"] if "=" not in x]))
    # Both FORMS must appear, and every entry must classify as one of them. Asserting a COUNT
    # here made the suite fail the moment a third pin was added for a real reason - a test that
    # breaks on correct change teaches people to edit tests rather than read them.
    kinds = [r_pin_kind(x) for x in s["r"]]
    check("every r: entry is one of the two exact forms", all(kinds), str(list(zip(s["r"], kinds))))
    check("at least one is a CRAN version", "cran" in kinds, str(kinds))
    check("at least one is a git commit", "git" in kinds, str(kinds))
    # An R lock pins r-base and NOT python. Demanding a python pin from an R lock is the format
    # asserting an assumption; r-base decides which binaries every r-* package resolves against.
    check("an r lock needs no python pin", s["python"] is None, str(s["python"]))
    check("and does pin r-base", any(x.startswith("r-base=") for x in s["conda"]))

    check("a branch is not a pin", r_pin_kind("owner/repo@main") is None)
    check("a tag is not a pin", r_pin_kind("owner/repo@v2.2.0") is None)
    check("a short sha is not a pin", r_pin_kind("owner/repo@75253cd") is None)
    check("a version range is not a pin", r_pin_kind("NMF>=0.23.0") is None)

    with tempfile.TemporaryDirectory() as td:
        d = Path(td) / "rk"
        d.mkdir()
        (d / "kernel.yml").write_text("name: rk\nsummary: s\nlanguage: r\nentry: run.R\n"
                                      "needs_env: true\n")
        # A SECTION THE INSTALLER DOES NOT APPLY MUST RAISE. Before this, an `r:` section was read
        # and silently skipped: the fingerprint would then say the environment was built from a
        # lock whose R packages it does not contain.
        (d / "lock.yml").write_text("dependencies:\n  - r-base=4.3.3\nweird:\n  - x\n")
        try:
            lock_spec(Kernel(d))
            check("an unknown section raises", False, "it was skipped")
        except ValueError as e:
            check("an unknown section raises", "not a section this installer applies" in str(e))

        (d / "lock.yml").write_text("dependencies:\n  - r-base=4.3.3\nr:\n  - owner/repo@main\n")
        try:
            lock_spec(Kernel(d))
            check("a branch in r: raises", False, "it was accepted as a pin")
        except ValueError as e:
            check("a branch in r: raises", "40-char commit" in str(e))

        (d / "lock.yml").write_text("dependencies:\n  - r-dplyr=1.1.4\n")
        try:
            lock_spec(Kernel(d))
            check("an r lock with no r-base raises", False)
        except ValueError as e:
            check("an r lock with no r-base raises", "r-base" in str(e))

        # `install` must tell a plugin that CANNOT have an environment apart from one that has not
        # been given one yet. "no lock.yml" was true of both and explained neither.
        (d / "kernel.yml").write_text("name: rk\nsummary: s\nneeds_env: false\n")
        try:
            install(Kernel(d), Path(td) / "prefix")
            check("install refuses a needs_env:false plugin", False, "it tried to build one")
        except RuntimeError as e:
            check("install refuses a needs_env:false plugin", "needs_env: false" in str(e))
            check("and points at selftest instead", "scprofile selftest" in str(e))
        (d / "kernel.yml").write_text("name: rk\nsummary: s\nneeds_env: true\nstatus: planned\n")
        (d / "lock.yml").unlink()
        try:
            install(Kernel(d), Path(td) / "prefix")
            check("install refuses a plugin with no lock", False)
        except FileNotFoundError as e:
            check("install refuses a plugin with no lock", "lock.yml" in str(e))
            check("and says which state it is in", "status: planned" in str(e))


def test_every_lock_is_validated_whatever_the_status():
    """A lock is about an ENVIRONMENT; a status is about a run.py. They arrive in either order.

    These checks used to run only for a plugin whose status is `built`, so four of the five locks
    in this tree - installed environments, proved by their own selftests - were validated by
    nothing at all.
    """
    print("\nevery lock in the tree is checked, built or not")
    from scprofile import validate as V
    for name, k in sorted(discover().items()):
        if not (k.path / "lock.yml").exists():
            continue
        errs = [f for f in V.validate_plugin(k)
                if f.level == "ERROR" and "lock.yml" in f.check]
        check(f"{name}: lock has no pin errors ({k.status})", not errs, str(errs))
    locked = [n for n, k in discover().items() if (k.path / "lock.yml").exists()]
    planned = [n for n in locked if discover()[n].status != "built"]
    check("and some of them are planned, which is the point", bool(planned), str(planned))


def test_a_half_built_environment_is_not_a_built_one():
    """`install` used to ask only whether the DIRECTORY exists. Two ways that is wrong.

    Both were live on PBS 676357, where a conda step built 306 packages, the `r:` step failed, and
    the directory left behind looked finished from the outside.
    """
    print("\nan environment that exists is not one that was finished")
    from scprofile import runner
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        d = td / "k"
        d.mkdir()
        (d / "kernel.yml").write_text("name: k\nsummary: s\nneeds_env: true\n")
        (d / "lock.yml").write_text("channels:\n  - conda-forge\ndependencies:\n  - python=3.11\n")
        pref = td / "prefix"
        env = runner.env_prefix("k", pref)
        (env / "bin").mkdir(parents=True)
        (env / "bin" / "python").write_text("#!/bin/sh\n")
        (env / "left_by_the_previous_lock").write_text("x")

        # No stamp: the build never reached its last act, so the environment is not the one the
        # lock describes and must not be handed to a selftest as though it were.
        try:
            runner.install(Kernel(d), pref)
            check("a stampless environment is refused", False, "install carried on")
        except RuntimeError as e:
            check("a stampless environment is refused", "exists but is stale" in str(e))
            check("and the refusal names --force", "--force" in str(e))

        # A stamp from a DIFFERENT lock is the same fact wearing a different hat.
        (env / ".scprofile_lock").write_text("deadbeefcafe")
        try:
            runner.install(Kernel(d), pref)
            check("an environment built from another lock is refused", False)
        except RuntimeError as e:
            check("an environment built from another lock is refused",
                  "deadbeefcafe" in str(e) and "current lock is" in str(e))

        # A matching stamp is the one case that may skip the build.
        (env / ".scprofile_lock").write_text(runner.lock_fingerprint(Kernel(d)))
        said = []
        try:
            runner.install(Kernel(d), pref, log=said.append)
        except Exception:                                     # the selftest step, not this check
            pass
        check("a matching stamp still skips the rebuild",
              any("matches the current lock" in x for x in said), str(said))

        # --force must REMOVE first. Installing again into a populated prefix leaves every package
        # the previous lock pulled and this one does not, in an environment whose fingerprint then
        # claims it came from this lock.
        said = []
        try:
            runner.install(Kernel(d), pref, force=True, log=said.append)
        except Exception:
            pass
        check("--force removes the old prefix", any("removing" in x for x in said), str(said))
        check("and nothing from the previous lock survives",
              not (env / "left_by_the_previous_lock").exists())

        # The removal is guarded by NAME, so a caller passing some other path cannot turn --force
        # into an rmtree of it.
        stray = td / "not-an-env"
        stray.mkdir()
        orig = runner.env_prefix
        runner.env_prefix = lambda name, prefix: stray
        try:
            runner.install(Kernel(d), pref, force=True)
            check("--force refuses a path it did not construct", False, "it removed it")
        except RuntimeError as e:
            check("--force refuses a path it did not construct", "refusing to remove" in str(e))
        finally:
            runner.env_prefix = orig
        check("and that path is untouched", stray.exists())


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
    test_r_lock_section()
    test_every_lock_is_validated_whatever_the_status()
    test_a_half_built_environment_is_not_a_built_one()
    test_unmet_names_the_fix()
    test_ordering()
    test_schedule()
    test_key_map_is_resolved()
    test_scaffold_cannot_produce_a_running_noop()
    test_validate_catches_what_got_through()
    test_wrapping_plugins_record_upstream()
    print()
    if FAILED:
        print(f"{len(FAILED)} FAILED: {', '.join(FAILED)}")
        return 1
    print("all contract checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
