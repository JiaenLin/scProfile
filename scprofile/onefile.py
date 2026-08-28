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
        # `anndata` because the host reads the object with it inside YOUR interpreter before
        # `run` is called; `matplotlib` because `ctx.plot()` imports it inside yours too. Both are
        # contract dependencies rather than yours, and both are ERRORs to omit - a plugin missing
        # either works only for as long as it happens to share an environment with one that
        # names it.
        "packages": {"__TOOL__": ">=1.0,<2", "anndata": ">=0.11,<0.12",
                     "matplotlib": ">=3.6,<4"},
    },

    # WHAT THE ALLOCATOR NEEDS. `cores` is what the method can actually use — the host passes a
    # share and the plugin must use that, never the machine's count.
    #
    # MEMORY IS TWO TERMS, a fixed cost plus a per-cell one:
    #     peak_gb  ~=  memory_gb_base  +  memory_gb_per_100k * n_cells / 100_000
    # The interpreter, the imports and the object are paid once whatever n is. Modelling this as
    # a pure rate makes a 15 GB measurement on a 10k-cell instance read as 150 GB per 100k.
    #
    # MEASURE THEM ONCE AND DECLARE THEM. Left out, the allocator assumes conservative values and
    # prints that it is guessing — which either wastes memory or, if the guess is low, gets the
    # job killed. Every run FITS both terms from its own instances and prints them ready to paste.
    "cost": "medium", "cores": 4, "memory_gb_base": 4, "memory_gb_per_100k": 8,

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

    # WHAT THE PAGE SHOULD CONTAIN. The reporter reads this, orders the panels by `shows`, prints
    # each `question` above its panel, and states any declared panel that was NOT drawn - which is
    # the thing a reader cannot see for themselves. It knows no id here and never will: it
    # positions by `shows`, captions by `question` and links by `source`, so a plugin written
    # outside this repository is reported exactly as well as one inside it.
    #
    # DIAGNOSTICS FIRST, and that ordering is the point rather than a style. A result under a
    # failed check is a number, not an answer, and a reader must meet the check first.
    #   diagnostic   did this method's assumptions hold on THIS data?
    #   result       the answer it was run for
    #   comparison   the same question answered a second way - needs another plugin, so this is
    #                the one kind of panel that can be absent because something else did not run
    #
    # `source` is the table the panel must be drawable from. A figure whose numbers cannot be
    # opened is a figure a reader has to believe. The `id` is what `emit_figure` is called with.
    "report": {
        "figures": [
            {"id": "TODO_check", "shows": "diagnostic", "required": True,
             "question": "TODO - the check that decides whether the result below means anything",
             "source": "figures/TODO_check.csv"},
            {"id": "TODO_result", "shows": "result", "required": True,
             "question": "TODO - the question this method was run to answer",
             "source": "figures/TODO_result.csv"},
        ],
        # Another plugin answering the same question from different evidence, if there is one.
        # "reads_with": ["TODO"],
    },

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
        "  ctx.emit_obs / emit_table declare results; ctx.caveat states limits\\n"
        "  ctx.emit_figure(id, ...) - the id MUST be one declared in PLUGIN['report']\\n"
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
