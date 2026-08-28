"""The registry of NETWORK PANEL KINDS, and the rules every one of them must obey.

WHY A REGISTRY AND NOT TWELVE FUNCTIONS. A panel kind is drawn once per contrast and once per
unit, at two levels - group and sample - so a design with six contrasts and ten samples turns
one kind into dozens of figures. Writing those by hand is how a kind ends up drawn correctly in
one place and wrongly in another, and how "every figure covers every arm" quietly becomes "most
of them do". A kind is DECLARED here; the expansion over contrasts and levels is mechanical and
belongs to the host.

THE RULES BELOW WERE PAID FOR. Each is a defect that was drawn, looked at, and diagnosed on real
output before it was written down. They are properties of the panel kinds, not of any study, and
nothing here names a tissue, a species, a factor or a level.

R1  ONE SCALE ACROSS A GRID, NEVER PER PANEL.
    A grid whose panels each use their own maximum makes the widest edge in every panel look
    identical whatever it is worth. Measured on a nine-panel decomposition: the widest edge in
    one panel was 0.0120 against another's 0.0384, a factor of 3.2, and per-panel maxima would
    have drawn both at full width. The shared maximum is computed over the whole grid and
    PRINTED, so a reader can convert a width back to a number.

R2  ABSENCE IS NOT ZERO, AND IT IS NOT ONE THING.
    A population with no edge has two causes that look identical and mean opposite things:
      measured absence - it was scored and returned nothing. That is a RESULT.
      never tested     - it fell below a minimum-cells floor before scoring. That is a
                         THRESHOLD, and reading it as silence is reading a threshold as biology.
    A panel that cannot distinguish them must say it cannot. A panel that can must mark them
    differently and say which mark is which.

R3  A CUT MUST NAME WHAT IT REMOVED.
    Circle and chord panels draw a subset of edges or they are unreadable. State the fraction of
    total strength kept, and NAME the populations left with no link - on a real cohort a chord
    silently dropped five of thirteen. Keep each population's strongest link in and out whatever
    its rank, so nothing vanishes merely for being weak.

R4  A DENOMINATOR THAT IS NOT WHAT IT LOOKS LIKE MUST BE DECLARED.
    Averaging over N units while a quantity was measurable in fewer than N divides by N anyway
    and under-reads by the ratio. Say the denominator, and mark the elements it affects.

R5  A SCALE THAT IS PER-OBJECT IS NOT COMPARABLE ACROSS OBJECTS.
    Where each unit's inference is normalised within that unit, widths and heights compare
    WITHIN a panel and rank-order across panels, and nothing more. The caption says so rather
    than leaving a reader to assume otherwise.

R6  NO PANEL IS GATED ON THE SAMPLE AXIS.
    Every kind is drawn at GROUP level first - units pooled into design arms - and additionally
    per sample where the design supports it. A thin sample axis withholds nothing.
"""

from __future__ import annotations

#: Levels a kind can be drawn at. Group first, deliberately - see R6.
GROUP, SAMPLE = "group", "sample"

#: The rule ids, so a kind can declare which it is bound by and a test can check it obeys them.
RULES = ("R1_one_scale", "R2_absence_split", "R3_cut_names_omitted",
         "R4_denominator_declared", "R5_per_object_scale", "R6_never_gated_on_sample")


class Kind:
    """One panel kind: what it shows, what it cannot show, and the rules it must obey."""

    def __init__(self, kid, title, establishes, does_not_establish, *, rules=(),
                 levels=(GROUP, SAMPLE), per_contrast=True, needs=()):
        self.id = kid
        self.title = title
        #: WHAT IT ESTABLISHES AND WHAT IT DOES NOT, as a pair. A panel described only by what
        #: it shows invites every reading its geometry allows; the second half is the half that
        #: stops a reader taking a picture for a test.
        self.establishes = establishes
        self.does_not_establish = does_not_establish
        self.rules = tuple(rules)
        self.levels = tuple(levels)
        #: True when the kind compares two arms; False when it describes one unit or arm.
        self.per_contrast = per_contrast
        #: Columns the kind needs from a unit network, beyond source/target/weight.
        self.needs = tuple(needs)

    def __repr__(self):
        return f"<Kind {self.id} {'contrast' if self.per_contrast else 'single'}>"


#: EVERY KIND THIS TOOL KNOWS HOW TO DRAW OR HAS DECIDED IT MUST. `drawn` in the host's registry
#: says which are implemented; a kind listed here and not drawn is a NAMED gap rather than a
#: silence, which is the only honest way to publish a catalogue that is not yet complete.
KINDS = (
    Kind("matrix", "Sender by receiver matrix",
         "which ordered population pairs carry inferred signal, and how much",
         "that a pair is absent for a biological reason - see R2",
         rules=("R2_absence_split", "R5_per_object_scale", "R6_never_gated_on_sample"),
         per_contrast=False),
    Kind("diff_matrix", "Change in the sender-by-receiver matrix",
         "which ordered pairs differ between two arms, and in which direction",
         "that any single difference is larger than the noise - no interval is computed",
         rules=("R5_per_object_scale", "R6_never_gated_on_sample")),
    Kind("circle", "Aggregate network, as a ring",
         "the shape of the network: who signals to whom, at what relative strength",
         "absolute strength, and nothing about the edges the cut removed - see R3",
         rules=("R1_one_scale", "R3_cut_names_omitted", "R5_per_object_scale"),
         per_contrast=False),
    Kind("chord", "Aggregate network, as a chord diagram",
         "how one population's outgoing strength is distributed over its partners",
         "anything about a population with no surviving link - it is NOT DRAWN, so R3 applies "
         "with full force",
         rules=("R1_one_scale", "R3_cut_names_omitted"), per_contrast=False),
    Kind("role_scatter", "Sender against receiver strength",
         "whether a population is a net sender or a net receiver within one arm",
         "that the asymmetry is significant - it is two sums, not a test",
         rules=("R5_per_object_scale",), per_contrast=False),
    Kind("role_shift", "How signalling roles move between two arms",
         "the direction and relative size of each population's change in role",
         "that any single arrow is longer than chance; arrows have no interval",
         rules=("R5_per_object_scale",)),
    Kind("flow_rank", "Groups ranked by total flow, within one arm",
         "which pathways or groups carry the most inferred signal here",
         "that a bar's HEIGHT is comparable to the same bar in another unit - only rank is",
         rules=("R5_per_object_scale",), per_contrast=False, needs=("group",)),
    Kind("flow_compare", "Group flow in two arms, paired",
         "which groups differ most between two arms, by rank and by relative size",
         "a tested difference - no interval is drawn because none was computed",
         rules=("R1_one_scale", "R5_per_object_scale"), needs=("group",)),
    Kind("role_heatmap", "Group by population role matrix",
         "where in the population set a group acts, as sender and as receiver",
         "how STRONG a group is - rows are scaled to their own maximum by construction",
         rules=("R1_one_scale",), per_contrast=False, needs=("group",)),
    Kind("patterns", "Latent communication patterns",
         "which populations use which groups together, and at what rank",
         "a cell state, a cluster, or any ordering of the patterns themselves",
         rules=("R1_one_scale",), per_contrast=False, needs=("group",)),
    Kind("similarity", "Groups placed by shared partners",
         "which groups act between the same populations as each other",
         "magnitude - the similarity discards it, and unplaceable groups must be NAMED",
         rules=("R3_cut_names_omitted",), per_contrast=False, needs=("group",)),
    Kind("contribution", "One group decomposed into its members",
         "how a group's total is distributed over the interactions inside it",
         "that a member absent from a panel was tested and returned nothing - see R2",
         rules=("R1_one_scale", "R2_absence_split", "R4_denominator_declared"),
         per_contrast=False, needs=("group", "member")),
    Kind("coverage", "What the reference database offered and what survived",
         "how far the object could see the reference, and how much survived testing",
         "that what survived is biology rather than what the preparation retained",
         rules=(), per_contrast=False),
)

BY_ID = {k.id: k for k in KINDS}


def expand(kinds, contrasts, levels=(GROUP, SAMPLE)):
    """[(kind, contrast_or_None, level)] - the full figure set a design implies.

    THE EXPANSION IS MECHANICAL AND THAT IS THE POINT. "Every kind, every arm, both levels" is a
    property of this function rather than of anybody's diligence, so a kind added here is drawn
    everywhere it applies without a second edit.
    """
    out = []
    for k in kinds:
        for lv in levels:
            if lv not in k.levels:
                continue
            if k.per_contrast:
                out += [(k, c, lv) for c in contrasts]
            else:
                out.append((k, None, lv))
    return out
