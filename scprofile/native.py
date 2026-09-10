"""Every plot the wrapped tool ships must be USED or ACCOUNTED FOR, and the reasons are a closed set.

WHY THIS EXISTS. Asked which of CellChat's 29 plotting functions the plugin used, the answer was
ONE - and only for its numbers. The other 28 were explained away with four reasons, three of
which are not reasons at all:

    "reimplemented in Python"     - the instruction was to use the tool's own plot
    "never considered"            - not a reason, an omission wearing one
    "dependency missing"          - a package that is one install away is not a decision
    "not applicable to this assay"- the only valid one of the four

Prose cannot stop that: a free-text field accepts any sentence, and the three bad answers read
as fine until someone counts them. So the vocabulary is CLOSED. A plugin may skip an upstream
plot for exactly three reasons, each of which demands evidence that can be checked, and the three
excuses above are rejected BY NAME with the remedy attached.

THE DEFAULT IS USE IT. A reimplementation is legitimate only as `superseded_by_design`, which
requires naming the panel that replaces it AND the specific defect in the upstream encoding it
corrects - so the reimplementation is a documented improvement rather than an accident of what
was importable.

Nothing here knows what tool is being wrapped. The inventory is the plugin's, measured from its
own environment; this module only holds the vocabulary and the accounting.
"""

#: The only reasons an upstream plot may go unused, and what each must supply to be believed.
VALID = {
    "not_applicable": (
        "the data cannot support this plot at all",
        ("evidence",),
        "Say what is absent - a modality, a coordinate system, a layer - and how that was "
        "established. `netVisual_spatial` on a dataset with no coordinates is the shape of this."),
    "superseded_by_design": (
        "a panel we designed replaces it, and corrects a named defect in the upstream encoding",
        ("panel", "defect"),
        "Name the panel that replaces it and the DEFECT it corrects. 'Ours is nicer' is not a "
        "defect; 'the upstream panel scales each facet to its own maximum, so widths are not "
        "comparable across a grid' is."),
    "duplicate_of": (
        "another upstream function already used produces the same figure",
        ("same_as",),
        "Name the function actually called. Two entry points to one plot is a property of the "
        "upstream API, not a decision by this plugin."),
}

#: Reasons that are NOT reasons, with what to do instead. Rejected by name so the message lands
#: on the person writing the declaration rather than in a review months later.
REJECTED = {
    "reimplemented": (
        "The instruction is to use the wrapped tool's own plot. If the reimplementation corrects "
        "a real defect, declare `superseded_by_design` and NAME the defect; if it does not, "
        "delete it and call the upstream function."),
    "not_considered": (
        "An omission is not a reason. Either call it, or establish one of the three valid "
        "reasons for not calling it."),
    "dependency_missing": (
        "A package one install away is not a design decision. Add it to the plugin's own "
        "requirement, or - if it genuinely cannot be installed - say why under `not_applicable` "
        "with the failure recorded."),
    "too_slow": (
        "Cost is a scheduling problem, not a reason to omit evidence. Declare its cost and let "
        "the planner decide."),
    "not_useful": (
        "Whether a figure is useful is the reader's judgement, not the wrapper's. If it cannot "
        "be read, that is `superseded_by_design` with the defect named."),
}


class Unaccounted(Exception):
    """An upstream plot is neither used nor validly skipped."""


def account(inventory, declared):
    """Check every upstream plot is used or validly skipped. Returns (used, skipped, problems).

    `inventory`  the plotting functions the wrapped tool exports, measured from its environment.
    `declared`   {function: {"use": <where>} | {"skip": <reason>, ...evidence}}

    A function missing from `declared` is a problem, not a silent pass: the accounting must be
    exhaustive or it is a sample of the ones somebody remembered.
    """
    used, skipped, problems = {}, {}, []
    for fn in sorted(inventory):
        d = (declared or {}).get(fn)
        if not d:
            problems.append((fn, "UNACCOUNTED: neither used nor skipped. Call it, or give one "
                                 "of: " + ", ".join(sorted(VALID))))
            continue
        if d.get("use"):
            used[fn] = d["use"]
            continue
        reason = str(d.get("skip") or "")
        if reason in REJECTED:
            problems.append((fn, f"REJECTED REASON {reason!r}: {REJECTED[reason]}"))
            continue
        if reason not in VALID:
            problems.append((fn, f"unknown reason {reason!r}. Valid: " + ", ".join(sorted(VALID))))
            continue
        _what, needs, _help = VALID[reason]
        missing = [k for k in needs if not str(d.get(k) or "").strip()]
        if missing:
            problems.append((fn, f"{reason} requires {', '.join(missing)} - {VALID[reason][2]}"))
            continue
        skipped[fn] = d
    for fn in sorted(set(declared or {}) - set(inventory)):
        problems.append((fn, "declared but NOT IN THE INVENTORY: the upstream does not export "
                             "this, so the entry is stale or misspelt"))
    return used, skipped, problems


def coverage(inventory, declared):
    """(used, validly_skipped, unaccounted) counts."""
    u, s, p = account(inventory, declared)
    return len(u), len(s), len(p)


def report(inventory, declared):
    """Human-readable accounting, for `validate` and for a plan report."""
    u, s, p = account(inventory, declared)
    L = [f"UPSTREAM PLOTS: {len(inventory)} exported, {len(u)} used, {len(s)} validly skipped, "
         f"{len(p)} unaccounted"]
    for fn, where in sorted(u.items()):
        L.append(f"  used         {fn}  ->  {where}")
    for fn, d in sorted(s.items()):
        L.append(f"  skipped      {fn}  ({d.get('skip')})")
    for fn, why in p:
        L.append(f"  PROBLEM      {fn}  {why}")
    return "\n".join(L)


def requires_accounting(spec):
    """True when a plugin wraps an upstream tool and therefore owes an account of its plots.

    A plugin that wraps nothing draws only what it invented, and there is no inventory to be
    measured against. Everything else inherits its upstream's figures whether it uses them or not.
    """
    return bool(((spec or {}).get("wraps") or {}).get("tool"))


def unreviewed(spec):
    """The plugin's own written admission that nobody has looked at its upstream's plots, or "".

    THE DEBT BELONGS TO THE PLUGIN THAT OWES IT. This was a tuple of eight plugin names in this
    module - `OWES_ACCOUNTING` - which is a registry, in the host, of the one thing the one-file
    format exists to stop the host from holding. It also went unseen by the check written to
    catch exactly that, twice: the names were behind a constant, and the read was
    `[n for n in owing if n not in OWES_ACCOUNTING]`, whose left operand is a loop variable.

    Moved into `wraps`, the admission travels with the plugin, is written by the person taking
    the debt on, and shows up in that plugin's diff rather than as a name appended to a list in
    somebody else's file. It is also STRICTER than the list was: a new wrapper used to need
    nothing at all until someone noticed and added it here, and now it cannot validate without
    either an accounting or an admission in its own words.
    """
    return str((((spec or {}).get("wraps") or {}).get("plots_unreviewed") or "")).strip()


def accounting_debt(specs):
    """(owing, undeclared) - wrappers with no `native_plots`, and those admitting to neither.

    `specs` is {plugin_name: spec}. `undeclared` is the regression: a wrapper that neither
    accounts for its upstream's figures nor says in its own file that nobody has looked at them.
    """
    # PARTIAL IS A STATE, and until now it was not one. The debt was discharged by the PRESENCE of
    # `native_plots`, so a wrapper that had ruled on two of its upstream's twenty read exactly like
    # one that had ruled on all twenty - and writing those two in would have stopped it being
    # counted as owing at all. Faced with that, the only honest move was to write nothing, which is
    # how an accounting stays at zero for months.
    #
    # Three states now. A complete accounting is `native_plots` and no admission. A partial one is
    # `native_plots` AND `plots_unreviewed` saying what is left - still owing, and progress is
    # recorded rather than discarded. None is the admission alone.
    owing = sorted(n for n, sp in (specs or {}).items()
                   if requires_accounting(sp)
                   and (unreviewed(sp) or not (sp or {}).get("native_plots")))
    undeclared = [n for n in owing if not unreviewed((specs or {}).get(n))]
    return owing, undeclared


def undrawn(declared, filenames):
    """Declared upstream plots that produced NO FILE anywhere in a run - [(function, use)].

    THE DECLARATION IS A PROMISE AND NOTHING WAS CHECKING IT. `native_plots` says, for every
    upstream function this plugin uses, the file that function writes. `function_for` above reads
    that mapping FORWARDS - given a file, which function drew it - and the backwards question was
    asked by nothing: a function the plugin declares it uses, whose file never appeared, is a
    panel the reader was promised and did not get.

    MEASURED, AND IT IS WHY THIS EXISTS. A plugin that had only ever run inside a SHARED
    environment silently depended on two packages it never declared - one of them reached only
    from inside an upstream function, so no import in this repository names it and no difference
    of declarations can predict it. Unplugged, three of its declared plots drew nothing across
    every unit of a full run, and the run still sealed: 657 panels where the reference had 711,
    and nothing in the tool said which promise had been broken.

    ACROSS THE WHOLE RUN, NOT PER UNIT, and that is the difference between a check and a nuisance.
    Plenty of declared panels are legitimately absent from one unit - a comparison panel in a
    single-sample unit, a pathway panel where the pathway is not present. A promise is broken only
    when the file appears NOWHERE, which is a fact about the run and not about one of its parts.

    A SKIPPED ENTRY PROMISES NOTHING. `not_applicable`, `superseded_by_design` and `duplicate_of`
    are rulings that this plugin does not draw the thing; asking them for a file would report the
    accounting as a defect. Only an entry carrying `use:` is a promise.
    """
    stems = {str(f).rsplit("/", 1)[-1] for f in (filenames or ())}
    stems |= {s[:-4] for s in list(stems) if s.endswith(".png")}
    out = []
    for fn, rec in sorted((declared or {}).items()):
        use = str((rec or {}).get("use") or "")
        if not use or (rec or {}).get("skip"):
            continue
        # AN ENTRY THAT PROMISES NO PANEL IS NOT A PANEL THAT WENT MISSING. A `use:` may name a
        # table rather than a figure - cellchat's `netAnalysis_computeCentrality` says
        # "tables/cellchat_centrality.csv (numbers only; its plot is not drawn)" - and asking a
        # figure question of it reports the declaration's own honesty as a defect. That was the
        # single false row this check produced on its first real run, and one false row in twelve
        # is the rate at which a check stops being read.
        if ".png" not in use:
            continue
        if not any(function_for(  # the SAME matcher, so the two can never disagree
                {fn: rec}, name) == fn for name in stems):
            out.append((fn, use))
    return out


def undeclared(declared, filenames, ids=()):
    """Files a run produced that NO declaration accounts for - [(filename, count)].

    THE OTHER DIRECTION FROM `undrawn`, AND THE ONE NOTHING WAS ASKING. `undrawn` catches a
    promise the run did not keep; this catches output the run made and nobody promised. Both read
    the same declaration with the same matcher, and until this existed a plugin could litter a run
    with files it had never mentioned and every gate in the tool would report the run as clean.

    MEASURED. One cohort of 1187 figures carried 24 `estimationNumCluster*.pdf` written by the
    NMF rank estimation inside an upstream function - not by any call this plugin makes, not named
    by any entry in `native_plots`, linked from no page, and cited by no sentence. They are the
    wrapped tool writing into the working directory, which is a thing wrapped tools do. The point
    is not that they are large; it is that nothing in the run could tell them from output somebody
    had asked for.

    `ids` is the plugin's OWN figure ids - what it draws itself rather than through the tool -
    passed in by the caller, because which declaration fields carry them is a fact about the
    format and not about this matcher. A file is accounted for when the upstream matcher names a
    function for it OR its name begins with one of those ids.

    THE COUNT IS RETURNED WITH THE NAME because litter arrives per unit: reporting 24 rows of the
    same file is a list nobody reads, and reporting one row hides that it happened 24 times.
    """
    import collections
    known = tuple(sorted((str(i) for i in (ids or ()) if str(i)), key=len, reverse=True))
    seen = collections.Counter()
    for f in (filenames or ()):
        name = str(f).rsplit("/", 1)[-1]
        if not name:
            continue
        if function_for(declared or {}, name):
            continue
        stem = name.rsplit(".", 1)[0]
        if any(stem.startswith(k) for k in known):
            continue
        # THE UNIT OR CONTRAST IS STRIPPED so the same litter from eighteen units is one row.
        seen[stem.split("__", 1)[0]] += 1
    return sorted(seen.items())


def function_for(declared, filename):
    """Which declared upstream function drew this file, or "" - read from the declaration.

    THE PLUGIN ALREADY SAYS WHERE EACH FUNCTION'S OUTPUT LANDS. `native_plots` carries, for every
    function it uses, the file that function writes; inverting that mapping names the function
    behind a file without the host knowing anything about the wrapped tool. A caption that says
    which upstream function drew the panel is the difference between a figure a reader can check
    against the tool's own documentation and a picture that appeared.

    A declaration may name one file, a brace family (`native_circle_{count,weight}.png`) or a
    placeholder (`native_contribution__<pathway>.png`). Each is turned into a pattern; the
    LONGEST literal prefix wins, so `nativecmp_diff_heatmap_count` beats a shorter declaration
    that also matches. A placeholder matches a name that reaches it and stops, which is what a
    file whose suffix is filled in at run time looks like before the value is known.
    """
    import re
    stem = str(filename).rsplit("/", 1)[-1]
    stem = stem[:-4] if stem.endswith(".png") else stem
    best, best_len = "", -1
    for fn, rec in (declared or {}).items():
        use = str((rec or {}).get("use") or "")
        if not use:
            continue
        for tok in re.findall(r"[A-Za-z0-9_{},<>.]+", use):
            tok = tok.strip(".,;")
            if tok.endswith(".png"):
                tok = tok[:-4]
            if len(tok) < 6:
                continue
            variants = [tok]
            if "{" in tok and "}" in tok:
                head_, rest = tok.split("{", 1)
                opts, tail = rest.split("}", 1)
                variants = [head_ + o.strip() + tail for o in opts.split(",")]
            for v in variants:
                lit = v.split("<")[0]
                if "<" in v:
                    ok = stem == lit or stem.startswith(lit)
                else:
                    ok = stem == v
                if ok and len(lit) > best_len:
                    best, best_len = fn, len(lit)
    return best
