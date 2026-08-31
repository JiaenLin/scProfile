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
    # TWO CAPABILITIES, BECAUSE THEY ARE TWO THINGS. The wording here was always right - "to
    # compute neighbours on" - and two consumers read it as "to draw on" anyway, which put a
    # 30-dimensional scANVI latent on the x and y axes of four panels. A representation is a
    # space where distances mean something; a layout is two coordinates made to be looked at.
    # For a variational latent they are not even close: its dimensions carry no variance
    # ordering, so the first two are two arbitrary coordinates and draw as a featureless ball.
    "embedding":    {"resolve": "data",   "why": "a cell embedding to compute neighbours on. "
                                                 "NOT a thing to draw - see `layout`"},
    "layout":       {"resolve": "data",   "why": "a TWO-column embedding to draw on, ideally "
                                                 "the one derived from the representation"},
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


def available(cap, *, keys=None, obs=(), obsm=(), layers=(), var=(),
              has_design=False, organism=None, derived=()):
    """Is this capability available here? ONE answer, for the planner and for the run.

    THE PLAN AND THE RUN MUST AGREE BY CONSTRUCTION. `inject` is the mechanism that replaced
    prerequisite checking inside plugins, and it was implemented at run time only: the entrypoint
    refused a plugin whose required capability was missing, and the PLANNER - whose whole job is
    to say that before a queue slot is spent - did not know `inject` existed. A plugin requiring
    an organism was planned as RUN on an object with no organism, and found out an hour later.

    So the question is answered here, once, and both callers ask it. A second implementation
    beside this one is the same bug wearing different clothes.
    """
    spec = CAPABILITIES.get(cap)
    if spec is None:
        return False
    how = spec["resolve"]
    if cap == "organism":
        return bool(organism)
    if how == "design":
        return bool(has_design)
    if how == "derived":
        return cap in set(derived or ())
    name = (keys or {}).get(cap)
    if not name:
        return False
    return any(name in set(where) for where in (obs, layers, obsm, var))


class DeclarationError(Exception):
    """The declaration is wrong. Said here, where it is cheap, not inside somebody's run."""


#: What a panel is FOR, and the only vocabulary the reporter understands. Three words, chosen
#: because they are the three questions a reader asks in this order and no other:
#:
#:   diagnostic   did this method's assumptions hold on THIS data? Read before the result,
#:                because it decides whether the result means anything.
#:   result       the answer the method was run for.
#:   comparison   the same question answered a second way. Needs another plugin, so it is the
#:                one kind of panel that can be absent because something ELSE did not run.
#:
#: THE REPORTER KNOWS THIS VOCABULARY AND NO FIGURE. It positions a panel by `shows`, captions it
#: by `question` and links it by `source`; it has no list of figure ids, no idea what any of them
#: draws, and gains nothing when a tenth plugin arrives with panels nobody has seen. A reporter
#: that knew the ids would be wrong about every plugin it had not been told about - the defect
#: `_who_produces` in kernels.py was written to record.
SHOWS = ("diagnostic", "result", "comparison")

#: The order the reporter lays them out in. Not alphabetical, not emission order: a reader must
#: meet the checks on the method before the number it produced.
SHOWS_ORDER = {k: i for i, k in enumerate(SHOWS)}


def figures_in(block) -> list:
    """The panels a `report` BLOCK declares, in declaration order. `[]` when it declares none.

    TWO READERS BECAUSE THERE ARE TWO SHAPES IN CIRCULATION, and conflating them is silent: the
    checker and the feedback loop hold a whole plugin spec, while the reporter is handed the block
    alone out of `report.json` - and a reader that took the wrong one returned `[]` for a plugin
    that had declared nine panels, which renders as a plugin that declared none.

    A plugin that declares nothing still runs and still reports; its figures are laid out in
    emission order as they were before this existed. That is deliberate and not a loophole: the
    declaration must be worth adding for a plugin written outside this repository, and a format
    that refuses a plugin for not having it yet is a format nobody adopts.
    """
    if not isinstance(block, dict):
        return []
    figs = block.get("figures")
    return [f for f in figs if isinstance(f, dict)] if isinstance(figs, list) else []


def report_figures(spec) -> list:
    """The panels a plugin's declaration carries. Takes the whole spec, not the block."""
    return figures_in((spec or {}).get("report"))


#: EVERY KEY THE `report` BLOCK MAY CARRY, stated once. It was a set literal inside the
#: unknown-key check, written before `unit_metrics` existed and never updated when it became a
#: REQUIREMENT - so `check` demanded the key of every per-unit plugin and then warned, on the
#: same declaration, that the key was unknown and "the reporter ignores them". Three shipped
#: plugins carried that warning permanently, and it was false: the reporter uses it.
#:
#: IT THEN HAPPENED AGAIN, WITH `unit_network`, AND THE GUARD DID NOT SEE IT. The guard compared
#: this tuple against the keys `_check_report` reads - two statements inside ONE module, both of
#: which I updated together. The consumer that drifted was the REPORTER, in another module, and
#: nothing compared the list against it. So `validate` told the author of the only two plugins
#: using the newest capability that "the reporter ignores them", while `report.py` read the key
#: and `check` carried a row asserting that it does. A checker and a reporter contradicting each
#: other about the same declaration, with the checker's message the wrong way round.
#:
#: The fix is structural rather than another entry: every consumer now reads the block through
#: `report_get`, which REFUSES a key that is not listed here, and the guard scans the whole
#: package for those calls. A new key cannot be consumed before it is declared, and a declared
#: key that nothing consumes is reported as dead.
#: `provides_evidence` and `comparison_stats` are read by the writing layer rather than by
#: the reporter, and were unregistered - so the checker warned about them on every run as
#: "a note to a human that reads as a setting", while the composer was in fact reading
#: both. A key that IS read must be declared, or the warning trains a reader to ignore
#: exactly the message that would matter for a key that is not.
REPORT_KEYS = ("figures", "reads_with", "unit_metrics", "unit_network",
               "provides_evidence", "comparison_stats")

#: THE COLUMNS A `unit_network` NAMES. `table`, `source`, `target` and `weight` are required and
#: are the network itself; `group` and `member` are optional and each earns further panels -
#: `group` the flow ranking and the role heatmap, `group` with `member` the decomposition. What a
#: plugin declares is what it gets, which is why an unrecognised key here is an ERROR and not a
#: warning: a misspelt column name removes panels in silence.
UNIT_NETWORK_KEYS = ("table", "source", "target", "weight", "group", "member",
                     "weight_scale",
                     # what the plugin CALLS its quantity, so the host can write about
                     # it without knowing what it is. Optional; "weight" without it.
                     "weight_name",
                     # WHICH UNIT METRIC IS THE NUMBER OF OBSERVATIONS THE FIT USED, and what to
                     # call them. A network's size rises with the observations behind it, so an
                     # arm assembled from more samples can carry a larger one with nothing
                     # biological behind it. Naming the metric lets the host put a per-observation
                     # scale beside the raw one without knowing what the method measures. Both
                     # optional; without them the host reports the raw scale only, as before.
                     "size_metric", "size_name")

#: What `weight_scale` may say. `per_object` means the weight was normalised within each unit -
#: a communication probability computed over the cells present is the usual case - so widths
#: compare WITHIN a panel and rank-order across panels. `absolute` means two units' values are on
#: one ruler. The host cannot tell them apart and the difference decides what a grid of arms is
#: allowed to claim, so it is declared, and the conservative reading is the default.
WEIGHT_SCALES = ("per_object", "absolute")


def report_get(spec, key, default=None):
    """One value out of a plugin's `report` block, by a key this module has declared.

    THE SINGLE DOOR. A consumer that reaches into the block directly can read a key the checker
    has never heard of, and the checker will then tell the plugin's author that the key is
    ignored - which is what happened to `unit_network`. Going through here makes that a
    programming error at the first call rather than a false warning in a maintainer's terminal.
    """
    if key not in REPORT_KEYS:
        raise KeyError(f"`report.{key}` is read but not declared in declare.REPORT_KEYS — "
                       f"add it there, or the checker will warn that the reporter ignores it")
    return (spec or {}).get(key, default)


def _check_report(spec, out) -> None:
    """The `report` block: a contract the reporter reads and the run is held to.

    Every rule here exists because the alternative is a page that looks complete. A panel with no
    question is a picture; a panel with no source is a picture a reader must take on trust; an
    optional panel with no `when_absent` leaves a gap that reads exactly like a panel nobody
    thought was needed.
    """
    block = spec.get("report")
    if block is None:
        out.append(("WARN", "declares no `report` block, so its page is a list of outputs and "
                            "whatever figures it happened to emit, in emission order. The "
                            "reporter cannot tell a diagnostic from a result, cannot say what a "
                            "panel is for, and cannot report one as MISSING - an absent figure "
                            "and a figure nobody wanted look the same."))
        return
    if not isinstance(block, dict):
        out.append(("ERROR", f"`report` must be a mapping, got {type(block).__name__}"))
        return

    figs = block.get("figures")
    if figs is None or (isinstance(figs, list) and not figs):
        out.append(("WARN", "declares a `report` block with no figures. A result with no panel "
                            "is a table, and a reader cannot check a table against the data it "
                            "came from."))
    elif not isinstance(figs, list):
        out.append(("ERROR", "`report.figures` must be a list of mappings"))
        figs = []
    else:
        seen = set()
        for i, f in enumerate(figs):
            at = f"report.figures[{i}]"
            if not isinstance(f, dict):
                out.append(("ERROR", f"{at} must be a mapping, got {type(f).__name__}"))
                continue
            fid = str(f.get("id") or "").strip()
            at = f"report.figures[{fid or i}]"
            if not fid:
                out.append(("ERROR", f"{at} declares no `id`. The id is what the reporter "
                                     f"positions, what `emit_figure` is called with, and what a "
                                     f"reader names when they refer to the panel."))
            elif fid in seen:
                out.append(("ERROR", f"{at} is declared twice. Two panels under one id cannot "
                                     f"both be reported present or absent."))
            else:
                seen.add(fid)
            if not str(f.get("question") or "").strip():
                out.append(("ERROR", f"{at} states no `question`. It is printed above the panel "
                                     f"so a reader knows what it is for before deciding whether "
                                     f"it answers them."))
            shows = f.get("shows")
            if shows not in SHOWS:
                out.append(("ERROR", f"{at} declares shows={shows!r}; it must be one of "
                                     f"{', '.join(SHOWS)}. The reporter orders a page by this and "
                                     f"by nothing else - a reader must meet the checks on the "
                                     f"method before the number it produced."))
            if not str(f.get("source") or "").strip():
                out.append(("ERROR", f"{at} names no `source` table. A figure whose numbers "
                                     f"cannot be opened is a figure a reader has to believe, and "
                                     f"several journals now require the source data beside the "
                                     f"panel."))
            if not f.get("required", True) and not str(f.get("when_absent") or "").strip():
                out.append(("WARN", f"{at} is optional and says nothing for the case where it is "
                                    f"absent. The reporter will print that it was not produced "
                                    f"and no reason, which reads as an oversight rather than as "
                                    f"a property of the data."))

    # A PAGE HAS A BUDGET AND A PLUGIN IS NOT THE ONLY THING SPENDING IT. The reporter adds its
    # own panels to any page whose plugin writes a per-cell column - the per-arm views, capped at
    # `BY_ARM_PANEL_CAP` - so a plugin's declared figures are not the page's figure count. One
    # shipped plugin declares 9 and its rendered page carries exactly 12, which is the standard's
    # cap: it passes with ZERO headroom, and nothing anywhere would have told its maintainer.
    #
    # Both numbers are imported from the modules that own them rather than restated here. The
    # restated version of this same fact is the defect two commits ago, where an allowed-key set
    # written before a key existed contradicted the check that required it. Imported lazily
    # because a declaration is read on interpreters that have nothing installed.
    if isinstance(figs, list) and figs and not spec.get("per_unit"):
        from .report import BY_ARM_PANEL_CAP
        from .standard import MAX_FIGURES
        budget = MAX_FIGURES - BY_ARM_PANEL_CAP
        if len(figs) > budget:
            out.append(("ERROR", f"declares {len(figs)} figures for one page. A page carries at "
                                 f"most {MAX_FIGURES} and the reporter adds up to "
                                 f"{BY_ARM_PANEL_CAP} per-arm panels of its own, so a cohort "
                                 f"plugin's budget is {budget}. Above it the page fails the exit "
                                 f"standard on every run, and the maintainer finds out after the "
                                 f"job rather than before it."))

    rw = block.get("reads_with")
    if rw is not None:
        if not isinstance(rw, list) or any(not isinstance(x, str) for x in rw):
            out.append(("ERROR", "`report.reads_with` must be a list of plugin names"))
        elif spec.get("name") and spec["name"] in rw:
            out.append(("ERROR", "`report.reads_with` names this plugin itself"))

    # `unit_network` IS WHAT EARNS THE HOST-DRAWN PANELS, so a typo in it costs a plugin every
    # one of them - silently, because a panel that cannot find its column simply is not drawn.
    # `member` was added after `contribution` was implemented and `members` is the obvious
    # slip; without this it would read as a plugin that chose not to declare one.
    net = block.get("unit_network")
    if net is not None:
        if not isinstance(net, dict):
            out.append(("ERROR", "`report.unit_network` must be a mapping"))
        else:
            missing = [k for k in ("table", "source", "target", "weight") if not net.get(k)]
            if missing:
                out.append(("ERROR", f"`report.unit_network` is missing {', '.join(missing)} — "
                                     f"without all four the host cannot read the network and "
                                     f"draws none of the panels a declaration earns"))
            _ws = net.get("weight_scale")
            if _ws is not None and str(_ws) not in WEIGHT_SCALES:
                out.append(("ERROR", f"`report.unit_network.weight_scale` is {_ws!r}; one of "
                                     f"{', '.join(WEIGHT_SCALES)}"))
            odd = sorted(set(net) - set(UNIT_NETWORK_KEYS))
            if odd:
                out.append(("ERROR", f"`report.unit_network` carries unknown key(s) "
                                     f"{', '.join(odd)} — a misspelt column name here removes "
                                     f"panels without any error, so it is refused rather than "
                                     f"warned about"))

    extra = sorted(set(block) - set(REPORT_KEYS))
    if extra:
        out.append(("WARN", f"`report` carries unknown key(s) {', '.join(extra)}. The reporter "
                            f"ignores them, so they are a note to a human that reads as a "
                            f"setting."))


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

    # MEMORY IS A SCHEDULING DIMENSION AND AN UNDECLARED ONE IS A GUESS. The allocator assumes a
    # conservative rate when this is absent and prints that it is assuming - but a job killed for
    # memory dies at the end of its longest step, with no partial result and an error naming the
    # plugin rather than the scheduler. WARN and not ERROR: a plugin that cannot yet state its
    # rate is still runnable, and blocking on it would stop people declaring anything at all.
    _ex = spec.get("executor") if isinstance(spec.get("executor"), dict) else {}
    if _ex.get("memory_gb_per_100k") is None and spec.get("memory_gb_per_100k") is None:
        out.append(("WARN", "no `memory_gb_per_100k`. The allocator schedules on memory as well "
                            "as cores and will assume a conservative rate for this plugin, which "
                            "either wastes memory or - if the guess is low - gets the job killed. "
                            "Measure it once on a real object and declare it."))

    if not spec.get("summary"):
        out.append(("ERROR", "no `summary`. It is what a user reads in the plan to decide "
                             "whether they want this at all."))

    # `design_aware` IS A CLAIM, AND IT IS CHECKED AGAINST THE OUTPUT THAT WOULD MAKE IT TRUE.
    #
    # It means "reports per arm without testing across the design". Two plugins declared it and
    # between them had fourteen panels, none of them about an arm - the flag was a sentence in a
    # declaration and nothing anywhere compared it with what the plugin produced. The host now
    # renders the per-arm view from any per-cell column a plugin writes, so the claim is
    # structurally possible exactly when there is such a column to split.
    if spec.get("design_aware") and not [q for q in (spec.get("produces") or [])
                                         if str(q).startswith("obs[")]:
        out.append(("ERROR", "declares `design_aware` - it reports per arm - and produces no "
                             "per-cell `obs[...]` column, so there is nothing the host can split "
                             "by an arm and nothing on its page will be about the design."))

    # A PER-UNIT PLUGIN MUST DECLARE WHAT MAKES ITS UNITS COMPARABLE.
    #
    # It runs separately on every unit and its page is that many single-unit reports in
    # sequence. Each panel is true and the question a cohort study asks - do the units agree? -
    # is answered nowhere, because the numbers never share an axis. Measured on a real cohort:
    # one plugin's per-unit count ran 8,194 to 38,895, a 4.7-fold range across the units of a
    # single tissue, and its page put every one of those numbers in a figure of its own.
    #
    # The host draws the comparison itself for any plugin that records the number, so this
    # declaration is the whole of what a plugin owes - and it is checked against what the run
    # emits, exactly as figures are, because a number nobody declared cannot be compared and a
    # declared number that never arrives leaves a gap that reads like nobody wanted one.
    if spec.get("per_unit"):
        ums = (spec.get("report") or {}).get("unit_metrics")
        if not ums:
            out.append(("ERROR", "runs per unit and declares no `report.unit_metrics`, so its "
                                 "units cannot be put on one axis and its page is N single-unit "
                                 "reports in sequence. Declare at least one scalar and record "
                                 "it with `ctx.metric(name, value)`."))
        elif not isinstance(ums, list):
            out.append(("ERROR", "`report.unit_metrics` must be a list of mappings"))
        else:
            for i, m in enumerate(ums):
                at = f"report.unit_metrics[{i}]"
                if not isinstance(m, dict):
                    out.append(("ERROR", f"{at} must be a mapping"))
                    continue
                if not str(m.get("id") or "").strip():
                    out.append(("ERROR", f"{at} declares no `id`; the id is the name passed to "
                                         f"`ctx.metric` and is how the two are matched"))
                if not str(m.get("question") or "").strip():
                    out.append(("ERROR", f"{at} declares no `question`. A number on a shared "
                                         f"axis with no question attached is a number a reader "
                                         f"must guess the meaning of."))
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

    req = spec.get("requires")
    if req is not None:
        if not isinstance(req, dict):
            out.append(("ERROR", "`requires` must be {'python': ..., 'packages': {...}}"))
        else:
            from . import resolve as _RS
            for label, s in ([("python", req.get("python"))]
                             + sorted((req.get("packages") or {}).items())):
                if not s:
                    continue
                try:
                    _RS.parse(s)
                except ValueError as e:
                    out.append(("ERROR", f"requires.{label}: {e}"))
            for field, want in (("packages", dict), ("conda", dict),
                                ("channels", list), ("r", list)):
                v = req.get(field)
                if v is not None and not isinstance(v, want):
                    out.append(("ERROR", f"requires.{field} must be a {want.__name__}"))
            if not (req.get("packages") or req.get("conda") or req.get("r")):
                out.append(("WARN", "`requires` names no packages, so it constrains only the "
                                    "interpreter"))
            # THE CONTRACT'S OWN DEPENDENCY, WHICH NOTHING DECLARED AND NOTHING CHECKED.
            # `_entry.py` reads the object with `anndata.read_h5ad` before a plugin sees
            # anything, so a python plugin whose environment has no anndata cannot run - and the
            # failure arrives as "this kernel's interpreter cannot read the object", which reads
            # as a problem with the OBJECT. Measured on PBS 677677: ten instances of one plugin
            # reported exactly that, and the cause was `No module named 'anndata'`.
            #
            # Only for a plugin that brings python packages. A requirement that is entirely
            # conda or entirely another language is not run through the python entrypoint.
            if req.get("packages") and "anndata" not in (req.get("packages") or {}):
                out.append(("ERROR",
                            "the requirement names no anndata, and the CONTRACT needs it. The "
                            "host reads the object with `anndata.read_h5ad` in `_entry.py` "
                            "before this plugin is called, so an environment without it cannot "
                            "run any plugin at all - and the failure surfaces as 'this kernel's "
                            "interpreter cannot read the object', which reads as a problem with "
                            "the object rather than with the environment."))
            if not req.get("python") and not (req.get("conda") or req.get("r")):
                out.append(("ERROR", "`requires` pins no python and names nothing outside pip. "
                                     "An environment has to be built at SOME interpreter version "
                                     "- wheels are built per minor version - and a requirement "
                                     "that names none cannot be built at all."))
            # A PLUGIN MAY SAY ITS PINS ARE DELIBERATE, ONCE. scenic genuinely needs an exact,
            # older, self-consistent stack - pySCENIC's dask handshake breaks on anything newer -
            # and nine identical warnings telling its maintainer to "see whether a range holds"
            # is nine pieces of advice that are wrong. Stating why is better than suppressing.
            deliberate = str(req.get("exact_pins_why") or "").strip()
            if deliberate and len(deliberate) < 30:
                out.append(("WARN", "exact_pins_why is too short to be a reason"))
            for name, s in sorted((req.get("packages") or {}).items()):
                if deliberate:
                    continue
                if str(s).startswith("==") and "," not in str(s):
                    out.append(("WARN", f"requires {name} {s} exactly. A pin says only THAT "
                                        f"version works, and where that is not true it forces an "
                                        f"environment nobody can share - see whether a range "
                                        f"holds."))
    if spec.get("env") is not None and req is not None:
        out.append(("ERROR", "declares both `requires` and `env`. `env` is the older, "
                             "fully-pinned shape; keep one, and `requires` is the one the builder "
                             "can resolve against other plugins."))

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

    _check_report(spec, out)

    # MATPLOTLIB IS A CONTRACT DEPENDENCY OF DRAWING, on the same terms as anndata is of reading.
    # `ctx.plot()` imports it inside the plugin's own interpreter, so a plugin that declares
    # panels and does not name it either fails at the first figure or works by accident because
    # it SHARES an environment with a plugin that does - which is how anndata went unnoticed on
    # three plugins until ten instances failed at once. Five of the nine declared it and four did
    # not, on the run that added figures to all of them.
    if report_figures(spec) and (spec.get("requires") or {}).get("packages"):
        if "matplotlib" not in spec["requires"]["packages"]:
            out.append(("ERROR", "declares figures in `report.figures` and does not require "
                                 "`matplotlib`. `ctx.plot()` imports it in this plugin's own "
                                 "interpreter; without it the first panel raises, or the plugin "
                                 "works only because another plugin in its environment named it."))

    w = spec.get("wraps") or {}
    if w and not (spec.get("upstream") or {}).get("docs"):
        out.append(("ERROR", "wraps a tool and records no `upstream.docs`. The record of having "
                             "READ the tool's documentation is the thing that catches a default "
                             "that is wrong rather than absent."))
    return out


def resolve_config(spec, given, name="<plugin>"):
    """Defaults applied, types checked, unknown keys refused. BEFORE the run, not inside it.

    A bad `--params` should fail in the second the plan is drawn, not an hour into a queue.

    TWO KINDS OF THING ARRIVE IN ONE DICT, and only one of them is a knob. A `config` key is
    something the USER sets. An INJECTED CAPABILITY is something the HOST hands the plugin
    because the plugin declared it can use one - a contrast decided from the design is the
    case here - and it reaches the plugin through the same `params` mapping. This validated
    the whole mapping as though it were all config, so the host could not deliver what the
    plugin had itself declared: the two plugins that read `ctx.params["contrast"]`, and whose
    own documentation says the host passes it there, refused the run outright with "no such
    parameter ['contrast']".

    Both halves were wrong and the second would have survived a fix to the first: `out` was
    built from `cfg` alone, so an injected value that got past the check would have been
    dropped without a word on its way to the plugin.
    """
    cfg = spec.get("config") or {}
    inj = spec.get("inject") or {}
    injected = ((set(inj.get("required") or []) | set(inj.get("optional") or []))
                if isinstance(inj, dict) else set())
    given = dict(given or {})
    unknown = sorted(set(given) - set(cfg) - injected)
    if unknown:
        raise DeclarationError(
            f"{name}: no such parameter(s) {unknown}. It declares: "
            f"{', '.join(sorted(cfg)) or 'none'}"
            + (f"; and can be injected: {', '.join(sorted(injected))}" if injected else ""))
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
    # CARRIED THROUGH, NOT TYPE-CHECKED against a config schema it was never described by. An
    # injected capability's shape is the host's contract with the plugin, not a user-facing
    # parameter with a type and bounds.
    for key in sorted((set(given) & injected) - set(cfg)):
        out[key] = given[key]
    return out
