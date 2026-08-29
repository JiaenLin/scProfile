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
               "params", "keys")

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
