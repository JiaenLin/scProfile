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


#: PLUGINS THAT WRAP A TOOL AND DO NOT YET ACCOUNT FOR ITS PLOTS. A ratchet, not an excuse: the
#: list may SHRINK and never grow, so the practice is locked without pretending the debt is paid.
#: Every name here is a wrapper whose upstream ships figures nobody has looked at, and the first
#: one to be worked on will show what that is worth - cellchat went from 1 of 30 used to 14, and
#: four of the fourteen answer a design comparison directly.
OWES_ACCOUNTING = (
    "abundance", "cellcycle", "de", "decoupler", "liana", "pseudotime", "scenic", "velocity",
)


def requires_accounting(spec):
    """True when a plugin wraps an upstream tool and therefore owes an account of its plots.

    A plugin that wraps nothing draws only what it invented, and there is no inventory to be
    measured against. Everything else inherits its upstream's figures whether it uses them or not.
    """
    return bool(((spec or {}).get("wraps") or {}).get("tool"))


def accounting_debt(specs):
    """(owing, unexpected) - wrappers with no `native_plots`, and any not on the ratchet list.

    `specs` is {plugin_name: spec}. `unexpected` is what makes this a ratchet: a NEW wrapper
    arriving without an accounting is a regression, while the named ones are known debt.
    """
    owing = sorted(n for n, sp in (specs or {}).items()
                   if requires_accounting(sp) and not (sp or {}).get("native_plots"))
    unexpected = [n for n in owing if n not in OWES_ACCOUNTING]
    return owing, unexpected
