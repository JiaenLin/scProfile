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
