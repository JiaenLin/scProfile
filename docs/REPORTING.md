# What a plugin owes, and what the reporter owns

Derived from the defects that produced it, not from a design meeting. Every rule below is here
because a real report failed without it, and the failure is named beside the rule.

## The one line

**A plugin knows its method. The host knows the cohort. Anything a plugin cannot see from inside
one method belongs to the host, and anything the host would have to guess belongs to the plugin.**

Every fix that stuck this cycle moved work in that direction. The report that started with 191
figures, 51 of them distinct and 140 of them the same fifteen plots redrawn per sample, had no
cohort overview, no comparison between design arms anywhere, and two headlines its own figures
refuted. The host owns these so that every plugin gets them without implementing them.

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
| `ctx.contradiction(...)` | When its OWN diagnostic refutes its OWN headline. Two pages carried a headline the evidence below it disproved - honestly plotted, and never met by a reader who takes the headline. It is a payload field of its OWN (contract 1.4), not one sentence among ten in `caveats`: a refutation nothing downstream can distinguish from a qualification cannot be shown where the claim is, and its absence cannot be noticed by anything. |

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
| folding repeated caveats | the caveats | a per-unit plugin emits the same sentence once per unit, with its own numbers in it |
| folding repeated refutations | the contradictions | the same problem, and it CANNOT be folded at render time because the exit standard matches the claim verbatim - so the FOLD dedupes on the sentence with its numbers blinded and keeps the first one intact |
| the per-sample appendix | the figures' units | a page carrying one plot per unit hides its own result |
| the verdict on the page | the rendered directory | only the host knows what a whole report looks like, and the page that fails is the one nobody opens |
| what a design can estimate | the design table | `ctx.estimable` - a term the data cannot carry raises from inside a fitting library after the fit is paid for, and every plugin fitting a model needs the same answer |
| what one instance COST | `ctx.measured` + the declaration | a plugin cannot see the scheduler's counter; the host takes the LARGER of the measurements and names which |

## The rules the boundary follows

**One statement of a fact, and every consumer asks the place it is stated.** Every drift this
cycle was two copies of one thing: two wave builders, two smoke checkers, a requirement declared
twice, a size formula written twice.

**The plan and the run must agree BY CONSTRUCTION.** Not by matching today. `available()` says it
for capabilities and `decisions_for` says it for decisions: one function, called by both.

**An absence is named.** A panel that could not be drawn, a metric that never arrived, a
capability with no provider, an identifier with no gene symbol. Silence and success look the same.

**A check that cannot fail is worse than no check.** Of the ten criteria in the exit standard, FIVE
were at some point measuring something other than what they claimed - one keyed on an attribute
the reporter never emits, one counted the stylesheet, one counted collapsed text, one could not
see a real arm figure, one read captions instead of the labels a figure is drawn with.

**Measure the artifact, never a fixture.** `scprofile standard` takes a DIRECTORY, so it can only
ever be pointed at a report that was actually written. And whatever WRITES a report measures it,
in the same breath: both job harnesses invoked the standard and the tool itself did not, so a run
delivered a report and said nothing about whether a reader could get through it. It never refuses
and never rewrites - a report that fails the standard is still the record of what the run did.

**A criterion that cannot fail, and a criterion a correct run cannot satisfy, are the same
defect.** Each criterion carries a page written to break it, and the ruler is measured against
those pages before it measures anything - on every invocation, not only in the suite. Pointing
the other way: `arms` is unmeetable on a cohort with no design table, so a page DECLARES its own
exemption with `data-standard-exempt="<criterion>"` and the element's visible text is the reason.
Exempt is reported as `exempt`, never as `ok`; an exemption with no reason is refused, because an
unexplained exemption is indistinguishable from the defect it excuses.

**What a plugin owes the report is checked before it runs, not after.** `declare.check` refuses a
per-unit plugin with no `unit_metrics`, a figure with no question, no `shows`, or no source table -
so a maintainer learns at authoring time rather than after a job. The keys a `report` block may
carry are stated ONCE and held against the keys the checker reads: the set was a literal written
before `unit_metrics` existed, and the checker spent three releases demanding a key it then
reported as unknown.

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

## The five domains, and where a report defect goes

`docs/ARCHITECTURE.md` carries the whole table; this is the half that concerns a report. Each
row is a defect that was misfiled before the boundary was written down, and misfiling one costs
a debugging session in the wrong file.

| the symptom | the domain that owns it | the remedy |
|---|---|---|
| a panel is missing and nothing says why | **the plugin** | it declared the figure and did not emit it, or never declared it — `figure_drift` |
| a per-unit page is N reports stapled together | **the plugin** | no `unit_metrics`; `declare.check` refuses this now |
| the run was killed with no traceback | **the plugin's declaration** | its memory model under-sizes what it cost — `memory_drift` |
| a headline its own figures refute | **the plugin** | `ctx.contradiction`; the host renders and the standard checks |
| no page says what the cohort was | **the reporter** | one method cannot see the cohort |
| nothing compares an arm | **the reporter**, unless there is no design | it renders per-arm from any per-cell column; with no design table the page declares the exemption |
| two panels showing one division of the samples | **the reporter** | aliased factors are folded and NAMED |
| a criterion passes on a page that plainly fails | **the standard** | it is measuring something other than what it claims — `selfcheck` |
| a criterion no correct run can satisfy | **the standard** | a declared exemption with a reason, or the criterion is wrong |

**The direction of every fix that stuck.** Work moved to whoever could see the thing: the cohort
to the host, the method to the plugin, the design to the host, the cost to whoever holds both the
measurement and the declaration. Nothing was fixed by asking a plugin to be more careful.

## Reproducing a report, efficiently

Three properties make a report cheap to get right, and all three were learned by getting them
wrong at full scale.

**One fix, one job.** A plugin is the unit of testing: eight cores and minutes, against a full
run that tests everything and attributes nothing. Two contradiction mechanisms were found broken
by two short jobs; the long run would have shown the same silent nothing and taken hours.

**The gate before the run.** A synthetic cohort through the whole host path costs minutes and has
caught a `TypeError` from calling a width constant as a factory, an unbound name that killed a
design-less run after every plugin had finished, and a checker still pointing at a page its
content had moved off.

**Nothing is re-run to fix a report.** `scprofile report` rebuilds every page from `report.json`,
so a reporting defect is a render away from fixed and never costs the compute again. That is why
the boundary matters: everything the host owns is recoverable without a job, and everything a
plugin owns is not.
