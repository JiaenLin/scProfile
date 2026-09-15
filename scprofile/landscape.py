"""What EARLIER RUNS already hold, so a new run computes only what is genuinely new.

`resume` answers "what is left in THIS directory". It cannot help the ordinary case: a new run
gets a new run key, so every expensive result computed last week sits one directory away and is
recomputed from scratch. On a wrapped method that takes hours per unit, that is the difference
between iterating and not.

THE MAP IS A CHECKLIST, AND THE ONLY THING THAT MAKES IT SAFE IS THE KEY. A result is reusable
when everything that DETERMINES it is unchanged:

    the plugin, and its VERSION      different code, different result
    the unit                         the slice of the data it was computed over
    the input object                 identity, not merely the same path
    the parameters                   the config the plugin was given
    the keys                         which columns and layers it was pointed at

Anything else - the run key, the date, the machine, who launched it - is not part of the key and
must not be, or nothing is ever reusable.

WHAT THIS CANNOT VERIFY, SAID OUT LOUD. Runs record the input object's PATH and not a digest of
its contents, so a rebuilt object at the same path is indistinguishable from the original by
anything written down. This is the exact shape of failure this codebase has paid for before: a
pointer is only ever correct as of a date. So `identity()` records size and mtime where it can
reach the file, `reuse_key()` includes them, and every report says which parts of the key were
VERIFIED and which were taken on trust. A map that quietly assumed the input had not moved would
be worse than no map, because it would be believed.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

#: The fields that determine a result. Everything not here is deliberately excluded.
DETERMINING = ("plugin", "version", "unit", "input", "input_size", "input_mtime",
               "params", "keys", "host")

#: THE HOST'S OWN VERSION IS PART OF WHAT DETERMINES A RESULT, and leaving it out cost a whole
#: mechanism. The key covered the PLUGIN's version and nothing about the code that writes an
#: instance - so when the host gained a drawing audit that every panel was supposed to carry, the
#: next run adopted 14 of 15 instances from before it existed, the audit never ran, and the
#: station reading it reported "no panel carries an audit" on a tool that had just grown one.
#: Nothing was wrong except that reuse was too permissive, and nothing said so.
#:
#: SCOPED TO THE MODULES THAT WRITE AN INSTANCE, not to the whole tool. `_entry` invokes the
#: plugin, `plugin` is the emit surface it writes through, and `manifest` serialises what it
#: wrote. A change to the reporter or the CLI does not change an instance's contents - the
#: reporter redraws from the payload on every render - so folding the whole tree in would
#: invalidate every cached result on every commit and the reuse layer would be worth nothing.
#: THE RULE, so the next module is judged rather than remembered: a module belongs here if its
#: code can change what an INSTANCE contains. `figure.py` was left out on the first attempt and
#: the loop caught it within the hour - a fix to the drawing audit did not invalidate reuse, so
#: the next run adopted fourteen of fifteen instances carrying the flaw the fix removed, and the
#: station reported the same 154 false positives on a tool that had just stopped producing them.
#:
#: What is NOT here and must not be: the reporter and the panel modules. They draw at REPORT
#: time from the payload, on every render, so a change to them reaches an adopted instance
#: anyway - and folding them in would invalidate every cached result on every commit.
HOST_MODULES = ("_entry.py", "plugin.py", "manifest.py", "figure.py")


def host_version():
    """A digest of the host code that decides what an instance CONTAINS."""
    here = Path(__file__).resolve().parent
    h = hashlib.sha256()
    for name in HOST_MODULES:
        f = here / name
        h.update(name.encode())
        h.update(f.read_bytes() if f.is_file() else b"")
    return h.hexdigest()[:12]

REUSABLE, CHANGED, ABSENT = "reusable", "changed", "absent"


def _digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()


def identity(path):
    """(size, mtime_ns) for an input, or (None, None). NOT a content hash - see the docstring.

    Cheap enough to run on a multi-gigabyte object every time, which is what makes it get run.
    It catches the case that actually happens - the object was rebuilt - and it does not catch a
    rewrite that preserved both, which is why the caller is told what was checked.
    """
    try:
        st = Path(path).stat()
        return int(st.st_size), int(st.st_mtime_ns)
    except (OSError, TypeError):
        return None, None


def unit_record(rundir, plugin, unit=None):
    """One instance's identity and state, read from what the run wrote. None if not staged."""
    from . import resume

    d = resume.unit_dir(rundir, plugin, unit)
    ij, oj = d / "in.json", d / "out.json"
    if not ij.exists():
        return None
    try:
        inp = json.loads(ij.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    out = {}
    if oj.exists():
        try:
            out = json.loads(oj.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            out = {}
    h5 = inp.get("h5ad")
    size, mtime = identity(h5)
    st, why, n = resume.state(d)
    figs = sorted(p.name for p in (d / "figures").glob("*.png")) if (d / "figures").is_dir() \
        else []
    return {
        "run": Path(rundir).name, "run_dir": str(rundir), "dir": str(d),
        "plugin": plugin, "unit": unit,
        "version": out.get("version"), "contract": inp.get("contract"),
        "input": h5, "input_size": size, "input_mtime": mtime,
        "params": inp.get("params") or {}, "keys": inp.get("keys") or {},
        # WHAT THE INSTANCE ITSELF RECORDS, so a run made before a host change cannot be adopted
        # into one made after it. Absent on an instance written before this existed, which is
        # itself the right answer: its key differs from a current one and it is not reused.
        "host": inp.get("host_version"),
        "state": st, "why": why, "artifacts": n, "figures": figs,
    }


def reuse_key(rec):
    """The stable hash of everything that determines this result."""
    return _digest({k: rec.get(k) for k in DETERMINING})


def scan(root, plugins=None):
    """Every instance every run under `root` holds, newest run first.

    `root` is a directory of run directories - the shape a tool's stage output already has.
    """
    from . import resume

    r = Path(root)
    if not r.is_dir():
        return []
    runs = sorted((d for d in r.iterdir() if d.is_dir()), key=lambda d: d.name, reverse=True)
    out = []
    for run in runs:
        for plugin, unit in resume.discover(run):
            if plugins and plugin not in plugins:
                continue
            rec = unit_record(run, plugin, unit)
            if rec:
                rec["key"] = reuse_key(rec)
                out.append(rec)
    return out


def wanted(plugin, unit, *, version, h5ad, params=None, keys=None):
    """The identity a NEW run would have for one instance. Same shape, same key function."""
    size, mtime = identity(h5ad)
    rec = {"plugin": plugin, "unit": unit, "version": version, "input": str(h5ad),
           "host": host_version(),
           "input_size": size, "input_mtime": mtime,
           "params": params or {}, "keys": keys or {}}
    rec["key"] = reuse_key(rec)
    return rec


def match(want, have):
    """(state, source_record, reasons) - can this wanted instance reuse anything on disk?

    A near miss is far more useful than a bare no, so when the key differs the FIELDS that
    differ are named. "changed: version 0.3.1 -> 0.4.0" tells a reader they changed the code;
    "changed: input_mtime" tells them the object was rebuilt underneath them.
    """
    from . import resume

    cands = [h for h in have
             if h["plugin"] == want["plugin"] and h.get("unit") == want.get("unit")]
    if not cands:
        return ABSENT, None, ["no earlier run holds this instance"]
    from . import licence as _LC, runcard

    # EVERY CANDIDATE IS CONSIDERED, NEWEST FIRST, AND THE SEARCH DOES NOT STOP AT THE FIRST
    # UNTRUSTED ONE. It did, and the newest copy is often an IN-PROGRESS run - which has no card
    # yet, is therefore `unknown`, and so shadowed every completed older run behind it. Measured:
    # ten units whose determining fields were IDENTICAL to a finished earlier run were all
    # reported unusable because a run started minutes earlier had not finished writing.
    rejected = []
    for h in cands:
        if h["key"] != want["key"] or h["state"] not in resume.FINISHED:
            continue
        # A GRANTED LICENCE IS THE EVIDENCE, and it outranks a bare card verdict: it was
        # evaluated against the criteria, it hashes the products, and it survives a run that
        # never published a card. Without this the licence and the landscape disagreed - one
        # calling a result adoptable, the other calling it unknown.
        lic = _LC.read(h["run_dir"], h["plugin"], h.get("unit"))
        if lic:
            # A LICENCE THAT EXISTS IS DECISIVE, IN BOTH DIRECTIONS. Falling through to the run
            # card when a licence was REFUSED reused a result whose required figure was missing:
            # the licence said no, the card said `ok`, and the card won. The card is the run's
            # own impression; the licence is that impression PLUS integrity, completeness and
            # provenance checked against what is on disk. It cannot be the weaker authority.
            if lic.get("grade") not in _LC.ADOPTABLE:
                rejected.append(f"{h['run']}: licence REFUSED - "
                                + "; ".join(lic.get("refused_because") or ["no reason given"]))
                continue
            ok, bad = _LC.verify(lic)
            if ok:
                return REUSABLE, dict(h, verdict=lic["grade"], licensed=True), []
            rejected.append(f"{h['run']}: licence {lic['grade']!r} no longer verifies - "
                            f"{bad[0] if bad else 'artifact changed'}")
            continue
        v, why = runcard.verdict_for(h["run_dir"], h["plugin"], h.get("unit"))
        if v in runcard.TRUSTED:
            return REUSABLE, dict(h, verdict=v, licensed=False), []
        rejected.append(f"{h['run']}: the run that produced it calls it {v!r}"
                        + (" and it holds no licence" if v == runcard.UNKNOWN else ""))
    if rejected:
        return CHANGED, cands[0], rejected[:3]
    best = cands[0]
    diffs = []
    for f in DETERMINING:
        a, b = want.get(f), best.get(f)
        if a != b:
            diffs.append(f"{f}: {b!r} -> {a!r}" if f not in ("params", "keys")
                         else f"{f} differ")
    if not diffs:
        diffs = [f"the newest copy is {best['state']}: {best['why']}"]
    return CHANGED, best, diffs


def verified_fields(rec):
    """Which parts of the key were checked against the filesystem, and which were not.

    THE MAP MUST NOT OVERSTATE ITSELF. Size and mtime were read from the input just now; the
    rest came out of a file the run wrote and is trusted as written.
    """
    checked = [f for f in ("input_size", "input_mtime") if rec.get(f) is not None]
    return checked, [f for f in DETERMINING if f not in checked]


# ------------------------------------------------------------------------------ the forecast
def _spec_of_source(src):
    """The PLUGIN literal of a plugin's source, read and never imported."""
    import ast
    tree = ast.parse(src)
    node = next((n for n in tree.body if isinstance(n, ast.Assign)
                 and any(isinstance(t, ast.Name) and t.id == "PLUGIN" for t in n.targets)), None)
    return ast.literal_eval(node.value) if node is not None else {}


def _span_of(src, markers):
    """The lines between the two markers, or None when either is missing."""
    a, b = str(markers[0]), str(markers[1])
    lines = src.splitlines()
    ia = next((i for i, ln in enumerate(lines) if ln.startswith(a)), None)
    ib = next((i for i, ln in enumerate(lines) if ln.startswith(b)), None)
    if ia is None or ib is None or ib <= ia:
        return None
    return "\n".join(lines[ia:ib + 1])


def span_key(plugin_path, decl):
    """The key the host puts the unit's cache directory under: a digest of the declared
    inference span, or None when the plugin declares none (harness ADR-0026, runs F and G).

    LAST WRITER WON. The store held one object per parameter key; a run of another inference
    span re-inferred and overwrote the objects the previous run left, and the next run of the
    previous span - forecast HIT - paid the whole inference again and overwrote them back.
    Keyed by the span, versions of the inference coexist: a run of another span writes beside,
    never over, and what a run left is still there when its span comes back. The stamp inside
    the object still decides validity; this only decides where it lives.
    """
    if not isinstance(decl, dict) or not decl.get("span"):
        return None
    try:
        src = Path(plugin_path).read_text(encoding="utf-8")
    except OSError:
        return None
    span = _span_of(src, list(decl.get("span") or []))
    if span is None:
        return None
    import hashlib
    return hashlib.sha1(span.encode("utf-8")).hexdigest()[:10]


def cache_forecast(root, plugin, run):
    """{hit: True|False|None, reasons: [...], commit} - whether the next run of `plugin` from
    the tree at `root` will reuse the objects the run at `run` left, read from the declaration
    (harness ADR-0026).

    A plugin that keeps a fitted object declares under `cache` what keys it: `span`, the two
    marker lines of the source that determines the object, and `keyed_on`, the config parameters
    in the key. The forecast compares the working tree with the tool commit the run recorded -
    the span's text and each keyed parameter's effective value (what the run was given, else the
    default) - and says HIT or MISS with the reason. The environment (the wrapped tool's own
    version) is assumed the same; nothing here can read it.
    """
    import json as _json
    import subprocess
    root = Path(root)
    run = Path(run)
    f = root / "kernels" / f"{plugin}.py"
    out = {"hit": None, "reasons": [], "commit": None}
    if not f.is_file():
        out["reasons"].append(f"no plugin file at {f}")
        return out
    src_now = f.read_text(encoding="utf-8")
    try:
        spec_now = _spec_of_source(src_now)
    except (SyntaxError, ValueError) as e:
        out["reasons"].append(f"the plugin's declaration does not read: {e}")
        return out
    decl = spec_now.get("cache")
    if not isinstance(decl, dict) or not decl.get("span"):
        out["reasons"].append(f"{plugin} declares no `cache` (span, keyed_on), so nothing here "
                              f"can say whether the run will re-infer")
        return out
    try:
        commit = str(_json.loads((run / "report.json").read_text(encoding="utf-8")).get("tool_commit") or "")
    except (OSError, ValueError):
        commit = ""
    if not commit:
        out["reasons"].append(f"{run.name} records no tool_commit")
        return out
    out["commit"] = commit
    r = subprocess.run(["git", "-C", str(root), "show", f"{commit}:kernels/{plugin}.py"],
                       capture_output=True, text=True)
    if r.returncode:
        out["reasons"].append(f"the tree at {root} cannot show {commit}: {r.stderr.strip()[:120]}")
        return out
    src_then = r.stdout
    try:
        spec_then = _spec_of_source(src_then)
    except (SyntaxError, ValueError):
        spec_then = {}
    markers = list(decl.get("span") or [])
    span_now, span_then = _span_of(src_now, markers), _span_of(src_then, markers)
    if span_now is None:
        out["reasons"].append(f"the span markers {markers} are not both in the file now")
        return out
    reasons = []
    if span_then is None or span_now != span_then:
        import difflib
        n = sum(1 for ln in difflib.unified_diff((span_then or "").splitlines(),
                                                 span_now.splitlines(), n=0, lineterm="")
                if ln[:1] in "+-" and ln[:3] not in ("+++", "---"))
        reasons.append(f"the inference span changed since {commit} ({n} line(s) differ): every "
                       f"unit re-infers")
    # THE EFFECTIVE VALUE OF EACH KEYED PARAMETER: what the run was given, else the default.
    given = {}
    for inp in sorted((run / "kernels" / plugin).glob("*/in.json")):
        try:
            given = dict(_json.loads(inp.read_text(encoding="utf-8")).get("params") or {})
            break
        except (OSError, ValueError):
            continue

    def _effective(spec, key):
        if key in given:
            return given[key]
        c = ((spec.get("config") or {}).get(key) or {})
        return c.get("default") if isinstance(c, dict) else None
    for key in (decl.get("keyed_on") or []):
        then_, now_ = _effective(spec_then, key), _effective(spec_now, key)
        if then_ != now_:
            reasons.append(f"keyed parameter {key} {then_!r} -> {now_!r}: every unit re-infers")
    # RELATIVE TO THE RUN NAMED, NOT TO THE CACHE'S CONTENTS (harness ADR-0026, run F): nothing
    # here can read the store. The store keeps one object per span (`span_key`), so a run of
    # another span since the one named cannot have overwritten what it left: a HIT holds short
    # of the cache being cleared, and a MISS may still hit if a run since then wrote objects for
    # this span.
    out["hit"] = not reasons
    out["reasons"] = ([r + " - unless a run since then already wrote objects for this span"
                       for r in reasons]
                      or [f"the inference span and the keyed parameters are those of the run at "
                          f"{commit}; the saved objects are under this span's key and are reused "
                          f"unless the cache was cleared (assuming the same environment)"])
    return out


def format_forecast(plugin, fc):
    if fc.get("hit") is None:
        return f"  CACHE FORECAST for {plugin}: cannot say - " + "; ".join(fc.get("reasons") or [])
    word = "HIT" if fc["hit"] else "MISS"
    return f"  CACHE FORECAST for {plugin}: {word} - " + "; ".join(fc.get("reasons") or [])
