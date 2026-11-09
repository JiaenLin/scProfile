# The held-out plugins, migrated through the maker

Eight plugins were held out of the maker's development so that it could be tested on plugins it
had never been fitted to (DEVPOINTS.yaml, `rules.held_out`). They are spent one at a time. Each
migration is a **blind test of the maker**: the maker is run on the plugin as it stands, and what
it says is written here **before the maker changes**. Only then are the maker's gaps fixed, in the
maker or in the plugin's worksheet answers, never by a hand edit of the plugin. A maker fix found on
one plugin is tested on the next.

Each record has three parts, written in this order:

1. **the blind record** - the maker's own output on the unchanged plugin, and the dev ladder's
   verdict tier by tier;
2. **what the maker lacked** - the fixes it caused, each with the test that fails on the commit the
   record was taken at;
3. **what the next plugin should test** - the fixes the next migration measures blind.

The numbers below are the maker's and the ladder's on the synthetic two-shape fixture. Nothing in
this file comes from a cohort.

---

## 1. `de` (PyDESeq2) - blind record taken at `f5175ea`

**Venue.** The workstation; the harness's maker at `3860507`; the plugin's interpreter a virtual
environment built from this repository's shipped lock (`setup/locks/`, 161 exact pins, Python
3.12, pydeseq2 0.5.2, formulaic 1.2.2); both cohort projects' word lists for the leak tier.

### The blind record

| what was run | what the maker said |
|---|---|
| `sch dev convert status --name de --python <env>` | HELD OUT banner. **build 5 of 9**: environment, contract, defaults, references, judgement done; **freshness STALE** (`version` 0.2.0, 14 commits since it moved); **inventory PART** (`wraps.plots_unreviewed`, and the stage declares no `finished_by`); **plan PART** (6 entries, each lacking an axis, a position and a legend); **layout** todo. **test 0 of 9**. 13 of 17 required keys filled by a stage |
| `inventory --python <env>` | exit 2, *no extractor could look at pydeseq2*. Measured in the same environment, pydeseq2 0.5.2 has three plotting functions: `DeseqDataSet.plot_dispersions`, `DeseqStats.plot_MA` and `pydeseq2.utils.make_MA_plot` - a class method and a submodule function, both outside the python extractor's reach. `account`: exit 2, nothing to rule on |
| `plan`, `plan --migrate` | 6 entries, all `drawn_by: plugin`. `--migrate` prints each with `axis: unit` and `position: contrast` - `unit` for a plugin that runs once over the whole cohort |
| `layout` | exit 2: the 6 entries are counted on no axis; `report.host_panels` owed; the cohort axis is already full with the host's own kinds, which the host draws only for a plugin that declares `report.unit_network` |
| `scprofile scaffold de` | writes nothing: a one-file Python plugin has no generated companion |
| `scprofile validate de` | 0 errors, 1 warning (`memory_gb_per_100k` without `memory_gb_base`); no accounting of upstream plots |
| `sch dev rules` | 4 held, 0 broken |
| `sch dev check --name de` (no plugin environment) | **exit 3**: 8 of 9 tiers ran, none failing - declaration, rules, contract, unit (110 suites), leak; fixture_a and fixture_b passed only as accepted refusals (`plan`: not ready in this installation), so **the plugin never ran** and `agree` compared nothing; **baseline could not run** (none recorded) |
| the same ladder with the plugin's interpreter given (`SCPROFILE_DE_PYTHON`) | **exit 2, `agree` FAILED.** The plugin ran on both shapes. Shape a contrasted `treated vs ctrl`; shape b, whose control sorts last, contrasted `untreated vs treated` - the control became the numerator - so every log2 fold change and Wald statistic is negated between the shapes. `agree` also compared execution measurements (CPU, wall, peak memory), which only a baseline names as unstable |
| what the fixture run was given | the fixture command passed `--control {condition}=ctrl` to both shapes, a literal fitted to shape a: shape b has no such level, the run recorded the control and refused nothing. The fixture design's covariate column was dropped by `--factor` and named nowhere in the plugin's caveats |
| `status --run <the fixture run>` | test 2 of 9: cores and promised answered; measure, cost and declared owe (one size of 2,000 cells); looked_at, audited, written, delivered owe |

**Missing, in short:** the contrast's direction (the plugin chose its reference by sort order and the
host's declared control never reached it); covariates (no part of the host knew the word: a
covariate column was either dropped by `--factor` or read as a factor); the plan's axis, position and
legend per figure; the accounting of the tool's own three plots; a fresh `version`; a baseline; and a
caveat that says the interaction "is not contrasted" while the code contrasts it.

### What the maker lacked, and the fixes (each with a suite that fails at `f5175ea`)

| defect | where it was | the fix | the suite |
|---|---|---|---|
| nothing asked a design-aware plugin how it orders a factor or what it adjusts for | the maker (DEVPOINTS) | a build stage `design`: `scprofile design <plugin>` names each site where a model is built or a contrast taken, and what is owed there | `test_the_maker_demands_the_design.py` |
| the host's control never reached a plugin; the plan had no `--control` | `planner.decisions_for`, `cli` | the contrast decision carries each term's control, its basis and the level order; `plan` takes `--control` | `test_the_contrast_is_read_against_the_declared_control.py` |
| a `--control` the design does not have was recorded and resolved to nothing | `cli`, `design_panel.control_for` | refused by name in plan and run (`planner.declared_problems`) | the same |
| no word for a covariate: dropped by `--factor`, or read as a factor | `inputs`, `planner`, `cli` | `--covariate`, resolved per contrast: modelled, or refused with the reason; every other column of the design table named as not in the model - under `--factor` only since the fix-up below, which found the columns it leaves out still dropped without a word | `test_a_covariate_is_modelled_or_refused_by_name.py` |
| a numeric column was dummy-coded, one coefficient per value | `inputs._term_columns` | a float column is one centred column | the same |
| a plugin ordered levels itself | no accessor existed | `ctx.levels(term, present)`, `ctx.model_frame(obs, terms)`; the design's sentences said once by the host | both |
| the fixture handed shape b shape a's control (`=ctrl`) and no covariate | DEVPOINTS `fixture` | `{control}` and `--covariate {role_covariate}` in plan and run | `test_the_maker_demands_the_design.py` |
| the inventory stage said nothing about how it is finished | DEVPOINTS | `finished_by` | read by the status |

**The plugin's answers**, all through the maker: `sch dev edit` for `inject` (`covariates`),
`state_version` 2, the corrected limit, and the figure plan (axis `cohort` - the plugin runs once
over the cohort - position and legend for all six entries; followers green every time); and the
`design` worksheet answered at the sites it named. On the two-shape fixture, with the plugin's
interpreter given, the shapes now agree on every number DE writes (`treated vs ctrl`, `treated vs
untreated`; the covariate modelled on both). Run on a synthetic 2x2 whose controls both sort last,
the plugin's table is bit-identical to the unmerged hand edit that first attempted this, on one
interpreter, and is the base fit reparametrised exactly as treatment coding predicts.

**Build 7 of 10** (blind: 5 of 9, the `design` stage added since). Still owed, all in the harness
half of the maker, so not fixable in this repository:
- the python extractor cannot see a tool whose plots are class methods or live in a submodule
  (`sch/dev/extract/python_package.py`), so `inventory` and `plan` stay part-way on the admission;
- the layout charges the host's own kinds to every plugin's budget, though the host draws them only
  for a plugin declaring `report.unit_network`, and requires every plugin's `host_panels` to equal
  the layout's list (`sch/dev/layout.py`): a pooled plugin's six plates are over the cohort budget
  by construction, and the trim would drop all of them, so it was not applied;
- the ladder's baseline tier fails a fixture run that was an accepted refusal (no products), and
  fingerprints a product's byte count, which moves with the digits of a timing; `agree` compares
  execution measurements wherever no baseline names them. A baseline recorded on a workstation is
  also the wrong machine for the cluster, so none is committed: the dev suite records it.

### The verifier's FAIL, and the fix-up (2026-11-09)

A fresh verifier replayed the 21 verb calls on `f5175ea` and diffed the result against the
branch: five hunks were the `design` worksheet's answers at the sites it named, and one was not -
the runtime caveat that had said the interaction was "not contrasted" was rewritten at a site no
verb and no worksheet named, under a comment claiming the worksheet had asked. It also found
`--factor` dropping every other column without a word, and a population with no sample at the
control contrasted between two other levels. Fixed in the maker, then answered through it:

| defect | where it was | the fix | the suite |
|---|---|---|---|
| a sentence about the design was answerable only by hand (GAP-C47) | the `design` worksheet | it names every `ctx.caveat`/`ctx.refuse` carrying a design word; `--answer` records the diff, `--confirm` binds a true sentence to the digest of its syntax, `--replay-into` rebuilds the plugin from the record. As first shipped (`35c6225`) a fit site was its whole loop or function, an insertion at a span's edge was admitted, and the replay trusted the record - the verifier laundered a doubled filter threshold, a zeroed selftest gate and an `out = out[:1]` through it. Since fix-up 2 `--answer` applies a change only inside a named site - a fit call's statement and the lines that define the names its DESIGN arguments read (`design`, `formula`, `contrast`, `design_factors`, `ref_level`, `reference`, `levels`, `metadata`), two hops back and above the line that reads them, or a statement and the comment block directly above it - inserting only strictly inside one; it refuses an answer that names no site, changes a fit call's other arguments, adds a statement binding a name the replaced lines did not bind as a design name, or carries a character another reader takes as a line break, and the replay admits every diff again | `test_the_maker_demands_the_design.py` |
| `--factor` left the other columns unnamed | `planner`, `inputs`, `cli` | the design table's columns are recorded and every one outside the model is named | `test_a_covariate_is_modelled_or_refused_by_name.py` |
| no sample at the control read `mid vs alpha` (GAP-C48) | the host's frame | the control stays as an empty level, so the replication check refuses the contrast, by name | `test_the_contrast_is_read_against_the_declared_control.py` |

`de` then answered the worksheet's 16 statements: three changed (the interaction caveat, the
not-interacted caveat - false of a fitted interaction spread over several coefficients - and the
multi-level caveat, which now names the control), thirteen confirmed with their reasons. The 21
verb calls replayed on `f5175ea`, then `scprofile design de --replay-into`, give the shipped
`kernels/de.py` byte for byte.

**Fix-up 2.** The verifier then laundered three hand edits through `--answer` (above). With the
sites narrowed, de's answers were re-recorded from the post-verb file: answer 1 now changes only
three lines that define what the fit reads - the frame (`ctx.model_frame`, the host dropping and
naming a covariate a population cannot carry), the formula (the estimable terms plus those
covariates) and each term's levels (`ctx.levels`) - where it had changed five regions of the loop;
answer 2 carries its comments inside the three statements. The table on a 2x2 rehearsal is
byte-identical to the one before, and the replay still rebuilds the shipped file byte for byte.

**Fix-up 3.** The verifier's next pass still got hand edits through, more narrowly: eleven form
feeds (or line separators) in an admitted comment shifted the diff's line indices against the
`ast` line numbers the sites are counted in, and an edit in no site was admitted; a fit site
followed every argument's names, so the configuration, the gene mask, `refit_cooks` and `alpha`
were answerable; a statement added beside a site line rode in with it. And two real design answers
two hops from the call were refused. Now: one line model (split on "\n" alone) and those
characters refused; only the design arguments' names, two hops back, each definition above the
line reading it, never a name the call reads as another argument; a fit call's other arguments
unchanged; an added statement binds only design names the replaced lines bound. The host tests a
covariate against the terms a subset can carry, so a population whose terms are confounded keeps
a covariate that varies within the term the fit keeps (`~ fa + weight`, not `~ fa`). de's record
replays under the tightened admission unchanged, byte for byte; no answer had to be re-recorded.

**Fix-up 4.** The admission held only where someone ran `--replay-into`, and nothing that gates a
commit did: a hand edit in no site (the cut of the hit counts) with an entry appended to the
record - the right digests, a site it does not touch - passed the suite, `scprofile check`,
`scprofile design` and the maker's status. The record now verifies itself wherever it is read, from
the shipped file alone: every diff undone, last first, to the first answer's `before`, each admitted
again with the sites it records; a forged entry, an inadmissible one, or a file changed outside its
declaration with no entry makes the `design` stage owe and the suite fail. Each answer keeps the
declaration it left, so the maker's verb may still edit the declaration afterwards. de's answers
were re-recorded through the mechanism to carry it: the same diffs, digests and sites, and the
same file byte for byte. What it does not guarantee, exactly: the content of a site line is not judged - a loop header binding a design name is a site line, so its iterable can change, and a side effect written into a design line or a caveat (`C.update(alpha=0.5)`) is admitted and recorded; the call's other arguments are held as syntax only, so their values can still move through such a side effect; a design definition can be deleted; and the declaration (`PLUGIN = {...}`) is the maker's verb's, not this record's. Review therefore reads every answer's diff in the record.

### What the next plugin (abundance) should test, blind

- `scprofile design abundance` before anything changes: does the stage name its fitting sites and
  the three debts, and does its migration answer them the way this one did?
- its sentences about the design: does the worksheet name every one that states what was or was
  not contrasted or modelled, and miss none a reader would take as such - the vocabulary is the
  maker's guess, and this is its first plugin it was not written against?
- the fixture with the plugin's environment: does `agree` now see a reference taken by a formula
  library's alphabetical default (the second way to choose a reference, not the first)?
- `--covariate` and the interaction: a plugin that fits one factor at a time must model the
  covariate or be named as not modelling it, and the plan must say which.
- whether a plugin whose own guard refuses the fixture's covariate is told apart from one whose
  model ignores it.
