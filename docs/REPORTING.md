# What a plugin owes, and what the reporter owns

Derived from the defects that produced it, not from a design meeting. Every rule below is here
because a real report failed without it, and the failure is named beside the rule.

## The one line

**A plugin knows its method. The host knows the cohort. Anything a plugin cannot see from inside
one method belongs to the host, and anything the host would have to guess belongs to the plugin.**

Every fix that stuck this cycle moved work in that direction. The report that started with 191
figures, 51 of them distinct and 140 of them the same fifteen plots redrawn per sample, had no
cohort overview, no comparison between design arms anywhere, and two headlines its own figures
refuted. None of that was a plugin being careless: it was work nobody owned.

## What a plugin owes

A plugin declares these; the host holds it to every one of them.

| It must declare | Why, and what went wrong without it |
|---|---|
| `inject.required` | The SINGLE statement of what it must be given. Stating the same requirement twice - once as `inject`, once as a `needs_*` flag - drifted, and six decisions read the flag nobody set: no plugin ever refused, no contrast was ever planned, and the wave graph had no edges. |
| `provides` | The capability it offers. A plugin naming a PEER hard-codes one site's toolbox; naming a capability lets the host resolve the producer. Two plugins wrote the thing another asked for by name and declared `provides: []`, so the request could never be satisfied. |
| `produces` | Every slot it writes, INCLUDING the column names of any array. A 674-column matrix reaches the object as a bare ndarray, and the host can split it by design arm and can only call the result `X_tf_activity[3]`, which is not a regulator. |
| `report.figures` | Per panel: `id`, `shows`, the QUESTION it answers, its `source`, and whether it is `required`. Without a declaration an absent panel and a panel nobody wanted look identical. |
| `report.unit_metrics` | If it runs per unit: at least one comparable scalar. Without it a per-unit plugin delivers N single-sample reports stapled together, and whether the units agree is answered nowhere. One plugin's count ran 8,194 to 38,895 across the units of a single tissue. |
| `cannot_show` | Its limits, written before the run. A result whose limits were never written down reads exactly as authoritative as one whose limits were thought about. |
| caveats, claim-first | The leading sentence carries the claim; the host shows that and collapses the rest. A caveat nobody reaches the end of was not read. |
| `ctx.contradiction(...)` | When its OWN diagnostic refutes its OWN headline. Two pages carried a headline the evidence below it disproved - honestly plotted, and never met by a reader who takes the headline. |

And two things about how it draws:

- **Through the shared conventions.** `ctx.figure` carries the palette, the label shortening, the
  axis naming. A convention reimplemented per plugin is a convention that has already drifted -
  three of them had.
- **A grid shares one scale.** Panels that scale themselves cannot be compared, and comparison is
  the only reason to draw a grid. One report had y-axes of -10..5, -5..5 and -2.5..2.5 side by
  side, and the panel with the largest effects looked flattest.

## What the host owns

None of this is in any plugin, and none of it should be. Each is computed ONCE, from what
plugins already produce, and arrives for a plugin written next year that does nothing to get it.

| The host computes | From | Because a plugin cannot see it |
|---|---|---|
| the cohort overview | the design table | one method does not know how many samples or arms there are |
| across units | `ctx.metric` per unit + the design | a per-unit instance sees ONE unit by construction |
| across the design | obs columns and named obsm columns | the same: an instance cannot compare arms it was not given |
| cross-plugin concordance | per-cell columns of DIFFERENT plugins | a diagnostic is useless on the page of the plugin that computed it - one plugin exists to check that a trajectory is not a cell-cycle axis, and the trajectory is on another page |
| which factors are aliased | the design | two factors that split the samples identically are one panel, not two |
| what the constraint binds | the constraint + what each page shows | only the host holds both |
| folding repeated caveats | the caveats | ten units emit the same sentence with their own numbers in it |
| the per-sample appendix | the figures' units | a page carrying one plot ten times hides its own result |

## The rules the boundary follows

**One statement of a fact, and every consumer asks the place it is stated.** Every drift this
cycle was two copies of one thing: two wave builders, two smoke checkers, a requirement declared
twice, a size formula written twice.

**The plan and the run must agree BY CONSTRUCTION.** Not by matching today. `available()` says it
for capabilities and `decisions_for` says it for decisions: one function, called by both.

**An absence is named.** A panel that could not be drawn, a metric that never arrived, a
capability with no provider, an identifier with no gene symbol. Silence and success look the same.

**A check that cannot fail is worse than no check.** Of nine criteria in the exit standard, FIVE
were at some point measuring something other than what they claimed - one keyed on an attribute
the reporter never emits, one counted the stylesheet, one counted collapsed text, one could not
see a real arm figure, one read captions instead of the labels a figure is drawn with.

**Measure the artifact, never a fixture.** `scprofile standard` takes a DIRECTORY, so it can only
ever be pointed at a report that was actually written.

## Efficiency

**One fix, one job.** A plugin is the unit of testing: eight cores and minutes, against sixty-four
cores and hours for a run that tests everything and attributes nothing. Two contradiction
mechanisms were found broken by two short jobs - the long run would have shown the same silent
nothing and taken three hours to do it.

**The gate before the run.** A synthetic cohort through the whole host path costs minutes and has
caught, so far: a `TypeError` from calling a width constant as a factory, an unbound name that
killed a design-less run after every plugin had finished, and a checker still pointing at a page
its content had moved off.

**The standard is run, not remembered.** Both harnesses invoke it. A module somebody has to think
to call is the same as not having it: the report that fails is exactly the one nobody checks.
