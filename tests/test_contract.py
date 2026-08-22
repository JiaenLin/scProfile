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
import inspect
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
        needs_design=False, can_source_layers=False, name="fake", injects_required=[])
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
        needs_design=False, can_source_layers=False, name="x", injects_required=[])
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
    # cellchat is a ONE-FILE plugin now, and its R packages are declared in PLUGIN["requires"]
    # rather than in a lock.yml. The rule under test is unchanged - an R package must be pinned
    # to a commit or a version - so the test follows the shape and not the file.
    from scprofile.kernels import FileKernel
    k = FileKernel(root / "kernels" / "cellchat.py")
    from scprofile import resolve as _RS
    s = _RS.requirement(k)
    check("cellchat's requirement parses", bool(s), str(s))
    check("it declares R packages", bool(s.get("r")), str(s.get("r")))
    # The COUNT of conda pins was the old lock's CONTENT, not a rule, and asserting it made the
    # suite fail the moment the plugin declared its requirement instead of its installation.
    # A VERSION, with no operator. The renderer supplies the `=`, and a value carrying one of its
    # own produced `r-base==4.3` - which in conda's grammar is an exact version that may not
    # exist, where `=4.3` means 4.3.*.
    check("r-base is pinned to a version", bool(str(s["conda"].get("r-base", "")).strip()),
          str(s["conda"]))
    check("and the version carries no operator",
          not str(s["conda"].get("r-base", "")).startswith(("=", ">", "<")),
          str(s["conda"].get("r-base")))
    # Both FORMS must appear, and every entry must classify as one of them. Asserting a COUNT
    # here made the suite fail the moment a third pin was added for a real reason - a test that
    # breaks on correct change teaches people to edit tests rather than read them.
    kinds = [r_pin_kind(x) for x in s["r"]]
    check("every r: entry is one of the two exact forms", all(kinds), str(list(zip(s["r"], kinds))))
    check("at least one is a CRAN version", "cran" in kinds, str(kinds))
    check("at least one is a git commit", "git" in kinds, str(kinds))
    # An R lock pins r-base and NOT python. Demanding a python pin from an R lock is the format
    # asserting an assumption; r-base decides which binaries every r-* package resolves against.
    check("and r-base is what every r-* package resolves against", "r-base" in s["conda"])

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
    # THE TALLY WAS THE POINT ONLY WHILE PLUGINS WERE UNWRITTEN. Every plugin in the tree is now
    # built, so this asserted a state the project spent the day removing. What must still hold is
    # that a PLANNED plugin is representable and handled - tested against the mechanism, not
    # against the tree, or the suite would need one plugin left unwritten forever to keep passing.
    check("a planned plugin is still representable",
          "planned" in inspect.getsource(discover)
          or all(k.status == "built" for k in discover().values()),
          f"planned={planned}")


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


def test_a_plugin_is_launched_the_way_its_shape_requires(tmp):
    """A ONE-FILE PLUGIN HAS NO `main()`, so handing the file to an interpreter is a no-op.

    The runner built `[exe, kernel.path / kernel.entry, in.json]` for everything. For the
    directory shape that is a `run.py` with its own `main()` and it is right. For the one-file
    shape - the shape the format is FOR - `kernel.path` IS the plugin, so the interpreter
    imported it, defined `PLUGIN` and `run`, exited 0 and wrote nothing.

    Exit 0 with no `out.json` is the one failure mode the host cannot tell from a plugin that
    finished with no results, and it is what the first plugin supplied from outside this
    repository did on a real cohort: 0 seconds, an empty log, no traceback anywhere.

    So the SHAPE says how it is launched, and this asserts both shapes rather than the one that
    happened to work.
    """
    print("\nlaunch")
    from scprofile.kernels import FileKernel, Kernel, SHARED_ENTRY

    check("the shared entrypoint exists", SHARED_ENTRY.exists(), str(SHARED_ENTRY))

    one = tmp / "onefile.py"
    one.write_text("PLUGIN = {'api': 1, 'summary': 's', 'cannot_show': ['c']}\n"
                   "def run(ctx):\n    pass\n"
                   "def selftest(ctx):\n    pass\n", encoding="utf-8")
    fk = FileKernel(one)
    argv = fk.argv("PY", "IN")
    check("a one-file plugin goes THROUGH the shared entrypoint",
          argv[1] == str(SHARED_ENTRY), " ".join(argv))
    check("and the plugin is an argument to it, not the thing executed",
          argv[2] == str(one) and argv[0] == "PY" and argv[-1] == "IN", " ".join(argv))
    check("its selftest is read from the file, not from a neighbouring one",
          fk.has_selftest and fk.selftest_argv("PY")[2] == "--selftest")

    quiet = tmp / "quiet.py"
    quiet.write_text("PLUGIN = {'api': 1}\ndef run(ctx):\n    pass\n", encoding="utf-8")
    check("a one-file plugin with no selftest(ctx) says so",
          FileKernel(quiet).has_selftest is False)

    d = tmp / "dirshape"
    (d).mkdir(exist_ok=True)
    (d / "kernel.yml").write_text("name: dirshape\nsummary: s\n", encoding="utf-8")
    (d / "run.py").write_text("", encoding="utf-8")
    (d / "selftest.py").write_text("", encoding="utf-8")
    dk = Kernel(d)
    check("the directory shape still runs its own entry directly",
          dk.argv("PY", "IN") == ["PY", str(d / "run.py"), "IN"])
    check("and its selftest is still the neighbouring file",
          dk.has_selftest and dk.selftest_argv("PY") == ["PY", str(d / "selftest.py")])

    # EVERY SHAPE ANSWERS. A shape added later that does not is a shape the runner would have to
    # learn about, which is the arrangement this replaced.
    for name, k in sorted(discover().items()):
        check(f"{name} answers argv()", isinstance(k.argv("PY", "IN"), list) and
              len(k.argv("PY", "IN")) >= 3)


def test_every_data_capability_can_actually_be_delivered():
    """A capability the host RESOLVES but never puts in `in.json` is a capability nothing has.

    `inject: {required: ["lognorm"]}` is checked against `keys`, and `keys` came from detection,
    where the roles are called `lognorm_layer` and `counts_layer`. The host therefore detected the
    layer, printed it, planned against it - and wrote a manifest with no `lognorm` in it. A plugin
    requiring it was refused a capability the object had; `ctx.X` fell back to `.X` and said
    nothing; `ctx.counts()` returned None on an object with a counts layer.

    The names are two vocabularies on purpose. This asserts the bridge between them exists for
    every data capability, rather than for the ones somebody remembered.
    """
    print("\ncapability delivery")
    from scprofile import inputs
    from scprofile.declare import CAPABILITIES

    detected = {r: (f"col_{r}", "detected") for r in inputs.CANDIDATES}
    km = inputs.capability_keys(detected)
    for cap, spec in sorted(CAPABILITIES.items()):
        if spec["resolve"] != "data" or cap in ("organism", "spliced", "unspliced"):
            continue
        check(f"{cap!r} is deliverable", cap in km,
              f"detection produces {sorted(detected)}; nothing maps to {cap!r}")

    check("an alias does not overwrite a real detection",
          inputs.capability_keys({"counts_layer": "raw", "counts": "counts"})["counts"]
          == "counts")
    check("a role detected as empty is dropped, not delivered as null",
          "label" not in inputs.capability_keys({"label": (None, "absent")}))


def test_the_builder_builds_what_the_resolver_resolved():
    """An environment shared by four plugins was built from ONE of their locks.

    Resolution decided WHERE the environment goes; the plugin's own `lock.yml` still decided what
    went into it. So the first member built a directory whose content-addressed name claims to
    satisfy four requirements, and the other three found something that looked finished and did
    not contain their packages - with a stamp saying it was current.

    Every check here is on the SPEC the builder would hand a package manager, because that is the
    artefact the defect lived in and no unit test looked at it.
    """
    print("\nthe builder builds the group, not the plugin")
    from scprofile import resolve as RS
    from scprofile import runner
    ks = discover()
    groups = RS.group_by_compatibility(list(ks.values()))
    shared = [g for g in groups if len(g.members) > 1]
    check("the shipped set resolves to at least one SHARED environment", bool(shared),
          str([(g.name, g.members) for g in groups]))
    if not shared:
        return
    g = shared[0]
    spec = runner.build_spec(g)
    check("the resolved python is a VERSION, not a constraint",
          bool(spec["python"]) and "," not in spec["python"] and ">" not in spec["python"],
          str(spec["python"]))
    pips = {x.split("=")[0].split(">")[0].split("<")[0] for x in spec["pip"]}
    for m in g.members:
        req = RS.requirement(ks[m])
        missing = sorted(set(req["packages"]) - pips)
        check(f"every package {m} requires is in the build", not missing, str(missing))
        cmissing = sorted(set(req["conda"]) - {x.split("=")[0] for x in spec["conda"]})
        check(f"and every conda package {m} requires", not cmissing, str(cmissing))
    # A conda match-spec is not a pip specifier. `petsc4py=3.20` means 3.20.*; rewriting it as
    # `==3.20` asks for a version that does not exist, and the build fails on a package the
    # plugin pinned correctly.
    for item in spec["conda"]:
        check(f"conda spec {item!r} is carried verbatim", "==" not in item, item)
    for m in ("cellchat", "scenic"):
        if m in ks:
            gm = [x for x in groups if m in x.members]
            check(f"{m} takes part in resolution", len(gm) == 1,
                  "a plugin that needs an environment and is invisible to the resolver gets a "
                  "private path nobody planned")


def test_an_environment_is_found_where_it_was_resolved_to():
    """`env_state` read the per-plugin path alone, so a SHARED environment read as `missing`.

    Built, stamped and proved - and `doctor` said MISSING, `plan` said NO ENVIRONMENT, and
    `install` refused it as a half-built directory belonging to somebody else. One bug: two
    functions in one file disagreeing about where a plugin's interpreter lives.
    """
    print("\nan installed environment is found where resolution put it")
    from scprofile import resolve as RS
    from scprofile import runner
    ks = discover()
    shared = [g for g in RS.group_by_compatibility(list(ks.values())) if len(g.members) > 1]
    if not shared:
        check("a shared group exists to test", False)
        return
    g = shared[0]
    with tempfile.TemporaryDirectory() as td:
        pref = Path(td)
        k = ks[g.members[0]]
        state, why, _fix = runner.env_state(k, pref)
        check("nothing built yet reads as missing", state == "missing", f"{state}: {why}")
        env = pref / g.name
        (env / "bin").mkdir(parents=True)
        (env / "bin" / "python").write_text("#!/bin/sh\n")
        (env / ".scprofile_lock").write_text(runner.env_fingerprint(k, g))
        for m in g.members:
            state, why, _fix = runner.env_state(ks[m], pref)
            check(f"{m} finds the shared environment", state == "installed", f"{state}: {why}")
        check("and is told who it shares with",
              "shared with" in runner.env_state(ks[g.members[0]], pref)[1],
              runner.env_state(ks[g.members[0]], pref)[1])
        # The stamp is the one thing a directory cannot say: that the build reached its last act.
        (env / ".scprofile_lock").unlink()
        state, why, fix = runner.env_state(ks[g.members[0]], pref)
        check("a stampless shared environment is stale, not installed", state == "stale", why)
        check("and the fix names --force", "--force" in fix, fix)

        # THE SEARCH AND THE SPECIFIC DIRECTORY ARE DIFFERENT QUESTIONS. A half-built group
        # directory has no interpreter, so the search walks past it to an older per-plugin
        # environment and answers `installed` - and `install`, reading that, skipped the build it
        # was about to do and proved the old environment instead.
        import shutil as _sh
        _sh.rmtree(env)
        k = ks[g.members[0]]
        old_env = runner.env_prefix(k.name, pref)
        (old_env / "bin").mkdir(parents=True)
        (old_env / "bin" / "python").write_text("#!/bin/sh\n")
        (old_env / ".scprofile_lock").write_text(runner.lock_fingerprint(k))
        (pref / g.name).mkdir(parents=True)            # started, never finished
        check("the search still finds the usable interpreter",
              runner.env_state(k, pref)[0] in ("installed", "stale"),
              str(runner.env_state(k, pref)))
        check("but the half-built group directory is missing when asked about DIRECTLY",
              runner.state_at(pref / g.name, k, g, pref)[0] == "missing",
              str(runner.state_at(pref / g.name, k, g, pref)))


def test_install_does_not_demand_a_lock_from_a_plugin_that_declares_a_requirement():
    """A one-file plugin declaring `requires` has no `lock.yml`, and could not be installed.

    `install` looked for `kernel.path / "lock.yml"`, which for the one-file shape is a path
    INSIDE a file - so the whole `requires` shape, the shape the layering was corrected to, had
    no build path at all. The plugin was listable, plannable and unbuildable.
    """
    print("\ninstalling a plugin that declares a requirement rather than a lock")
    from scprofile import runner
    ks = discover()
    one_file = [k for k in ks.values() if k.spec.get("requires") and not k.path.is_dir()]
    check("the shipped set has a one-file plugin with a requirement", bool(one_file),
          str(sorted(ks)))
    if not one_file:
        return
    k = one_file[0]
    check(f"{k.name} ships no lock.yml", not (k.path / "lock.yml").exists())
    said = []
    with tempfile.TemporaryDirectory() as td:
        runner.install(k, Path(td), dry_run=True, log=said.append)
    txt = "\n".join(said)
    check("install resolves it rather than refusing", "environment scprofile-env-" in txt, txt)
    check("and names every plugin the environment is shared by", "shared by:" in txt, txt)
    check("and every member's selftest is what would prove it",
          "selftests that would run:" in txt, txt)
    check("and it builds NOTHING on a dry run", "nothing was built" in txt, txt)


def test_a_required_capability_is_checked_before_the_run_not_inside_it():
    """`inject` gated the RUN and was invisible to the PLAN.

    The entrypoint refuses a plugin whose required capability is missing - correctly - and the
    planner, whose entire job is to say that before a queue slot is spent, did not know `inject`
    existed. A plugin requiring an organism was planned RUN against an object with none.

    Both now ask `declare.available`, so they cannot disagree.
    """
    print("\na required capability reaches the planner")
    from scprofile import declare as D
    from scprofile.kernels import unmet
    ks = discover()
    withreq = [k for k in ks.values() if k.injects_required]
    check("a shipped plugin declares required capabilities", bool(withreq),
          str({n: k.injects_required for n, k in ks.items()}))
    if not withreq:
        return
    k = sorted(withreq, key=lambda x: x.name)[0]
    probs = unmet(k, obs=set(), obsm=set(), layers=set(), ran=set(), keys={}, organism=None)
    check(f"{k.name} is blocked when its capabilities are absent", bool(probs), str(probs))
    check("and each problem names the capability and a fix",
          all("capability" in p and "Fix:" in p for p in probs), " | ".join(probs))
    # Satisfied, it must not be blocked - a check that always fires is a check nobody keeps.
    keys = {c: c for c in k.injects_required}
    probs = unmet(k, obs=set(), obsm=set(), layers=set(k.injects_required), ran=set(),
                  keys=keys, organism="mouse", has_design=True,
                  derived=[c for c in k.injects_required])
    check("and not blocked once they are available", not probs, str(probs))
    check("organism resolves from the ORGANISM, never from a column",
          D.available("organism", keys={"organism": "x"}, obs={"x"}) is False)
    check("a derived capability resolves from what another plugin provides",
          D.available("activity", derived=["activity"]) is True)
    check("and an unknown capability is never available",
          D.available("no_such_capability", keys={"no_such_capability": "x"},
                      obs={"x"}) is False)


def test_the_compatibility_copy_is_a_record_and_a_cache():
    """3.14 GB was left beside every run and called "a legitimate cached working file, reusable".

    It was neither. Nothing ever read it again - every run into the same `--out` rewrote it from
    scratch - and nothing named it, so it sat beside an output directory as an unidentifiable
    3 GB file. Both halves of the description are now true: a receipt makes it reusable, and
    `report.json` names it as what the plugins ACTUALLY read, which is not the object passed in.
    """
    print("\nthe compatibility copy")
    from scprofile import compat
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        src = td / "obj.h5ad"
        src.write_bytes(b"x" * 100)
        copy = td / "input_for_kernels.h5ad"
        check("no copy, no reuse", not compat.reusable(copy, src))
        copy.write_bytes(b"y" * 10)
        check("a copy with NO receipt is not reused", not compat.reusable(copy, src),
              "a run killed mid-conversion leaves a file that opens like a finished one")
        copy.with_suffix(copy.suffix + ".from").write_text(compat.receipt(src))
        check("a copy whose receipt matches this source is reused",
              compat.reusable(copy, src))
        src.write_bytes(b"x" * 200)                       # the object changed underneath it
        check("and is NOT reused once the source changes", not compat.reusable(copy, src),
              "a wrong copy is a run against a different object")
        check("a receipt names the source, its size and its mtime",
              len(compat.receipt(src).strip().splitlines()) == 3, compat.receipt(src))
        check("and a missing source has no receipt at all",
              compat.receipt(td / "gone.h5ad") == "")
    import inspect
    from scprofile import cli as _c
    check("the run names the copy in its own record",
          "input_read_by_kernels" in inspect.getsource(_c._run),
          "3 GB nobody can identify beside an output directory is debris, not a record")


def test_an_array_carries_its_barcodes():
    """"An array carries no barcodes" was a gap the host had left, stated as a fact about arrays.

    The host EXCLUDES cells with NaN in a computed embedding from every plugin. A plugin handed
    98,627 of an object's 100,713 cells therefore returned an array of 98,627 rows, and the merge
    refused it for not covering 100,713 - refused the plugin for returning exactly the cells the
    host had given it. Nothing in that is specific to one plugin: it is every plugin that emits
    an array on an object with a withheld cell in it.

    The barcodes are `ctx.adata.obs_names`, and `emit_obsm` is the host's own code.
    """
    print("\nan emitted array carries the barcodes its rows belong to")
    import numpy as np
    from scprofile import merge

    class _Idx(list):
        is_unique = True
        def astype(self, _):
            return self
        def intersection(self, other):
            o = set(other)
            return [x for x in self if x in o]
        def __getitem__(self, k):
            v = list.__getitem__(self, k)
            return _Idx(v) if isinstance(k, slice) else v

    class _AD:
        def __init__(self, bcs):
            self.obs_names = _Idx(bcs)
            self.n_obs = len(bcs)
            self.obs, self.obsm, self.layers = {}, {}, {}

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        (td / "arrays").mkdir()
        # The plugin saw three of the object's four cells - the fourth was withheld upstream.
        np.save(td / "arrays" / "X_a.npy", np.arange(6, dtype="float32").reshape(3, 2))
        check("no sidecar, no barcodes", merge._array_barcodes(td / "arrays" / "X_a.npy") is None)
        A = _AD(["c0", "c1", "c2", "c3"])
        try:
            merge.merge_one(A, td, {"kernel": "P", "obsm": {"X_a": "arrays/X_a.npy"}})
            check("without barcodes a short array is still refused", False, "it was accepted")
        except merge.MergeError as e:
            check("without barcodes a short array is still refused", True)
            check("and the refusal names the remedy", "emit_obsm" in str(e), str(e))

        (td / "arrays" / "X_a.barcodes.txt").write_text("c0\nc2\nc3\n")
        check("the sidecar is found beside the array",
              merge._array_barcodes(td / "arrays" / "X_a.npy") == ["c0", "c2", "c3"])
        said = []
        A = _AD(["c0", "c1", "c2", "c3"])
        got = merge.merge_one(A, td, {"kernel": "P", "obsm": {"X_a": "arrays/X_a.npy"}},
                              log=said.append)
        check("with barcodes it merges", got["obsm"] == ["X_a"], str(got))
        arr = A.obsm["X_a"]
        check("and every row lands where its barcode says", arr.shape == (4, 2), str(arr.shape))
        check("c0 keeps its own row", list(arr[0]) == [0.0, 1.0], str(arr[0]))
        check("c2 is the array's SECOND row, not the object's second cell",
              list(arr[2]) == [2.0, 3.0], str(arr[2]))
        check("the cell the plugin never saw is NaN, not somebody else's value",
              bool(np.isnan(arr[1]).all()), str(arr[1]))
        check("and the coverage is said out loud",
              any("3 of 4 cells covered" in x for x in said), str(said))

        # Barcodes that are not this object's are not a coverage gap, they are a different object.
        (td / "arrays" / "X_a.barcodes.txt").write_text("z0\nz1\nz2\n")
        try:
            merge.merge_one(_AD(["c0", "c1", "c2", "c3"]), td,
                            {"kernel": "P", "obsm": {"X_a": "arrays/X_a.npy"}})
            check("barcodes from another object are refused", False, "it was accepted")
        except merge.MergeError as e:
            check("barcodes from another object are refused", "not the same cells" in str(e),
                  str(e))
        # THE SAME GAP ONE SLOT OVER. A layer from a plugin handed fewer cells is refused by a
        # shape check for exactly the reason obsm was; the GENE axis still has to match, because
        # nothing beside the array names its columns and the host never subsets var.
        np.save(td / "arrays" / "layer_L.npy", np.arange(6, dtype="float32").reshape(3, 2))
        (td / "arrays" / "layer_L.barcodes.txt").write_text("c0\nc2\nc3\n")

        class _AD2(_AD):
            def __init__(self, bcs, n_vars):
                super().__init__(bcs)
                self.n_vars = n_vars
                self.shape = (len(bcs), n_vars)

        A = _AD2(["c0", "c1", "c2", "c3"], 2)
        got = merge.merge_one(A, td, {"kernel": "P", "layers": {"L": "arrays/layer_L.npy"}})
        check("a layer merges by barcode too", got["layers"] == ["L"], str(got))
        check("with NaN for the cell the plugin never saw",
              bool(np.isnan(A.layers["L"][1]).all()), str(A.layers["L"]))
        try:
            merge.merge_one(_AD2(["c0", "c1", "c2", "c3"], 5), td,
                            {"kernel": "P", "layers": {"L": "arrays/layer_L.npy"}})
            check("a layer with the wrong GENE axis is refused", False)
        except merge.MergeError as e:
            check("a layer with the wrong GENE axis is refused", "gene axis" in str(e), str(e))
        (td / "arrays" / "layer_L.barcodes.txt").unlink()

        # An index that disagrees with its own array says nothing about any cell.
        (td / "arrays" / "X_a.barcodes.txt").write_text("c0\nc1\n")
        try:
            merge.merge_one(_AD(["c0", "c1", "c2", "c3"]), td,
                            {"kernel": "P", "obsm": {"X_a": "arrays/X_a.npy"}})
            check("an index disagreeing with its array is refused", False)
        except merge.MergeError as e:
            check("an index disagreeing with its array is refused",
                  "disagree" in str(e), str(e))


def test_the_host_answers_the_sentinel_question_once():
    """Two of the first two plugins that grouped by label reported a sentinel as a population.

    That is a statement about the affordance, not about two authors. `ctx.obs("label")` hands back
    the raw column, and using it correctly means remembering, unprompted, that some of its values
    are the annotator DECLINING to call a cell type - and a mean activity or a silhouette for
    `UNRESOLVED` reads in a table exactly like a cell type that scored badly. Measured twice on
    real cohorts: PBS 676943 (silhouette) and PBS 677295 (decoupler).

    `ctx.populations()` is the host answering it once, with the caveat attached so a plugin
    cannot mask correctly and then forget to say it did.
    """
    print("\nthe host answers the sentinel question once, for every plugin")
    import numpy as np
    from scprofile.plugin import Context

    class _Col(list):
        def astype(self, _):
            return self

    class _AD:
        def __init__(self, labels):
            self.obs = {"cell_type": _Col(labels)}
            self.n_obs = len(labels)
            self.obs_names = _Col([f"c{i}" for i in range(len(labels))])
            self.obsm, self.layers = {}, {}
            self.X = None

    with tempfile.TemporaryDirectory() as td:
        A = _AD(["T", "B", "UNRESOLVED", "T", "EXCLUDED"])
        ctx = Context(A, keys={"label": "cell_type"}, out=td,
                      sentinels=("UNRESOLVED", "EXCLUDED"), log=lambda *_a: None)
        mask, groups = ctx.populations()
        check("sentinels are out of the grouping", list(groups) == ["T", "B", "T"], str(groups))
        check("and the mask says which cells they were",
              list(mask) == [True, True, False, True, False], str(mask))
        check("the caveat is added by the HOST, not by the plugin",
              any("NOT summarised as a population" in c for c in ctx.caveats), str(ctx.caveats))
        n_caveats = len(ctx.caveats)
        ctx.populations()
        check("and said once however many tables a plugin writes",
              len(ctx.caveats) == n_caveats, str(ctx.caveats))

        # No sentinels present: nothing is set aside and nothing is claimed to have been.
        ctx2 = Context(_AD(["T", "B"]), keys={"label": "cell_type"}, out=td,
                       sentinels=("UNRESOLVED",), log=lambda *_a: None)
        mask2, groups2 = ctx2.populations()
        check("a clean object gets no caveat", not ctx2.caveats, str(ctx2.caveats))
        check("and every cell is in the grouping", bool(np.asarray(mask2).all()))

        # No label column at all: callable unconditionally, and it says so by returning None.
        ctx3 = Context(_AD(["T"]), keys={}, out=td, log=lambda *_a: None)
        mask3, groups3 = ctx3.populations()
        check("no label column returns None rather than raising", groups3 is None)
        check("and an all-True mask", bool(np.asarray(mask3).all()))

    # And the bundled plugin that got it wrong now uses it.
    import inspect
    ks = discover()
    src = inspect.getsource(_load_module(ks["decoupler"].path).run)
    check("decoupler groups through ctx.populations()", "ctx.populations()" in src, src[:200])


def _load_module(path):
    import importlib.util
    spec = importlib.util.spec_from_file_location(f"_t_{Path(path).stem}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        test_contract_roundtrip(tmp)
        test_old_kernel_reads_new_input(tmp)
        test_objects_slot(tmp)
        test_captioned_figures(tmp)
        test_declared_but_absent_is_refused(tmp)
        test_a_plugin_is_launched_the_way_its_shape_requires(tmp)
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
    test_every_data_capability_can_actually_be_delivered()
    test_scaffold_cannot_produce_a_running_noop()
    test_validate_catches_what_got_through()
    test_wrapping_plugins_record_upstream()
    test_the_builder_builds_what_the_resolver_resolved()
    test_an_environment_is_found_where_it_was_resolved_to()
    test_install_does_not_demand_a_lock_from_a_plugin_that_declares_a_requirement()
    test_a_required_capability_is_checked_before_the_run_not_inside_it()
    test_the_compatibility_copy_is_a_record_and_a_cache()
    test_an_array_carries_its_barcodes()
    test_the_host_answers_the_sentinel_question_once()
    print()
    if FAILED:
        print(f"{len(FAILED)} FAILED: {', '.join(FAILED)}")
        return 1
    print("all contract checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
