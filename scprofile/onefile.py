"""The one-file plugin template — the shape `scaffold` writes and the README documents.

THE PLUGIN IS WRITTEN ONCE AND SHIPS PREBUILT; the builder and the planner run again on every
new machine and every new project. So everything those two need is DECLARED in the plugin rather
than discovered by them — what environment to build, how much memory to allow, what reference
data decides the answer, which scope the method is meaningful at.

A field left out is not neutral. It becomes a guess, made later, on somebody else's machine,
about a method they did not write.

Placeholders are `__NAME__`, `__SUMMARY__` and `__TOOL__`, substituted by `render()`. They are
not `str.format` fields on purpose: the template is mostly a dict literal, and escaping every
brace in it made the thing unreadable and unreviewable.
"""

from __future__ import annotations

TEMPLATE = '''"""__SUMMARY__

TODO — what this method does, in the terms a reader would use in a paper, and what it does not.
"""

PLUGIN = {
    "api": 1,
    "version": "0.1.0",
    "summary": "__SUMMARY__",
    "when_to_use": "TODO — the situation in which someone should reach for this",
    "wraps": {"tool": "__TOOL__", "homepage": "TODO", "license": "TODO", "cite": "TODO"},

    # READ THE TOOL'S DOCUMENTATION AND RECORD WHAT YOU CHANGED. A default accepted silently is
    # a decision nobody can find later.
    "upstream": {
        "docs": "TODO",
        "read": "TODO — the date you read it",
        "defaults_changed": ["TODO — a default this plugin overrides, and why"],
        "not_used": ["TODO — a capability of the tool this plugin deliberately does not expose"],
        "gotchas": ["TODO — a way this tool fails that does NOT raise"],
    },

    # CAPABILITIES, NEVER COLUMN NAMES. A plugin naming a real column has bound itself to one
    # project; the host resolves these against whatever the object actually calls things.
    "inject": {"required": ["lognorm", "label"], "optional": ["sample", "design"]},
    "provides": [],
    "produces": ["obs[TODO_score]", "tables/TODO_result.csv"],

    # SCOPE. Omit `per_unit` for a method meaningful over the whole cohort. Declare it when a
    # pooled answer would describe the average of the conditions and may describe none of them.
    # Add `also_cohort` ONLY when the method infers its own output vocabulary, so per-unit
    # results are not comparable with each other and one shared fit is needed to compare them.
    # "per_unit": "sample",
    # "also_cohort": {"why": "TODO — why per-unit results cannot be compared to each other"},

    "config": {
        "TODO_setting": {"type": "float", "default": 0.05, "min": 0.0, "max": 1.0,
                         "help": "TODO — what it decides, in the reader's terms"},
    },

    # WHAT THE BUILDER RESOLVES. Prefer ranges: the builder shares an environment between plugins
    # whose ranges provably overlap and isolates those that clash, naming the clash either way.
    # Pin exactly only where the tool needs it, and say why in `exact_pins_why`.
    "requires": {
        "python": ">=3.10,<3.13",
        "packages": {"__TOOL__": ">=1.0,<2", "anndata": ">=0.10,<0.12"},
    },

    # WHAT THE ALLOCATOR NEEDS. `cores` is what the method can actually use — the host passes a
    # share and the plugin must use that, never the machine's count. `memory_gb_per_100k` is a
    # RATE, because memory scales with the cells an instance touches; an absolute number would be
    # wrong for every project but the one it was measured on.
    #
    # MEASURE IT ONCE AND DECLARE IT. Left out, the allocator assumes a conservative rate and
    # prints that it is guessing — which either wastes memory or, if the guess is low, gets the
    # job killed. Every run reports each plugin's peak memory and cell count for exactly this.
    "cost": "medium", "cores": 4, "memory_gb_per_100k": 8,

    # REFERENCE DATA DECIDES ANSWERS AS MUCH AS THE ALGORITHM DOES. Declare everything this
    # method consults that did not come from the user's object — including what you cannot
    # verify. Three tiers:
    #   "fetch"    downloadable and checksummed; this tool gets it and verifies it
    #   "bundled"  ships inside a package, pinned by that version and by nothing else
    #   "runtime"  fetched by the tool WHILE IT RUNS — needs the network on the compute node
    # A reference you do not declare is one the plan cannot warn about and the report cannot name.
    # "references": {
    #     "TODO_prior": {"tier": "runtime", "role": "prior", "source": "TODO",
    #                    "cite": "TODO", "note": "TODO"},
    # },

    # WHAT A READER MUST NOT CONCLUDE. Required, and the most valuable field here: a result whose
    # limits were never written down is one somebody will over-read.
    "cannot_show": [
        "TODO — a conclusion this result does NOT support, however it looks",
    ],
}


def run(ctx):
    """The method call. Everything the contract requires has already been applied."""
    raise NotImplementedError(
        "__NAME__: run(ctx) is a skeleton. Replace this with the method call.\\n"
        "  ctx.counts() / ctx.X / ctx.obs(role) give you the data, resolved by ROLE\\n"
        "  ctx.cores is your share — never os.cpu_count()\\n"
        "  ctx.emit_obs / emit_table / emit_figure declare results; ctx.caveat states limits\\n"
        "  ctx.refuse(what, why) when the data cannot support the claim — never return a\\n"
        "  smaller answer that looks like a real one")


def selftest(ctx):
    """Prove the method RUNS AND RECOVERS A PLANTED SIGNAL, on a fixture.

    An import check passes on an environment that cannot compute. Plant an effect, run the real
    call, and assert the effect comes back — otherwise a broken environment is found inside a run
    instead of before one.
    """
    raise NotImplementedError(
        "__NAME__: selftest(ctx) is a skeleton. Build a fixture with ctx.fixture(), plant a "
        "signal, run the real computation, and assert it is recovered.")
'''


def render(name, summary="", tool="TODO"):
    """The template with its placeholders filled. Substitution, never `format`."""
    return (TEMPLATE
            .replace("__NAME__", str(name))
            .replace("__SUMMARY__", str(summary or f"TODO — what {name} gives you"))
            .replace("__TOOL__", str(tool or "TODO")))
