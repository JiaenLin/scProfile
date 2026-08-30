"""WHAT A READER NEEDS TO ANSWER A COMPARISON — designed from the biology, then resolved.

TWO STEPS, DELIBERATELY SEPARATED, because merging them is what makes a figure set shallow.

    DESIGN      given a question the design supports, what evidence would answer it?
                Asked of the BIOLOGY. No tool, no plugin, no panel kind appears here.
    RESOLVE     for each piece of evidence, what can produce it? The wrapped tool's OWN
                function first, a host panel second, and an honest gap third.

Run together, the question silently becomes "what can we draw?", and the answer is whatever the
host already draws. That is how a cell-cell communication section came to consist of one
difference matrix, one ranked bar chart and one scatter — three panels answering one question
between them, for a design that supports seven.

WHY THE ORDER MATTERS MORE THAN THE CONTENT. A need that nothing can produce is a RESULT: it says
this dataset cannot answer that part of the question, which is a sentence a paper should contain.
A need that is never written down cannot be reported missing, and the section reads as complete.

Nothing here is specific to a method, an assay or an organism. `NEEDS` is about what it takes to
believe a difference between two groups of cells; a plugin says which of them it can supply, in
its own declaration, and never the reverse.
"""

#: Evidence a reader needs to believe a difference between two arms. Each entry says what the
#: need IS, why the biology requires it, and what a section is missing without it.
#:
#: These are questions about a comparison, not about a drawing. "Which populations changed" is a
#: need; "a diverging heatmap" is one way to serve it, and belongs in `panels.py`.
NEEDS = {
    "who_changed": (
        "Which populations differ between the arms, and by how much",
        "A difference at the level of the tissue is uninterpretable until it is attributed to "
        "populations. Without it a section can say the arms differ and nothing more."),
    "what_carries_it": (
        "Which signalling programmes carry the difference",
        "Populations do not differ in the abstract - they differ in particular pathways. This is "
        "the axis a reader needs to connect a result to known biology."),
    "direction": (
        "Whether a population changed as a sender, as a receiver, or both",
        "Sending and receiving are different biology: a population that starts receiving a "
        "signal it did not receive before is a target, not a source, and treating the two as one "
        "quantity hides which."),
    "abundance_or_intensity": (
        "Whether the difference is driven by how MANY cells there are or by what each cell does",
        "The most common false positive in this kind of analysis. A population that doubles in "
        "abundance will appear to signal more with no change in any cell, and the two are "
        "indistinguishable in a total."),
    "presence_or_magnitude": (
        "Whether a changed element is absent from one arm or merely weaker in it",
        "Absence and reduction have different causes and different consequences. A population "
        "that is not there did not stop signalling; it was not sampled, or does not exist in "
        "that arm, and treating the two as one difference attributes a sampling fact to biology."),
    "specificity": (
        "Whether the difference is concentrated in a few pairs or spread across the network",
        "A diffuse shift usually reflects a global property - depth, composition, dissociation - "
        "while a concentrated one is the kind of finding that can be followed up."),
    "consistency": (
        "Whether the samples within an arm agree, or the arm rests on one animal",
        "The arm is the unit of inference and the sample is the confidence in it. Without this a "
        "reader cannot tell a population-level effect from one library."),
    "what_was_excluded": (
        "Which populations and elements could not enter the comparison, and why",
        "Every comparison drops something. Unnamed, the omission is invisible and the reader "
        "takes what remains for the whole tissue, so a population that could not be compared is "
        "read as one that did not change."),
}

#: WHICH NEEDS APPLY TO WHICH KIND OF QUESTION. A marginal effect and an interaction do not need
#: the same evidence: an interaction is a statement about two differences, so it needs each of
#: them shown separately before their difference means anything.
FOR_QUESTION = {
    "cohort": ("consistency", "what_was_excluded", "abundance_or_intensity"),
    "marginal": ("who_changed", "what_carries_it", "direction", "abundance_or_intensity",
                 "presence_or_magnitude", "specificity", "consistency", "what_was_excluded"),
    "simple": ("who_changed", "what_carries_it", "direction", "presence_or_magnitude",
               "consistency", "what_was_excluded"),
    "interaction": ("what_carries_it", "who_changed", "specificity",
                    "abundance_or_intensity", "consistency", "what_was_excluded"),
}

#: The routes a need can be met by, best first. NATIVE is first on principle, not on preference:
#: the wrapped tool's own function is the statistic and the encoding its authors chose, and a
#: reimplementation is a second implementation to keep in step.
ROUTES = ("native", "host", "unresolved")


def needs_for(question_kind):
    """[(need_id, what, why)] for one kind of question."""
    return [(n, NEEDS[n][0], NEEDS[n][1])
            for n in FOR_QUESTION.get(str(question_kind), ()) if n in NEEDS]


def declared_evidence(plugin_spec):
    """{need_id: [route strings]} a plugin says it can supply. `{}` when it declares none.

    A plugin declares this in `report.provides_evidence`, as a list of routes per need, each of
    the form `native:<function>` or `host:<panel kind>`. It is the plugin's own statement about
    what it can answer, and nothing else in the tool may assert it on the plugin's behalf.
    """
    return dict(((plugin_spec or {}).get("report") or {}).get("provides_evidence") or {})


def resolve(need_id, plugin_spec):
    """How this need would be met: (route, provider, why).

    `native` when the wrapped tool ships a function for it, `host` when a registered panel kind
    serves it, `unresolved` when neither - and unresolved is an answer, not a failure.
    """
    routes = declared_evidence(plugin_spec).get(need_id) or []
    for r in routes:
        kind, _, provider = str(r).partition(":")
        if kind == "native" and provider:
            return ("native", provider, "the wrapped tool's own function")
        if kind == "host" and provider:
            return ("host", provider, "a registered host panel kind")
    return ("unresolved", "", "neither the wrapped tool nor the host provides this evidence")


def plan_for(question_kind, plugin_spec):
    """[{need, what, why, route, provider}] - the design and its resolution, in one table."""
    out = []
    for nid, what, why in needs_for(question_kind):
        route, provider, note = resolve(nid, plugin_spec)
        out.append({"need": nid, "what": what, "why": why,
                    "route": route, "provider": provider, "route_note": note})
    return out


def coverage(question_kind, plugin_spec):
    """(met, total, [unmet need ids]) for one question kind."""
    rows = plan_for(question_kind, plugin_spec)
    unmet = [r["need"] for r in rows if r["route"] == "unresolved"]
    return len(rows) - len(unmet), len(rows), unmet
