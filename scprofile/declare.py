"""The plugin declaration: its schema, its capabilities, and the checks both sides depend on.

TWO READERS, ONE DECLARATION. The BUILDER reads it to decide what to install and whether it can;
the MAINTAINER reads it to know what the plugin promises. Both need it checked rather than
trusted, and both need the SAME check - a builder that accepts what validate rejects is a builder
that installs something nobody can maintain.

Nothing here imports a plugin. A declaration is read from source, so a plugin pinned to numpy 1.23
is still listable by a host running numpy 2 - which is the ordinary case on a cluster and the
reason discovery must never execute plugin code.
"""
from __future__ import annotations

#: The contract version a plugin was written against. A host that meets a higher one REFUSES BY
#: NAME rather than calling it and failing somewhere inside - without this, the only way to
#: discover a contract change is a crash in a stranger's run.
API = 1

#: CAPABILITIES, NOT COLUMN NAMES AND NOT PLUGIN NAMES.
#:
#: A plugin says it needs `counts`; the host works out which layer of THIS object that is. A
#: plugin says it needs `ordering`; the host works out which plugin provides one. Neither
#: question belongs in a plugin, and answering them there is how a plugin learns one project or
#: one implementation.
#:
#: `resolve` says where the host looks. `data` capabilities come from the object, `design` from
#: the design table, `derived` from another plugin.
CAPABILITIES = {
    "counts":       {"resolve": "data",   "why": "integer counts. A count model handed "
                                                 "log-normalised values returns a plausible lie"},
    "lognorm":      {"resolve": "data",   "why": "log-normalised values"},
    "label":        {"resolve": "data",   "why": "a cell-type or cluster column"},
    "compartment":  {"resolve": "data",   "why": "a coarser grouping than label"},
    "sample":       {"resolve": "data",   "why": "the unit of replication"},
    "batch":        {"resolve": "data",   "why": "a technical grouping"},
    "embedding":    {"resolve": "data",   "why": "a cell embedding to compute neighbours on"},
    "spliced":      {"resolve": "data",   "why": "spliced counts from the aligner. These cannot "
                                                 "be derived later"},
    "unspliced":    {"resolve": "data",   "why": "unspliced counts from the aligner"},
    "organism":     {"resolve": "data",   "why": "the species. Some priors are published per "
                                                 "organism and return a small plausible table "
                                                 "for the wrong one rather than failing"},
    "design":       {"resolve": "design", "why": "a design table, for a contrast to exist"},
    "contrast":     {"resolve": "design", "why": "a testable factor: two levels, one of them "
                                                 "replicated"},
    "ordering":     {"resolve": "derived", "why": "a pseudotime or trajectory ordering, from "
                                                  "whichever plugin provides one"},
    "velocity":     {"resolve": "derived", "why": "a fitted velocity field"},
    "communication": {"resolve": "derived", "why": "a ligand-receptor table"},
    "activity":     {"resolve": "derived", "why": "per-cell regulatory or pathway activity"},
    "phase":        {"resolve": "derived", "why": "a cell-cycle phase call"},
}

_TYPES = {"int": int, "float": float, "str": str, "bool": bool, "list": list}


class DeclarationError(Exception):
    """The declaration is wrong. Said here, where it is cheap, not inside somebody's run."""


def check(spec, name="<plugin>"):
    """Every problem with a declaration, as a list. Empty means it is usable.

    Returns [(level, message)] - ERROR stops the builder, WARN is something a reader of the
    result would want to know. Deliberately returns ALL of them rather than raising on the first:
    a maintainer fixing one problem per run is a maintainer who stops running the check.
    """
    out = []
    api = spec.get("api")
    if api is None:
        out.append(("WARN", f"no `api` declared; assuming {API}. Declare it, so a future host "
                            f"can refuse this plugin by name instead of failing inside it."))
    elif api != API:
        out.append(("ERROR", f"declares api {api}; this host implements {API}. Refusing by name "
                             f"rather than calling it and failing somewhere inside."))

    if not spec.get("summary"):
        out.append(("ERROR", "no `summary`. It is what a user reads in the plan to decide "
                             "whether they want this at all."))
    if not spec.get("cannot_show"):
        out.append(("ERROR", "no `cannot_show`. A result whose limits were never written down "
                             "reads exactly as authoritative as one whose limits were thought "
                             "about."))

    inj = spec.get("inject") or {}
    if not isinstance(inj, dict):
        out.append(("ERROR", "`inject` must be {'required': [...], 'optional': [...]}"))
        inj = {}
    for kind in ("required", "optional"):
        for cap in inj.get(kind) or []:
            if cap not in CAPABILITIES:
                out.append(("ERROR", f"injects unknown capability {cap!r}. Known: "
                                     f"{', '.join(sorted(CAPABILITIES))}. A capability the host "
                                     f"does not resolve is one it can never satisfy."))
    for cap in spec.get("provides") or []:
        if cap not in CAPABILITIES:
            out.append(("ERROR", f"provides unknown capability {cap!r}"))
        elif CAPABILITIES[cap]["resolve"] != "derived":
            out.append(("ERROR", f"provides {cap!r}, which the host resolves from the object. A "
                                 f"plugin may only provide a derived capability."))

    cfg = spec.get("config") or {}
    for key, c in cfg.items():
        if not isinstance(c, dict) or "type" not in c:
            out.append(("ERROR", f"config {key!r} declares no type"))
            continue
        if c["type"] not in _TYPES:
            out.append(("ERROR", f"config {key!r} has unknown type {c['type']!r}; "
                                 f"one of {', '.join(sorted(_TYPES))}"))
        if "default" not in c:
            out.append(("WARN", f"config {key!r} has no default, so a run that does not set it "
                                f"has no defined behaviour"))
        if not c.get("help"):
            out.append(("WARN", f"config {key!r} has no help. A parameter nobody can explain is "
                                f"a parameter nobody should set."))

    env = spec.get("env")
    if env is not None:
        if not isinstance(env, dict) or not env.get("python"):
            out.append(("ERROR", "`env` declares no python version. A lock that does not pin the "
                                 "interpreter is not a lock - wheels are built per minor "
                                 "version."))
        for pin in (env or {}).get("pip") or []:
            if "==" not in pin and not pin.startswith(("http", "git+", "-")):
                out.append(("WARN", f"env pin {pin!r} is not exact. A lower bound is honest about "
                                    f"what a tool was written against and says nothing about "
                                    f"what it still works with."))

    w = spec.get("wraps") or {}
    if w and not (spec.get("upstream") or {}).get("docs"):
        out.append(("ERROR", "wraps a tool and records no `upstream.docs`. The record of having "
                             "READ the tool's documentation is the thing that catches a default "
                             "that is wrong rather than absent."))
    return out


def resolve_config(spec, given, name="<plugin>"):
    """Defaults applied, types checked, unknown keys refused. BEFORE the run, not inside it.

    A bad `--params` should fail in the second the plan is drawn, not an hour into a queue.
    """
    cfg = spec.get("config") or {}
    given = dict(given or {})
    unknown = sorted(set(given) - set(cfg))
    if unknown:
        raise DeclarationError(
            f"{name}: no such parameter(s) {unknown}. It declares: "
            f"{', '.join(sorted(cfg)) or 'none'}")
    out = {}
    for key, c in cfg.items():
        val = given.get(key, c.get("default"))
        if val is None and "default" not in c:
            raise DeclarationError(f"{name}: parameter {key!r} has no default and was not given")
        want = _TYPES.get(c.get("type"), object)
        if val is not None and not isinstance(val, want):
            try:
                val = want(val)
            except (TypeError, ValueError):
                raise DeclarationError(
                    f"{name}: parameter {key!r} wants {c['type']}, got {val!r}") from None
        for bound, cmp_, word in (("min", lambda a, b: a < b, "below"),
                                  ("max", lambda a, b: a > b, "above")):
            if bound in c and val is not None and cmp_(val, c[bound]):
                raise DeclarationError(
                    f"{name}: parameter {key!r} is {val}, {word} the declared {bound} "
                    f"{c[bound]}")
        out[key] = val
    return out
