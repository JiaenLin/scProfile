"""What a plugin's UNIT is: a design group first, a sample only if the design supports it.

THE UNIT AXIS WAS HARD-WIRED TO THE SAMPLE COLUMN. `units = sorted(set(obs[sample_key]))`, with
no other possibility, and every consequence followed from that one line: a per-unit plugin ran
once per animal, every figure it drew was a figure about one animal, and any comparison between
conditions had to be assembled afterwards from summary numbers - or, where a design had too few
animals in an arm to support a sample-level test, was not drawn at all.

THAT IS THE WRONG DEFAULT AND IT GATES THE WRONG THING. The question a 2x2 exists to answer is
about the ARMS, not the animals. Pooling the cells of an arm gives the arm's own network,
inferred at full depth, with no requirement that each animal separately support an inference -
and a difference between two arms is the thing being asked for. The sample axis answers a
different and also useful question, "is this consistent across animals", and it is an ADDITION
rather than a precondition.

So the order here is: GROUP FIRST, SAMPLE AS WELL WHERE IT IS SUPPORTED, and no figure is
withheld because the sample axis is thin.

A GROUP is the combination of the design's BIOLOGICAL factors. Technical factors - batch,
chemistry, lane - are excluded from the label: crossing them multiplies the arms and splits the
very cells the pooling exists to gather, and a technical factor aliased with a biological one
adds nothing but a longer name. What is technical is not guessed here; the caller passes it,
because only the caller knows what the columns mean.
"""

from __future__ import annotations

#: Column names that are technical by convention. A DEFAULT, not a definition - `technical=`
#: replaces it outright, because one lab's `batch` is another's biological block.
DEFAULT_TECHNICAL = ("batch", "chemistry", "lane", "run", "flowcell", "library", "pool",
                     "sequencing_run", "chip", "kit")


def biological_factors(design, *, technical=DEFAULT_TECHNICAL, sample_key=None):
    """The factors that define a group: varying, not technical, not the sample itself.

    A factor with one level defines no contrast and would add a constant to every label.
    """
    tech = {str(t).lower() for t in (technical or ())}
    seen = {}
    for row in design.values():
        for f, v in (row or {}).items():
            seen.setdefault(str(f), set()).add(str(v))
    out = [f for f, lv in sorted(seen.items())
           if len(lv) > 1 and f.lower() not in tech and f != sample_key]
    return out


def group_label(row, factors, sep="_"):
    """The arm a sample belongs to, or None if the design does not place it."""
    vals = [str((row or {}).get(f)) for f in factors]
    if any(v in ("None", "") for v in vals):
        return None
    return sep.join(vals)


def resolve(design, *, sample_key=None, samples=None, technical=DEFAULT_TECHNICAL,
            prefer="group", min_per_group=1):
    """(plan, why) - the unit axes to run, GROUP FIRST.

    `plan` is a list of dicts, in run order:

        {"kind": "group",  "units": {arm: [samples...]}, "factors": [...]}
        {"kind": "sample", "units": {sample: [sample]},  "factors": []}

    The group axis comes first because it is the one the design was built to compare. The sample
    axis is appended when there is more than one sample, as an ADDITION - it is never a gate on
    the group axis, and its absence never withholds a group figure.

    `prefer` may be "group", "sample" or "both"; "group" still appends the sample axis when the
    design supports it, because running it costs one more pass and answers a question the group
    axis cannot: whether an arm's result is carried by all its animals or by one.
    """
    samples = list(samples if samples is not None else design)
    factors = biological_factors(design, technical=technical, sample_key=sample_key)
    plan, why = [], []

    groups = {}
    for s in samples:
        g = group_label(design.get(s), factors) if factors else None
        if g is not None:
            groups.setdefault(g, []).append(s)
    groups = {g: sorted(v) for g, v in sorted(groups.items())
              if len(v) >= int(min_per_group)}

    if prefer in ("group", "both") and len(groups) > 1:
        plan.append({"kind": "group", "units": groups, "factors": factors})
        why.append(f"group: {len(groups)} arm(s) over {', '.join(factors)} "
                   f"({'; '.join(f'{g} n={len(v)}' for g, v in groups.items())})")
    elif prefer in ("group", "both"):
        why.append("group: not resolvable - "
                   + ("no biological factor varies in the design"
                      if not factors else
                      f"only {len(groups)} arm(s) after grouping on "
                      f"{', '.join(factors)}, so there is nothing to compare"))

    if prefer in ("sample", "both", "group") and len(samples) > 1:
        plan.append({"kind": "sample", "units": {s: [s] for s in sorted(samples)},
                     "factors": []})
        why.append(f"sample: {len(samples)} unit(s), run as well - it answers whether an arm's "
                   f"result is carried by all its animals or by one")
    elif len(samples) <= 1:
        why.append("sample: one sample or none, so a per-sample axis would repeat the cohort")

    if not plan:
        why.append("NO UNIT AXIS: the plugin runs once over everything. That is a fact about "
                   "the design, not a failure - and it is not a reason to withhold a figure.")
    return plan, why
