# Anatomy of a scProfile Run

*Every layer of one whole run, every step and every element, as the code does it — read from scProfile d933b13 and harness 4658b1a on 2026-09-16 (harness ADR-0026, the open items). Figures in italics are measured on PBS 712314 (the run for review); everything else is read from the source. Written for a cold agent or maintainer who has to read a run without having built it. Nothing simplified away; where a step is a judgement, a limit or a debt, it is said as such. When the code moves, this file is the one to move with it.*

## 1. The map: one run directory

A run is a directory under `~/projects/SAMBO/runs/scprofile/04_profile/` named by its key `<stamp>__scprofile-<tool commit>__04_profile__<kind>` (`rerun`, `written`, `audit`). Four trees are the run's own; everything else at the top is written by a job, and every reader that walks a run now walks only the four (`manifest.OWN_TREES`).

```
<run>/
  RUNKEY.txt  JOBID.txt                 the submitter's (before the job starts)
  RUNNING.txt → SEALED.txt | FAILED.txt  the job's seal: exit, jobid, host, finished, reference,
                                        tool_commit_expected/actual, missing=, products_expected=, incomplete_checks=
  logs/pbs.log  logs/fixture.txt  logs/maker_status.txt      the job's
  cache/                                 the job's XDG/matplotlib cache
  fixture/                               the fixture gate's scratch (two synthetic cohorts, their runs)  ← not the run's
  STATUS.json  RUNNING/SEALED/FAILED.txt the tool's status contract for `run`
  STATUS.<cmd>.json  SEALED.<cmd>.txt   the same contract for every reader command asked of the run
  report.json                            the run's whole record (kernels, design, units, models, diagnoses …)
  RUN_CARD.json                          the run's verdict per instance (ok / suspect / failed)
  CAPACITY.json                          what the run delivered, counted from its own trees
  README.md                              written last, by inspecting the directory
  kernels/cellchat/
    <unit>/                              one directory per instance (18 on the cohort)
      in.json  out.json                  the contract in and out
      cellchat_db.R/.log/.csv            the database export
      cellchat_expr.mtx(.genes)  cellchat_meta.csv   what R was handed
      cellchat_R.R  cellchat_R.log       the unit script (companion + body) and its log
      cellchat.log  figure_context.tsv   the plugin's log; the host's colours, stamp, axis
      objects/cellchat.rds  objects/cellchat.inference.txt   hard links into the store
      tables/  figures/  arrays/  obs/   the outputs
      estimationNumCluster__*.pdf        CellChat's own side effect
    compare/<contrast>/ … compare/_across_arms/   the comparison phase (below)
    compare/phase.json
    FIGURES.txt  WRITING_BRIEF.md  AGENDA.md  PAPER.cellchat.md  PAPER_CLAIMS.cellchat.jsonl
    FIGURE_REVIEW.jsonl                  the looks and the answers (once a looker has looked)
  report/
    index.html  cellchat.html  cellchat_by_arm.html  cellchat_profile.html  cellchat_panel.html  cellchat_paper.html
    panels.json                          every host panel's audit and repairs
    figures/<axis>/<subject>/NN_<what>.png  + figure_NN.png composites + cellchat_figures.json
  tables/cellchat_<table>__<unit>.csv    every registered table copied out per unit
  objects/cohort_profiled.h5ad           the object with every merged column
```

Beside the runs, not inside one: `_cache/cellchat/<unit>/<span key>/objects/<param key>/` — the store (§10).

## 2. Layer 0 — the plugin's declaration, what the run reads

`kernels/cellchat.py` is one file: the `PLUGIN` dict (the declaration), four R scripts as strings, and the Python `run(ctx)`, `compare(ctx)`, `selftest(ctx)`. It is maker output: the maker writes it through `sch dev edit` (declaration by source span), the tool's own verbs (`capacity --declare`, `scaffold --force`, `layout --apply`), or a cold author's pasted answer — never by hand.

| element | what the run reads from it |
|---|---|
| `name, api, version, state_version` | the api is checked by the entry point before anything runs (mismatch → `refused`); the version is the reuse key and is bumped once per edit by the maker's verb (cellchat is 0.42.0) |
| `summary, when_to_use, cannot_show` | printed on the page and in the brief; `cannot_show` is the limits paragraph under the plugin's results (an empty one is an ERROR) |
| `requires / env` | the environment the builder resolves (shared groups: `scprofile-env-<hash>`); the run refuses at its door if it is not built where `--prefix` points |
| `inject` | required capabilities (`lognorm`, `label`, `organism`): the plan checks them against the object; the entry point refuses when one is missing |
| `produces` | the outputs, in the readers' grammar: `tables/name`, `slot[name]`, a trailing `?` for optional. Read by the drift check per unit, and by the host to register every declared table the R wrote |
| `cache` | `span`: the two marker lines around the inference recipe; `keyed_on`: the config keys in the object's key. Read by the forecast and by the host to key the store directory |
| `config` | every parameter with type, default, bounds, help (`min_cells 10, type, trim, population_size, nboot, thresh, min_coverage…`); resolved once per instance against `--params`; a default missing is an ERROR unless `required` |
| `cost, cores, memory_gb_base, memory_gb_per_100k` | the executor's declaration: `high, 2, 3.2, 14.3`. The scheduler sizes waves and memory from them; the test stages hold them against what the run measured |
| `references` | CellChatDB human and mouse, tier `bundled`: present by construction, no directory needed |
| `wraps, upstream, native_plots / report.skips` | the wrapped tool, its docs, changed defaults, what is deliberately unused; every export accounted for or the validator counts it |
| `report.figures` — the plan | 24 entries. Each: `id`, `kind`, `drawn_by` (tool \| plugin), `fn` (the upstream function), `axis` (unit \| sample \| group \| contrast \| interaction \| cohort), `position`, `at_most`, `items`, `file`, `expr`, `when`, `args`, `device`, `w`, `h`, `legend`; `generated: False` for a side effect the tool writes itself. The companion draws each at its `.draw("id")` site; the layout counts files per axis against the budgets; the promise reader expects each |
| `report.host_panels`, `unit_network`, `comparison_stats`, `provides_evidence` | what the host draws for this plugin (across_design, unit_presence, unit_totals, interaction), the edge table it reads, the comparison table, the evidence kinds |
| `kernels/cellchat.draw.R` | the companion the maker generates from the plan: the drawing protocol (`.draw`, `.draw_all`, colours, stamp, axis guard, ceilings, `when`), prepended to every R script the plugin launches |
| `kernels/cellchat.signatures.json` | CellChat's 43 exports and their formals, recorded once on the cluster; the validator refuses an argument a function has not got (33 of 43 have no `...`) |
| the R strings | `_R_CAP` (the core share, capped first), `_R_DB` (database export), `_R_RUN` (one unit: inference + the unit plates), `_R_COMPARE` (one contrast), `_R_COHORT` (across arms: totals, interaction) |

The maker's *build* stages, read from source alone: environment, freshness, contract, defaults, references, inventory, plan, layout, judgement (the last runs `scprofile validate`). Its *test* stages need a run (§9). After any edit through the verb, the followers the tool declares run in order: `validate`, `scaffold --force`, the plan baseline re-recorded, the portability suite, the R and Python free-name checks; the state after is printed only when none refused.

## 3. Layer 1 — the job

Written by `sch dev job --ref <reference run> --redraw --plugin cellchat --predict "…"`; validated by `~/tools/hpc-site/validate.sh`; submitted by `jobs/submit_rerun.sh`, which makes the run directory, writes `RUNKEY.txt`, checks the tool tree's `HEAD.txt` equals the job's expected commit and that the tree carries exactly one kernel, then `qsub`s. Everything is authored off-cluster and pushed; the cluster trees (`~/tools/single-cell-harness`, `~/tools/scProfile-cconly`) are pulled or re-exported at a named commit.

- **E1** — **Emission refuses** when the plugin's build owes (a stage not done, or a judgement stage whose validator refuses) — `--anyway` emits with a header note. The header carries the reference, the prediction, the tool commit, every flag carried from the reference's own recorded argv one per line, the flags a redraw dropped (`run.redraw_drops: [--no-cache]`), and the cache forecast (§10).

- **E2** — **Products expected** are read from the reference's own `STATUS.json` record (282 on this cohort); on a redraw figures are not expected. `fixture/`, `logs/`, `cache/` are never products.

- **J1** — **The seal trap.** `RUNNING.txt` at start; at exit `SEALED.txt` only if exit 0 and every expected product is present, else `FAILED.txt` with `missing=`. A killed job seals FAILED. `incomplete_checks=` names a gate that could not run.

- **J2** — **The checkout has not moved:** the tree's `HEAD.txt` (or `.git`) must equal the expected commit, else exit 3.

- **J3** — **The code that runs is the tree that was verified:** the tree goes first on `PYTHONPATH`; the module is asked where it imports from and refused if elsewhere. Thread pools are pinned to `NCPUS`; the cache is `$RUNDIR/cache`.

- **J4** — **The fixture gate** (§4) — `run.fixture_first` in the tool's DEVPOINTS. Exit 0 continues; exit 3 (could not run) and exit 2 (failed) both refuse the cohort with exit 4 and different words.

- **J5** — **The tool runs:** the reference's argv with only the destination changed — `scprofile run --h5ad cohort_integrated.h5ad --out <run> --kernel cellchat --prefix …/env --design design.csv --label-key cell_type_forced --sample-key sample --batch-key batch --counts-layer counts --lognorm-layer lognorm --embedding X_scanvi --layout X_umap_scanvi --organism mouse --assay nucleus --timeout 21600 --control age=young --control diet=chow`. Not piped, not teed; the exit code is read before the trap uses it.

- **J6** — **What follows a run**, declared in `run.after`: `status --out`, `capacity --promised`, `capacity --memory`. Each exit is a verdict printed as `after: exit N`, not a failure of the run.

- **J7** — **The maker's status** of the new run, into `logs/maker_status.txt` (`sch dev convert status --run`): the nine build stages and the nine test stages (§9).

## 4. Layer 2 — the fixture gate

`sch dev check --only fixture_a --only fixture_b --fixture-dir $RUNDIR/fixture`, with `SCH_DEV_PREFIX` = the reference's `--prefix`, under the tool's host interpreter.

- **F1** — The two-shape fixture is generated (seed 20260906): one synthetic cohort of 2000 cells × 520 genes, 6 populations, 7 design rows (6 samples with cells, one without), one factor `ctrl/treated`, written twice — shape *a* with the usual column names, shape *b* with every one of the seven roles renamed (`sample→library_id, cell_type→celltype_final, counts→raw_counts, condition→arm, batch→chip…`). The marker blocks carry real ligand–receptor symbols (CXCL12→CXCR4, TGFB1→TGFBR1+TGFBR2, …), ligand in one population's block and every receptor subunit in another's, so a communication method finds directional signal; the counts are the neutral fixture's, byte-identical to before the rename. Sixteen structural hazards are built in (an empty cell, an empty gene, a constant gene, a duplicated barcode, a gene named like a column, NaN in a numeric column, a covariate constant within an arm…).

- **F2** — Per shape, in parallel, the tool's `fixture.command`: `validate cellchat` → `plan` (told the shape's role names, `--factor` the one factor, organism human) → `run` (the same flags) → `capacity --promised` on that run. A declared refusal ("are not ready in this installation") is accepted and ends the command list, with the refusal's own lines kept in the log; a crash is not.

- **F3** — *Measured on 712314:* both shapes ok in 147 s. Eight units each (6 samples, 2 arms): seven inferred with status `partial` — 80 of 3,233 database interactions (2.5%) testable on the synthetic genes, below `min_coverage 0.5`, and the caveat says so; one sample (S12) `refused`, CellChat's own error in `computeCommunProb` recorded verbatim under `absent`. 23 unit plates and 10 contrast plates per shape; `promised` done with `compareInteractions` waived by name — an interaction-axis plate the one-factor design never launches.

> What this gate proves and does not: the plugin runs end to end on a cohort it was not fitted to, in both column vocabularies, and draws every plate it promised there. It cannot exercise the interaction axis (one factor) — `sch dev fixture --crossed` exists for that and is not in the job yet — and it says nothing about biology.

## 5. Layer 3 — `scprofile run`, step by step

Everything below runs inside the status contract: `STATUS.json` is written at the end with status `ok | failed | refused` (an instance's own `out.json` can also say `partial`), the exit code, a headline, the argv, the tool commit, the wrapped versions, and the run's own product list.

- **R1** — **The door.** For every requested kernel the interpreter is resolved under `--prefix` (the shared group environment first, then the per-plugin one, then `$SCPROFILE_<NAME>_PYTHON`). A kernel with none: "PREPARATION: N plugin(s) are not ready in this installation; nothing was launched", `scprofile: no plugin ran` on stderr, exit 1, FAILED.

- **R2** — **The object is read** (anndata) and described: how each role was decided — label, compartment, sample, batch, counts layer, lognorm layer, embedding, layout, organism (probe genes' case), assay, constraint, sentinels (annotator markers such as EXCLUDED/UNRESOLVED, replaceable with `--sentinels`), and the directory leads searched for reference files.

- **R3** — **The design** is read from `--design`: keyed on the column named by `--sample-key` when the table has it, else a known name (sample, sample_id, library, batch, donor), else refused naming `--sample-key`; every other column is a factor unless `--factor` names the factors the run is about (the other columns stay in the rows for the confound panels); a sample in the object with no row is refused by name; `--control FACTOR=LEVEL` fixes each factor's reference level. Without a table the design is derived from columns constant within every sample, and said to be derived.

- **R4** — **The units are resolved, group first.** `units.resolve`: the group axis is every arm of the design's factors (the four cells of a 2×2, named `<levelA>_<levelB>`) plus, for a crossed design, the marginal pools of each factor (each level over the other factor pooled) — the sides a marginal contrast needs; the sample axis is every sample (10 here). *18 units on this cohort.* Each unit's members, axis, cell count and the populations it contains are recorded once, where the object is open; a population absent from a unit is the host's to say.

- **R5** — **The tool's fingerprint** (the code as it was when the run started) is taken and re-checked before every instance; a tree that changes under a run stops it.

- **R6** — **The plan's decisions** are computed by the planner's own function (settings per plugin from the design; e.g. which parameters the design decides) and printed with their provenance (default / decided / overridden by `--params`).

- **R7** — **The schedule.** Budget = `--cores` or the machine's; memory per instance = base + rate × the cells that instance touches, from the declaration; `schedule` packs instances into waves by cores and memory (*18 instances in 1 wave, 64 cores*). The plan line and the per-instance timeout are printed before anything runs.

- **R8** — **A wave runs.** Prerequisites are re-checked at the start of each wave. Admission is by cores, not count: a `ResourcePool` of permits; each instance thread takes its share before spawning. For each instance the host writes `in.json` (§6) and launches the plugin's entry point in the plugin's own interpreter with the core share exported to every thread pool.

- **R9** — **One instance failing does not take the wave.** An environment failure is the one class the run repairs: it rebuilds the environment once and relaunches, naming what it rebuilt; a success after a rebuild is itself recorded as a finding.

- **R10** — **Per instance, when it returns:** the `run → declare` edge — `declaration_drift` (what `produces` promised vs what the manifest registered, per slot, `?` and globs honoured) and `figure_drift` (what `report.figures` promised vs what was drawn, minus what the unit itself declined by design: a marginal pool draws nothing, a group unit draws no sample plate); each mismatch is a diagnosis in `report.json`. Reuse is recorded, never silent.

- **R11** — **Merge.** Per-cell outputs (`obs`, `obsm`, `layers`) are merged into the object by barcode, refusing shape mismatches; every registered table is copied to `tables/cellchat_<table>__<unit>.csv` (*6 tables a unit now: ccc_edges, composition, pathway_prob, centrality, rank_net, net_embedding*); objects are hard-linked into `objects/`. Payloads are folded; failed units named.

- **R12** — **The comparison phase** (§7).

- **R13** — **The models.** From every instance's own measurement (`measured` in `out.json`: process-tree peak sampled every second, cgroup peak where readable, CPU seconds, wall, cells): memory fitted as base + per-100k-cells over the 18 points, cores as mean/peak, cost as a band; each carried in `report.json` beside the declaration.

- **R14** — **Across the design:** `by_arm` for every per-cell column (quantiles and compositions, description only); the concordance of one plugin's number against another's; which pages the constraint on use binds (from the factors a page actually shows). Controls, the section spec each plugin declared, what was reused and from where, the object the plugins actually read.

- **R15** — **`report.json`** is written (keys: kernels, design, units, unit_axis, unit_members, label_by_unit, label_total, schedule, seconds, memory_model, cores_model, cost_model, diagnoses, by_arm, concordance, constraint_*, controls, reused, repaired, ran, skipped, partial, merged, object, input, input_read_by_kernels, report_spec, summaries, cannot_show, sentinels, timeout, tool_commit, version, state_version, status). Then `RUN_CARD.json`: per instance ok / suspect / failed with reasons, the worst as the run's verdict; `unknown` when nothing ran.

- **R16** — **The pages and the figure set** (§8).

- **R17** — **The exit standard** (`_judge`) measures every rendered page — overview, arms, repeats, count, and the rest of `standard.py` — prints the verdict beside the path and never refuses or rewrites.

- **R18** — **`README.md`** last, by inspecting the run's own files; a handed-in section is carried in and rendered (`_carry_section`); `CAPACITY.json` records what the run delivered (units, plugins, figures by kind, tables, contrasts, documents, plots written/failed, cache hits, panel plates/gaps, claims, failed units) and says so if it delivered less than the run before; exit 0, or 1 with "no plugin ran".

## 6. One instance, inside

### 6a. `in.json` — what the host hands over

`h5ad` (the object, or a re-encoded copy the plugin's anndata can read), `out_dir`, `keys` (every role → column), `organism`, `assay`, `design` (the table's path), `references` and `reference_specs`, `params`, `upstream` / `upstream_units` (other plugins' outputs by unit), `sentinels`, `provenance`, `resources` (`cores`, `memory_gb`), `unit`, `unit_members`, `unit_axis`, `figures_for` (which unit axes the host wants drawn), `constraint`, `cache_dir` (`_cache/cellchat/<unit>/<span key>`), `figure_context` (the run-wide colour map and stamp), `contract`, `host_version`.

### 6b. The entry point (`scprofile/_entry.py`, run as a script in the plugin's interpreter)

- **I1** — reads the object; subsets to the unit's members (a unit with no cells → `refused`); drops sentinel-labelled cells and says how many; excludes cells with NaN in the embedding and records the caveat

- **I2** — checks the plugin's `api` against the host's; resolves `config` against `params` (a refused parameter → `refused`); builds the `Context` (the object, keys, out, cores, memory, unit, members, plan ids, design, sentinels, config, figure context, the companion text)

- **I3** — required capabilities missing → `NOT CALLED`, status refused; else `run(ctx)` under a process-tree sampler (memory and CPU every second)

- **I4** — after `run` returns: every table `produces` names that is on disk under `tables/` is registered; `out.json` is written by `manifest.write_output` — status, headline (refutations first), obs/obsm/layers/tables/figures/objects (paths relative to the instance), absent, caveats, contradictions, metrics, config as resolved, `not_drawn_by_design`, `measured`, the contract version

### 6c. cellchat's `run(ctx)`

- **C1** — refuses without a label or with fewer than two populations after `ctx.populations()` (the host's roster: a population below `min_cells` is dropped and named)

- **C2** — `_R_DB`: exports the database for the organism (`CellChatDB.mouse`) to `cellchat_db.csv`; coverage of the object's genes against it is computed; below `min_coverage` the run refuses or says the result will be thin

- **C3** — **the matrix store** (`ctx.cache("matrix")`): the expression matrix and metadata written once per unit as `.mtx`/`.csv` for R, reused when the digest matches

- **C4** — **the object store**: `pkey` = sha1 of the six inference parameters (type, trim, population_size, nboot, thresh, min_cells) → `ctx.cache("objects", pkey)` — under the host's span-keyed directory

- **C5** — `_R_RUN` (§6d) is launched with the matrix, meta, database, parameters, the edges path, the figure context, which plates this unit draws

- **C6** — back in Python: the edges table is registered (`ccc_edges`), the composition table (populations, cells, dropped, the floor and why), metrics (significant edges at `thresh`), the headline and caveats

### 6d. The unit script `_R_RUN`

- **U1** — the core share is capped before `library(CellChat)` can start anything (`_R_CAP`); reticulate is pointed at the environment's own Python; the drawing protocol (the companion, prepended) is configured once

- **U2** — the store: `cellchat.rds` and its stamp `cellchat.inference.txt` = md5(matrix) | md5(meta) | database | the six parameters | the CellChat version | md5(the recipe span). Stamp equal → `reusing the saved CellChat object; inference skipped` (*18 of 18 on 712314*); else the recipe

- **U3** — **the recipe** (between `# --- RECIPE START ---` and `END`): `createCellChat → subsetData → identifyOverExpressedGenes → identifyOverExpressedInteractions → computeCommunProb(type, trim, population.size, nboot) → filterCommunication(min.cells) → computeCommunProbPathway → aggregateNet → netAnalysis_computeCentrality`; between the last two, the four side tables the tool's own downstream quantities give (pathway probability, centrality, rank-net, network embedding), each wrapped so one failing costs its table and not the instance

- **U4** — saved by rename, the stamp last; older generations that nothing holds are evicted; the instance keeps a hard link (`objects/cellchat.rds`) so the run stands without the store

- **U5** — **CellChat's own plots, drawn by CellChat** through the plan: `.draw("native_circle_weight")`, `native_heatmap_count`, `native_signalingRole_scatter`, `native_signalingRole_heatmap_out`, `native_patterns` (k fixed at 3, said so), the embedding through the environment's UMAP; each site checks the entry exists, the unit's axis matches the entry's, the ceiling, the `when`; a plate not drawn is said and why. The tally last: `NATIVE PLOT TALLY: n written, m failed`

- **U6** — the edges written to `tables/ccc_edges.csv`; CellChat's rank-estimation PDF lands beside as its own side effect (`generated: False` on the plan)

## 7. The comparison phase

- **P1** — The pairs come from the design and the controls: on a 2×2 cohort the two marginal contrasts (`<A>`, `<B>`), the four simple effects within strata (`<A> | <B> = <level>`, one per level of the other factor, each way), and `_across_arms` for the interaction — *7 directories*.

- **P2** — Each launch runs the plugin's `compare(ctx)` in its own environment with two units' output directories, at the plugin's declared core share (2); launches run pooled, `at_once = cores // share` (*32 at once; the phase 2 min 45 s*); `compare/phase.json` records the share and the count; each launch writes `in.json`, `out.json`, `figure_context.tsv`, its R script and log, `removals.csv`, `tables/`, `figures/`.

- **P3** — `_R_COMPARE` (one contrast): the two saved objects are aligned before merging — a population only one arm has is removed from the comparison and recorded by category in `removals.csv`; `mergeCellChat`; then by the plan: `nativecmp_diff_heatmap_count/weight`, `nativecmp_rankNet_stacked` (CellChat's between-arm test, the numbers to `tables/rank_net_comparison.csv`), `nativecmp_signalingRole_scatter_pair`, `nativecmp_signalingRole_heatmap` (outgoing and incoming, one colour scale), `nativecmp_bubble_comparison`, `nativecmp_barplot_count` (ranked before it is cut, the ceiling the declaration's), `nativecmp_rankSimilarity_functional`, `nativecmp_aggregate_circle` and `nativecmp_chord_cell` per pathway under their ceilings. The tally last.

- **P4** — `_R_COHORT` (across arms, the interaction): every arm's object; `compareInteractions` (totals per arm with each animal as a point, count and weight) and the same per 1,000 cells; the interaction on both scales — per-pathway flow within each level of the other factor from `rankNet`, additive (`nativecmp_interaction_flow`) and log (`_flow_log`), the interaction matrix, the ligand–receptor level (`nativecmp_interaction_lr`, `_lr_scatter`); no test for a difference of differences exists and none is claimed; its tables (`nativecmp_interaction__*.csv`, alignment) beside the figures.

- **P5** — The host's own comparison panels are drawn from the plugins' tables (diff matrix, flow compare, role shift, unit totals, presence…), each through one audited save whose record goes to `report/panels.json`.

## 8. The record and the pages

- **W1** — `report.write_all` → per plugin `write_kernel`: `cellchat.html` (the plugin's page: overview, arms, contrasts, the interaction, limits), `cellchat_by_arm.html` (each arm's pooled fit), `cellchat_profile.html` (per sample — filed apart because a page carrying one plot ten times hides its result), the per-unit appendix; every host panel audited and repaired (the column fit, the stamp placed from the rendered box, the re-solve).

- **W2** — **The figure set** (`figureset.build`): every plate the pages placed and every per-unit plate on the plan copied to `report/figures/<axis>/<subject>/NN_<what>.png`, laid into lettered figures (`figure_01…16.png`, `figure_S01…S20.png`) with legends composed from the entries', indexed in `cellchat_figures.json` — *122 plates in 16 figures and 20 supplementary*. Derived, never drawn.

- **W3** — `write_index` → `index.html`; then per plugin: `ensure_section` (a section composed from the run's tables when none is authored — `PAPER.cellchat.md`; an authored one is never overwritten), `paper.render` → `cellchat_paper.html`, the brief `WRITING_BRIEF.md` (the design's questions, the contrasts, the figure list `FIGURES.txt`, the skill and the template), the agenda `AGENDA.md` (the run's tasks in the stations' own commands, outstanding count printed), the panel gallery `cellchat_panel.html` from `panels.json`.

- **W4** — The status contract closes: `STATUS.json`, `SEALED.txt` or `FAILED.txt` for the `run` command; the job's own seal (§3 J1) is a second, outer one.

## 9. Layer 4 — the readers after the run

| reader | what it reads and decides | *on 712314* |
|---|---|---|
| `scprofile status --out` | the run's own status files; owing stations | exit 0 |
| `capacity --promised` | the plan's promise (each entry's files per axis occurrence) and the native accounting's promise (each used export produced a file somewhere); a promise on an axis the run's directories show no occurrence of is waived by name; the other way: files under `kernels/` accounted for by nothing (the host's panels excepted) | done: 35 declared upstream plots, every one a file |
| `capacity --memory` / `--cores` / `--cost` | the fitted model against the declaration; owes when declared < fitted; `--declare` writes the envelope (raises a term the fit exceeds, keeps one it does not) | 3.2 + 14.3 at or above the fit |
| `capacity --drift` | the declaration diagnoses in `report.json`, each distinct drift once with how many units said it | no drift |
| `capacity --out RUN --against REF` | what the run delivered against another run, on the run's own trees: REGRESSION / gain per count | one gain: tables 214 → 286 (the four side tables registered) |
| `sch dev convert status --run` | the maker: build 9 stages from source; test 9 stages by running each stage's command against the run: measure, cores, cost, declared, promised, looked_at (station 7), audited (6b), written (8), delivered (9) | build 9 of 9; test 5 of 9, `looked_at` next |
| `scprofile next` / the agenda | the next command for the next station, in the run's own words | the lookers |

## 10. Layer 5 — the store and the forecast

`_cache/cellchat/<unit>/<span key>/` beside the runs: `<span key>` is a 10-hex digest of the declared inference span in the tree that ran, so versions of the inference coexist and a run of another span writes beside, never over; under it `matrix/` (the matrix store) and `objects/<param key>/cellchat.rds + cellchat.inference.txt`. The stamp inside still decides validity (§6d U2). Disposable: deleting it costs time and nothing else; `scprofile cache --out RUN` reports it (files, bytes, what clearing would free, hard links counted once), `--clear [--older-than]` removes.

**The forecast** (`scprofile cache --forecast --plugin cellchat --out REF --root TREE`, printed by the verb after an edit and written into the job's header): the tree's span and keyed parameters against the reference run's `tool_commit` via `git show`; HIT or MISS with the reason; MISS once when the store's key itself changed since that commit. It is relative to the run named — it cannot read the store — so a HIT holds short of the cache being cleared, and a MISS may still hit if a run since then wrote objects for this span.

## 11. Layer 6 — the agentic loop

No job or verb spawns an agent: each station prints the command for the next, and the session dispatches cold agents in clean rooms. The order is fixed (TEST_LOOP.md): the eye before the pen; the pen opens only when the audit is clean.

| station | who | the command, what it does, what it writes |
|---|---|---|
| 7 `looked_at` | lookers (cold agents, 3 in ADR-0025) | `scprofile review --out RUN --plugin cellchat --shards N` lists the scan set — every figure the paper numbers plus the largest instance of every kind it does not show (*80 on 712314*) — split N ways, siblings together, only the outstanding; each look is `review --figure F --note "…" [--defect] --reviewer <name>`, appended to `<run>/kernels/cellchat/FIGURE_REVIEW.jsonl` with the plate's sha256; a look carries to any sibling run whose plate has the same bytes (`--adopt` appends what a run relies on to its own ledger); `--defect` is a verdict the audit counts |
| 6b `audited` | machine, then the author | station 6b reads `panels.json` audits and repairs, the eye's defects, the stated disclosures (a disclosure closes a finding only while the entry's legend in this tree carries its words); the worksheet `review --worksheet` groups open findings by kind, names the owner (host panel / tool plate / plugin drawing), quotes the eye and prints the two answers |
| the author's pass | a cold author | edits through the maker's verb — `sch dev edit --set / --legend / --remove / --add …`, one command per change, the followers run — or `review --figure F --answer "why" --reviewer <author>` for a plate that should stay (settled by a looker's fresh look), or `--answer … --stated` once the sentence is in the legend; `capacity --declare` for a measured term |
| the rerun | the job | `sch dev job --ref RUN --redraw --plugin cellchat --predict "…"` → validate → submit (§3); the second look lists only what was redrawn or answered |
| 8 `written` | the writer (a cold agent) | `paper --brief` prints WRITING_BRIEF.md; `paper --claim` records a claim citing plates (`PAPER_CLAIMS.cellchat.jsonl`), refused on a plate with an open finding; `paper --write section.md` carries the section in (`PAPER.cellchat.md`), every citation re-checked against the brief; the result-section skill and its templates are the register |
| the review | a second agent | `paper --round --reviewer <name>` on every claim: standing / narrowed / refuted; a reviewer equal to the author is refused |
| 9 `delivered` | the writer | `paper --render` → `report/cellchat_paper.html`; station 9 reads the page and the ledger under the plugin |
| the writing seal | the job | `submit_writing_seal.sh --prepare REF` makes `<stamp>__…__written/` with `incoming/`; the agent's written layer is sent there; `--seal` runs `jobs/writing_seal.pbs`: the sealed run's light half copied writable into `replay/` (objects, cache, logs, fixture excluded), the written layer laid over, the maker's status on the replay, grading W1–W3 into `PREDICTIONS.txt`, the seal; a sealed run is never written to |

## 12. What it costs

| piece | time | basis |
|---|---|---|
| queue wait on the pinned node | ~1 min when idle, not guaranteed | 712312 submitted 15:08:52, started 15:09:38 |
| fixture gate, both shapes in parallel | 2 min 28 s | 712314 |
| cohort, objects reused | ~11 min (units ~3, compare 2:45, report once) | 712314: 14 min 9 s total |
| cohort, every object re-inferred | ~22 min | 712312: 24 min 49 s total |
| the loop with the writing, one clean pass | 2½–3½ h wall clock (estimate) | ADR-0025: lookers 36 min, author 71 min over three exchanges, writer 21, reviewer 17, three reruns and three seals in ~6 h |

## 13. What is not automatic, and the open limits

- **The agentic layer is session-started.** By design since ADR-0017/0019: every station prints its command; nothing spawns the lookers, the author, the writer or the reviewer.
- **Looks carry by bytes.** A re-inferred object changes the permutation-dependent plates, so after a re-inference every plate is new to the eye (712314: 80 figures to look at, nothing carried).
- **The forecast is relative to the run named**, not to the store; a cleared store makes a HIT wrong.
- **A literal fitted to the cohort** has no static gate; the fixture run is it, and the fixture has one factor — the interaction axis is never exercised by the gate.
- **The store keeps one object per parameter key per span**; a change to a keyed parameter or the recipe re-infers once (~22 min).
- **The disclosure binding is mechanical**: a rewrite of the legend in other words unbinds a stated disclosure until it is re-stated (the worksheet says which).
- **Two commit gates.** scProfile's runs under `.venv` and counts its SKIPs; the harness's `unittest discover` prints `skipped=N`. A green with skips is a weaker statement, and both now say so.
- **The run's own record lists only its own trees** since d933b13; runs made before it (712312, 712313) carry the fixture's files in their `STATUS.json` products.
- **The cluster's per-class trees** `~/tools/scProfile-cconly-{A..G}` and the mutant branches `attack-0026-*` stay as the campaign's record.

