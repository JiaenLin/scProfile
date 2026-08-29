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

R7  A COMPOSITIONAL READOUT IS CHECKED ON A SECOND SCALE, AND DISAGREEMENT IS DISCLOSED.
    Where values are shares of a total, a LINEAR difference of shares ranks by what is abundant
    and a LOG-RATIO ranks by what changes most in ratio. Both are correct arithmetic on the same
    numbers and they routinely give different orderings. A panel that NAMES elements is making a
    claim about the ordering, so it computes both, compares the top ranks, and where they
    disagree says so and declines to present its own ordering as the finding. Measured: the
    element leading the linear ranking was mid-table on the log ranking, and the element leading
    the log ranking had been used as a control on the grounds that it "does not move".

R8  A DIFFERENCE OF PRESENCE IS NOT A DIFFERENCE OF MAGNITUDE.
    In any comparison between two sets, an element present in one and absent from the other
    contributes its whole value as a "change". In every encoding it does so in the way that
    looks most like a finding - the extreme of a colour scale, an empty bar beside a full one,
    an arrow from the origin - and it sets the limits, compressing every real difference. Mark
    those elements, take them OFF the magnitude scale, and name them. Do not drop them: a
    dropped row is invisible and a reader cannot tell it was ever there.

R9  A CONTRAST STATES WHAT IT CANNOT SEPARATE.
    Aliasing is a property of the COMPARISON, not only of the factor pair. Two factors can be
    perfectly crossed over a whole cohort and still be aliased inside one conditional contrast,
    because conditioning discards the samples that crossed them. Each panel audits the samples
    it actually compares and says, on itself, which other factors are aliased, which are partly
    confounded, and which are balanced.

R10 A PANEL NAMES ON ITS FACE WHAT IT WAS DRAWN FROM.
    A caption does not travel with an image into a slide, a grant or a referee's PDF. The unit,
    what kind of unit it is, and n go ON the figure. A pooled group and a single member render
    identically otherwise, and the reader supplies the cohort the picture never claimed.

R11 WHERE THE WEIGHT IS NORMALISED WITHIN A UNIT, COMPARE SHARES AND PRINT THE TOTALS.
    Many methods return a quantity computed over the elements present, so two units' values are
    on two scales and a raw difference between them mostly reports which unit is smaller.
    Measured: four groups whose totals spanned a factor of four, where the raw comparison found
    no reversals at all and the share comparison found five. Whether a weight is per-object or
    absolute is not knowable from the numbers - it is DECLARED, and the conservative reading is
    the default.
"""

from __future__ import annotations

#: Levels a kind can be drawn at. Group first, deliberately - see R6.
GROUP, SAMPLE = "group", "sample"

#: The rule ids, so a kind can declare which it is bound by and a test can check it obeys them.
RULES = ("R1_one_scale", "R2_absence_split", "R3_cut_names_omitted",
         "R4_denominator_declared", "R5_per_object_scale", "R6_never_gated_on_sample",
         "R7_second_scale", "R8_presence_not_magnitude", "R9_contrast_confounds",
         "R10_provenance_on_face", "R11_share_when_per_object")


class Kind:
    """One panel kind: what it shows, what it cannot show, and the rules it must obey."""

    def __init__(self, kid, title, establishes, does_not_establish, *, rules=(),
                 levels=(GROUP, SAMPLE), per_contrast=True, needs=(), cohort_only=False):
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
        #: True when the kind describes the WHOLE COHORT and is drawn once, not once per arm.
        #: Without this a test asserting "every arm gets every host-owned kind" counts a
        #: cohort-level panel as an arm panel and goes red on correct behaviour.
        self.cohort_only = bool(cohort_only)

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
    Kind("interaction", "Whether one factor's effect depends on another",
         "which elements respond to a factor differently at each level of a second factor, and "
         "which reverse direction outright",
         "that any single departure from the identity line exceeds noise - no interval is "
         "computed, and an element absent from any of the four arms is not drawn at all",
         rules=("R1_one_scale", "R2_absence_split", "R5_per_object_scale",
                "R6_never_gated_on_sample"),
         per_contrast=False, levels=(GROUP,), cohort_only=True),
    Kind("unit_presence", "Which populations each unit contains",
         "which populations were available to the method in each unit, and how that varies "
         "across the design",
         "WHY a population is absent - too few cells to annotate and genuinely not present are "
         "the same thing in a label column - nor that a present population was well sampled",
         rules=("R2_absence_split", "R4_denominator_declared", "R6_never_gated_on_sample"),
         per_contrast=False, levels=(GROUP,), cohort_only=True),
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


#: WHO OWNS EACH KIND, WHICH IS A DIFFERENT QUESTION FROM WHETHER IT IS DRAWN YET.
#:
#: This distinction did not exist and its absence was misleading in the direction that flatters
#: nobody: thirteen kinds were registered, five were drawn, and the eight remaining read as work
#: not yet done. Three of them are not work at all. A latent decomposition of the group-by-
#: population matrix and a similarity embedding over groups are ANALYSES - they produce numbers
#: that first exist at render time, which `docs/ARCHITECTURE.md` forbids the reporter outright -
#: and database coverage needs the reference funnel, which an edge list does not carry and no
#: declaration can supply. Those three belong to the plugin, which has the method's machinery and
#: its statistics; a plugin drawing one is complete, not a stopgap.
#:
#: So a kind declares an owner. `host` means: derivable from `report.unit_network` by
#: aggregation alone, and therefore owed to every plugin that declares one. `plugin` means: needs
#: an analysis the host may not perform, or information the declaration does not carry - with the
#: reason recorded, because "the host does not draw this" and "the host must not draw this" look
#: identical in a table and mean opposite things.
HOST, PLUGIN = "host", "plugin"

OWNER = {
    "interaction": (HOST, ""),
    "unit_presence": (HOST, ""),
    "matrix": (HOST, ""),
    "diff_matrix": (HOST, ""),
    "circle": (HOST, ""),
    "chord": (HOST, ""),
    "role_scatter": (HOST, ""),
    "role_shift": (HOST, ""),
    "flow_rank": (HOST, ""),
    "flow_compare": (HOST, ""),
    "role_heatmap": (HOST, ""),
    "contribution": (HOST, ""),
    "patterns": (PLUGIN, "a latent decomposition is an analysis, and the reporter may not "
                         "produce a number that first exists at render time"),
    "similarity": (PLUGIN, "a similarity embedding over groups is an analysis, and the choice "
                           "of metric belongs to the method rather than to the page"),
    "coverage": (PLUGIN, "the reference funnel is not in an edge list and no declaration "
                         "carries it; only the plugin knows what its database offered"),
}

#: WHICH KINDS A RUN ACTUALLY DRAWS TODAY, and where. A registry nothing consults is a
#: specification of intent; pairing it with the implemented set turns the difference into a
#: recorded gap instead of an assumption. `tests/test_contract.py` asserts every id here is a
#: registered kind, so the two cannot drift apart silently — and that every HOST-owned kind is
#: in here, which is the assertion that would have caught the five-of-thirteen gap.
IMPLEMENTED = {
    # host-drawn, from a plugin's `report.unit_network` declaration
    # The id is built as C1_diff_<count|strength>; the checkable literal is the stem.
    "diff_matrix": "compare_panel.draw_contrast — C1_diff_",
    "flow_compare": "compare_panel.draw_contrast — C3_flow",
    "role_shift": "compare_panel.draw_contrast — C4_role_shift",
    "circle": "network_panels.circle — N1_circle, per arm",
    "chord": "network_panels.chord — N2_chord, per arm",
    "matrix": "network_panels.matrix — N3_matrix, per arm",
    "role_scatter": "network_panels.role_scatter — N4_role, per arm",
    "flow_rank": "network_panels.flow_rank — N5_flow, per arm, needs `group`",
    "role_heatmap": "network_panels.role_heatmap — N6_role_heatmap, per arm, needs `group`",
    "contribution": "network_panels.contribution — N7_contribution, per arm, needs "
                    "`group` and `member`",
    "unit_presence": "network_panels.unit_presence — P1_population_presence, on the cohort page",
    "interaction": "compare_panel.draw_interaction — C5_interaction, one per crossed pair",
}

#: Registered, specified, and NOT drawn by any run. Named so the gap is auditable.
NOT_IMPLEMENTED = tuple(k.id for k in KINDS if k.id not in IMPLEMENTED)


def implemented():
    """{kind id: where it is drawn} for the kinds a run currently produces."""
    return dict(IMPLEMENTED)


def owner(kid):
    """(owner, reason) for one kind. The reason is empty for a host-owned kind."""
    return OWNER.get(kid, (HOST, ""))


def host_kinds():
    """The kinds the host owes every plugin that declares a `unit_network`."""
    return tuple(k.id for k in KINDS if owner(k.id)[0] == HOST)


def plugin_kinds():
    """{kind id: why the host does not draw it} - kinds that belong to the method."""
    return {k.id: owner(k.id)[1] for k in KINDS if owner(k.id)[0] == PLUGIN}


def gaps():
    """HOST-OWNED kinds this tool has specified and does not yet draw.

    A kind the host must NOT draw is not a gap and is no longer counted as one: it is in
    `plugin_kinds()` with the reason. Conflating the two published a catalogue that read as
    eight-thirteenths unfinished when three of the eight were finished decisions.
    """
    return tuple(k for k in NOT_IMPLEMENTED if owner(k)[0] == HOST)
