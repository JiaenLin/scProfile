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

**Build: 7 stages done, of 10** (blind: 5 of 9, the `design` stage added since). Still owed, all in the harness
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

**Fix-up 5.** The chain had no fixed end: the verifier pushed the same hand edit (the up-count
cut, `lfc > 1`) under answer 1, re-derived every digest, and the record undid from the shipped file
to a doctored `before` and passed the suite, `scprofile check` and `scprofile design`; an empty
record returned ok, so a hand edit made before the first answer would have become the record's
base; run-time code inside `PLUGIN = {...}` passed; and a declaration the host could not load read
"not design-aware". Under the threat model stated for it - a builder with ordinary commit rights
making forward commits; rewriting history or moving the anchor is a diff review reads - the
chain's end is now anchored: DEVPOINTS `rules.held_out.spent` names the commit each spent
plugin's blind record was taken at (`de: f5175ea...`, the whole hash), and the first answer's
`before`, or with no answer the shipped file, must equal the plugin at that commit everywhere
outside its declaration, read with `git show` or, on a node with no `git` (the cluster's compute
nodes), from the checkout's own object store - loose objects and packs with their deltas, a linked
worktree's `.git` file, alternates. Where the commit cannot be read - a shallow checkout, no
repository - the base is not established and the check fails. `--answer` refuses a plugin with no
anchor and a first answer on a file that differs from it. The declaration must be a pure literal;
one that is not, or that the host cannot load, makes the stage owe by name. The suite's "the last
answer made the file that ships" compares outside the declaration, so the maker's verb may edit it
after the answers (proved with `sch dev edit` on a copy: the stage and the suite pass; a hand edit
outside the declaration fails both). The fixture's `execution_record` (harness W019) is declared
here too: the fourteen globs of fields a run records about its own execution - the resources given,
the process tree's measured use, the core budget and the models fitted to them, the resource
declaration as the run read it, the scheduled shares - which `agree` and the baseline report and
never judge; no DE number is among them. de's record and `kernels/de.py` are unchanged, and the 21
verb calls on `f5175ea` plus `--replay-into` still rebuild the shipped file byte for byte.

**W032 (W013's residue: the declaration guard).** The final re-check of fix-up 5 found the guard open by one-line variants. The record check folded and swapped the declaration's whole LINES while its literal check read only the assignment's VALUE, so a statement on the declaration's first line (`x(); PLUGIN = {`) or its last (`}; <code>`) ran on every import and was compared nowhere - a payload on de's closing brace doubled every fold change, on both fixture shapes, with the stage, the suite, `scprofile check` and the ladder's `agree` green. The host kept the LAST top-level `PLUGIN =` and the check read the FIRST, so a second binding left the stage at "not design-aware" (exit 0, the job's first step), past the record check; a key `literal_eval` rejects with TypeError crashed discovery; and `scprofile check` never ran the record check at all. Now one reader (`kernels.read_declaration`) serves the host, the record check, the literal check, the version line and the landscape's forecast: `PLUGIN` is bound once, in any syntax and at any depth the import runs (`global` included), by a top-level `PLUGIN = {...}` alone on its lines, a pure literal dict; anything else - and whatever the parser or `literal_eval` raises, a file that is not UTF-8, a `needs` that is not a mapping - is a sentence the host keeps (`declaration_error`), validate names first, and the stage owes. The record check holds every file of its chain to the same reader, runs for every plugin, fails closed on anything a record holds, and is a row of `scprofile check`. `tests/test_the_declaration_is_one_statement_alone.py` runs every attack of the re-check and twelve variants through the real commands on a clone (78 checks; 64 fail at b39ca4a). What it does not guarantee, as before: the declaration's VALUES are the maker's verb's, not this record's - a literal changed by hand reads exactly like one the verb wrote - and a binding no syntax names (`globals()[...]`, `exec`) is code outside the declaration, which only a plugin with a record refuses. de's record, `kernels/de.py` and DEVPOINTS are unchanged.

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

---

## 2. `abundance` (pertpy / scCODA) - blind record taken at `b5f646a`

**Venue.** The workstation; the harness's maker; the plugin's interpreter a private virtual environment built from
this repository's shipped lock's exact pins (pertpy 1.0.4, statsmodels 0.14.6, numpyro 0.21.0, jax 0.7.0, anndata
0.12.19, mudata 0.3.10; Python 3.12); both cohort projects' generated word lists for the leak tier, one at a time.

### The blind record

| what was run | what the maker said |
|---|---|
| `sch dev convert status --name abundance` | HELD OUT banner. **build 5 of 10**: environment, contract, defaults, references, judgement done; **freshness STALE** (`version` 0.2.0, 14 commits since it moved); **design OWES**; inventory PART and plan PART (`wraps.plots_unreviewed`); layout todo. **test 0 of 9** |
| `inventory` | exit 0, **0 functions** in `pertpy.pl`. Measured in the same environment: `pertpy.pl` is an empty module in 1.0.4 and the tool's plots are seven `pertpy.tl.Sccoda.plot_*` methods. An empty plotting submodule ends the extractor's search, so seven plots read as none, with exit 0 (the harness's extractor) |
| `plan`, `plan --migrate` | 5 entries, each lacking an axis, a position and a legend; `--migrate` asks the axis (it no longer defaults to `unit`) and still defaults `position: contrast` |
| `layout` | exit 2: 5 entries on no axis; `report.host_panels` owed |
| `references` | `references: {}` declared, "nothing to do". The method's paper is only free text in `wraps.cite`: no stage asks for a DOI, its title and year, or an exact pin of the wrapped tool (`pertpy>=0.9,<2` is a range) |
| `defaults` | reads only the constructor `Sccoda()`; `prepare`, `run_nuts` and `set_fdr`, which carry the method's defaults, are not read |
| `contract`, `scaffold`, `validate` | produces 2 of 2 and figures 5 of 5 matched; writes nothing (one file); 0 errors, 1 warning (`memory_gb_per_100k` without `memory_gb_base`) |
| `scprofile design abundance` | **OWES**: 2 fit sites (`prepare(formula=...)` in `run` and in the selftest) and 12 statements; owes `ctx.model_frame`, `ctx.levels` and `inject` `covariates`. Five of the twelve are not about the design: scCODA's reference is a POPULATION, so `reference` matched three sentences about it, `design` a palette sentence, `term` the sampler's sentences |
| `sch dev rules` | 3 held, 0 broken |
| `sch dev check --name abundance` (no plugin environment) | exit 2: contract and leak FAIL (comments carrying a cohort's levels and its measured size); unit green, 123 suites; fixture_a and fixture_b ok **only as accepted refusals**, so the plugin never ran; the plan named the fixture's covariate as NOT MODELLED (`inject` declares no `covariates`) and the design as main effects only |
| the same ladder with the plugin's interpreter given | **the plugin ran on both shapes; `agree` FAILED.** Shape a's effect column sums +3.462 (log2 fold change +4.548); shape b's sums -3.413 (-4.477): **the sign is reversed**, because shape b's control sorts last and the formula library's alphabetical default made the other level the base - GAP-039 by its second route, which section 1 asked this migration to look for. The figure sources F1 and F2 name columns by the factor and its levels, so the shapes' columns differ by construction; the sampled quantities differ between the shapes in the second or third decimal (one seeded chain on a relabelled table is not the same chain) |

**Missing, in short:** the contrast's direction (the formula library chose the base level); covariates (none can be
handed to it); a two-factor fit with an interaction, or a refusal of one by name (each factor is fitted alone); a
source that exists (DOI, title, year) and an exact pin; a fixture tier that refuses a plugin that never ran; an
inventory that sees class methods behind an empty plotting submodule; column names that do not carry the user's
vocabulary.

### What the maker lacked, and the fixes (autodev W055; each with a suite that fails at `2e5b95a` or before)

- **A source that exists** (`cd3d895`, `1c9b978`): the build stage `source` and `scprofile source <plugin>
  --resolve`; abundance, de and cellchat declare a DOI with its record's title and year, and an exact pin, through
  `sch dev edit --set` (`tests/test_a_source_exists.py`).
- **The fixture accepts no refusal** (`2e5b95a`), and **a refusal inside `run()` fails it** (`2db432b`): the run's
  STATUS.json reads `ok` and `run` exits 0 when a plugin refuses inside `run()`, so the fixture command's last step is
  `capacity --all-ok`, which reads every instance's `out.json` (`tests/test_a_refusal_inside_run_fails_the_fixture.py`).
- **The record check names a planted `version`** (`2b2e9f8`): once `sch dev edit` raised the version past an answer,
  that answer's version row was matched only from the record's `version`, and a planted value was refused as a line
  changed by hand.
- **The base level is the host's** (`2cb5472`, abundance's design answer 3): the fit's formula names `ctx.levels`'
  control as patsy's Treatment reference; the plan's terms meet `min_samples_per_level`; the model caveat names a
  dropped term and an interaction asked for and not fitted (`tests/test_abundance_reads_the_hosts_control.py`). On the
  fixture the effect table now agrees between the shapes.

### What the maker still cannot reach (the next plugin should test, blind)

- **A level order the plugin takes itself, outside a fit.** abundance's figure sources F1/F2 sort a factor's levels
  alphabetically, so on shape b their columns come in another order and F2's reference ratio is inverted (1.070 against
  0.935); `agree` fails on exactly these three lines. The worksheet names fit calls and statements, not a `sorted()` of a
  design term's levels, so no answer can change them.
- **The frame a positional data object carries.** pertpy reads its formula against the AnnData passed first to
  `prepare`, built outside every site: `ctx.model_frame` and covariates cannot be answered, so abundance declares no
  `covariates` and the plan names each NOT MODELLED by it, with the reason. An answer cannot add a statement either (an
  added `ctx.` call binds `ctx`), so a new sentence goes into an existing statement.
