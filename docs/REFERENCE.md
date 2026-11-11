# scProfile reference

Every element of scProfile, defined once. Each entry says what the element **is**, what it
**does**, and what it **does not** do.

---

## Concepts

| term | definition |
|---|---|
| **plugin** (kernel) | One file that wraps one analysis method. It declares what it needs and what it produces, and it runs in its own environment. Dropping the file in is the whole installation. |
| **host** | scProfile itself. It reads the object, plans the run, builds environments, launches plugins, merges results and writes the report. The host never imports a plugin. |
| **unit** | The slice of the data one plugin invocation is computed over. A **group** unit is a design arm (cells pooled). A **sample** unit is one sample. |
| **group** | A combination of the design's biological factors — an arm of the experiment. In single-cell analysis the group is the unit of inference: a method infers from the cells in an arm. |
| **sample** | One library or animal. The sample axis measures whether the members of a group agree. It is confidence, never a precondition for analysis. |
| **contrast** | A comparison between two arms. A two-factor design supports six: each factor marginally, and each factor held at every level of the other. |
| **run** | One invocation of `scprofile run`, writing one run directory identified by a run key. |
| **run key** | The directory name of a run. It names the timestamp, the tool commit and the stage. It is the only thing that ties a result to the code that made it. |
| **declaration** | The `PLUGIN` dictionary at the top of a plugin file: its requirements, config, produced artifacts, figures and report spec. The host reads it and never guesses. |
| **contract** | The JSON passed to a plugin (`in.json`) and returned by it (`out.json`), validated in both directions. |
| **reuse key** | The hash of everything that determines a result: plugin, version, unit, input identity, params, keys. Two instances with the same reuse key are asking for the same thing. |

---

## Commands

| command | what it does |
|---|---|
| `scprofile plan` | Reads the object, reports what would run and why the rest would not. Writes nothing and computes nothing. |
| `scprofile install` | Groups the selected plugins' requirements into as few environments as satisfy them, and builds the group the plugin belongs to. A group that has a current lock for this machine is built from that lock with `pip --no-deps`, so pip resolves nothing (conda still solves the conda packages), and the result is checked against the lock. A lock that no longer matches is refused. Then each member's selftest runs, and its verdict is recorded per member. |
| `scprofile lock` | Resolves a plugin's whole environment group once, with uv, under `setup/locks/constraints.txt`, for one platform (`--platform`, the building machine's) and one interpreter. It writes every version to `setup/locks/<platform>/<members>.txt`. A maintainer runs it after changing a plugin's `requires`. |
| `scprofile doctor` | Reports which environments exist, which plugins resolve to them, whether each group is locked, and what is missing. |
| `scprofile run` | Plans, runs the plugins, merges results into one object, writes the report and the run card. |
| `scprofile report` | Re-renders the documents from an existing run's `report.json`. Draws no new analysis. |
| `scprofile run --control FACTOR=LEVEL` | Declares which level of a factor is the control, so every contrast is measured against it. Repeatable; `plan` takes it too. Without it the tool recommends one from a vocabulary of experimental role and prints the basis. A factor or a level the design does not have is refused, by name, before anything runs. |
| `scprofile run --covariate COLUMN` | A column of the design table to adjust for beside the contrast's terms. Repeatable; `plan` takes it too. Each is modelled (numeric or categorical) or refused with the reason, for every plugin that declares `covariates` in `inject`; a plugin that does not is said not to model it, and every column of the design table that is neither a term nor a declared covariate - including those `--factor` leaves out - is named as not in the model. |
| `scprofile capacity` | What a run delivered, as counts measured from disk, and whether it delivered less than another run. The suites cannot catch a regression in output; this can. |
| `scprofile cache` | Reports what the reuse cache holds — apparent size, and how much of it is shared with run directories by hard link — and clears it. Everything in it is rebuildable, so the only cost of clearing is rebuilding. |
| `scprofile standard` | Measures a rendered report against the exit standard. |
| `scprofile status` | For one run directory: which instances are finished and which are outstanding. |
| `scprofile landscape` | Across many run directories: what earlier runs hold, and what a new run would still have to compute. |
| `scprofile licence` | Evaluates a run's results against the licence criteria and, with `--grant`, records licences for reuse. |
| `scprofile agenda` | What the agent still has to do on this run, in order, each task's state read off the run's own artifacts rather than stored. `--strict` exits non-zero while anything is outstanding. |
| `scprofile write` | The writing brief: the evidence this run's result is written from, and the order to do it in — read, **look at the figures**, write against the skill and the plugin's declared template, carry it back with `run --section`. The tool gathers; the agent writes. |
| `scprofile next` | The ONE next thing to do on this run. `agenda` prints the whole list, which is what to read when deciding; this prints the single next action, which is what to read when working. |
| `scprofile watch` | What state a run is in — running, sealed, failed, or not yet known. `--wait` blocks until it finishes. The run records its own job id, so nothing is passed in; a seal lags the queue, so a job that has left the queue with no marker is UNKNOWN rather than failed. |
| `scprofile review` | Records that a figure has been looked at, and reports which have not. |
| `scprofile paper` | The paper test: records a claim written from the figures and what each review round did to it. A claim is bound to the figures it cites, so a redraw makes it stale. `docs/PAPER_TEST.md`. |
| `scprofile check` | One green/red line per element of scProfile, asked of the code where it runs and never of its source text. Exits non-zero if any is red. One line is a WARN and never red: whether this clone's own commit gate is installed, a per-clone git setting a fresh clone, a cluster checkout or a pip install does not have. Among the rest: every shipped plugin validates, and every shipped plugin's declaration loads and its design record accounts for it as it ships (the check `scprofile design` runs on the record, below). With `--out`, also checks what a run produced. |
| `scprofile validate` | Checks a plugin declaration and its references without running anything. |
| `scprofile design` | For a design-aware plugin (`inject` names `design` or `contrast`): names every site where it builds a model or takes a contrast, and every runtime statement (`ctx.caveat`, `ctx.refuse`) of what was contrasted or modelled, and exits 1 while it does not take its frame (`ctx.model_frame`) and level order (`ctx.levels`) from the host, does not declare `covariates`, or leaves a statement unanswered. Named, it prints that plugin's worksheet; unnamed, one verdict line per plugin. `--answer FILE --why` applies a change only inside a named site - a fit call's statement and the lines that define the names its DESIGN arguments read (`design`, `formula`, `contrast`, `design_factors`, `ref_level`, `reference`, `levels`, `metadata`), two hops back and above the line that reads them, or a statement and the comment block directly above it - inserting only strictly inside one; it refuses an answer that names no site, changes a fit call's other arguments, adds a statement binding a name the replaced lines did not bind as a design name, or carries a character another reader takes as a line break; it raises `version` and records the diff in `kernels/<plugin>.design.json`; `--confirm LINE --why` records a statement true as it stands; `--replay-into FILE` rebuilds the plugin from that record, admitting every recorded diff again against the sites of the file it is applied to. `--rewrite-record` writes the plugin's record in the form the maker writes now, with no answer - no copy of a declaration, every row of an answer made on a committed file a digest - leaving the plugin untouched, refused unless the rewritten record passes its check; a record holds only the keys the maker writes, so a copy or any other key fails the check by name (W047). The record also verifies itself wherever it is read - in this command, for every plugin and not only a design-aware one, so the maker's `design` stage owes; in `scprofile check`; and in the suite, so the commit gate fails: the declaration must be one the host loads, read by the host's own reader (`kernels.read_declaration`) - `PLUGIN` bound once, in any syntax and at any depth the import runs, by a top-level `PLUGIN = {...}` standing alone on its lines (from the first column of its first line; nothing but blanks or a comment after it on its last), a pure literal (`ast.literal_eval`) dict - in the shipped file, in every file of the record's chain and in each declaration the record swaps in; a declaration that is not, or a file that does not parse or is not UTF-8, owes by name and never raises; every recorded diff is undone from the shipped file, last first, back to the first answer's `before`, and admitted again with the sites it records; and that first file - or, with no answer yet, the shipped file - must be, outside its declaration, the plugin at the commit its blind record was taken at, which DEVPOINTS `rules.held_out.spent` names and git keeps (read with `git show`, or, where there is no `git`, from the repository's own object store; never from the record). A forged or inadmissible entry, a record rewritten to start from a doctored file, a file changed outside its declaration with no entry, or a base that cannot be read - a shallow checkout, a directory with no repository - fails it. `--answer` refuses a plugin with no such commit, and a first answer on a file that differs from it outside the declaration. A plugin whose declaration the host cannot load owes, named, rather than reading "not design-aware"; `--answer` also refuses an answer that would leave such a declaration (a `global PLUGIN` inside a site). What it does not guarantee, exactly: the content of a site line is not judged - a loop header binding a design name is a site line, so its iterable can change, and a side effect written into a design line or a caveat (`C.update(alpha=0.5)`) is admitted and recorded; the call's other arguments are held as syntax only, so their values can still move through such a side effect; a design definition can be deleted; and the declaration (`PLUGIN = {...}`) is the maker's verb's, not this record's. Review therefore reads every answer's diff in the record. The maker's `design` stage runs it. |
| `scprofile prose` | Edits a plugin's prose through the maker: `--replace OLD NEW` (OLD once in the file; repeatable) with `--why`. Admitted only when the code is unchanged - Python's tokens with comments and docstrings set aside, each embedded R script by its code with its comments set aside - and refused with the line otherwise, the rule asked of the file as it is written (version raised; `--as-version` is N.N.N or refused). Made on a committed file, recorded in `kernels/<plugin>.design.json` as `kind: prose` (only the lines it wrote; every other line by its digest; no copy of the declaration), then the `plan.after_edit` followers run (`--no-follow` prints them; `--dry` writes nothing). A plugin DEVPOINTS anchors nowhere - every held-out one - is refused. |
| `scprofile scaffold` | With `--new`, writes a new one-file plugin from the template. Without it, writes an already-declared plugin's build skeleton. |
| `scprofile fetch` | Downloads a plugin's declared reference data. |
| `scprofile selftest` | Runs one plugin's selftest in its environment. |
| `scprofile generated` | Checks every document region rendered from the code — ROADMAP.md's shipped table and the figures skill's panel catalogue; `--write` rewrites them. Both are generated, so adding a kernel or a panel kind means adding it in the code and running this — never editing the document. |

---

## Run directory

```
<run key>/
├── kernels/<plugin>/<unit>/     one instance: in.json, out.json, figures/, tables/, staged inputs
├── objects/                     the merged object
├── tables/                      collected tables
├── report/                      the rendered documents
├── report.json                  the payload every document is rendered from
├── README.md                    what ran, what did not, and what the directory holds
├── RUN_CARD.json                this run's verdict on its own output
├── LICENCES/                    one licence per instance, once granted
├── FIGURE_REVIEW.jsonl          the record of which figures have been looked at
└── PAPER_CLAIMS.jsonl           claims written from the figures, and what review did to them
```

**Figures are NOT collected into a top-level directory, and tables are.** This listing said
`tables/  figures/` until 2026-08-29 and a reader would have gone looking; on a real ten-sample
run all 181 figures were under `kernels/<plugin>/`, where they are written. The asymmetry is
deliberate: a licence covers an instance's products and hashes them where they were produced, an
adopted instance is hardlinked back into the same place, and a second copy of a figure elsewhere
is a second thing to keep in step. The report reaches every one of them by relative path.

A job script may add more — a run key file, a `logs/` directory, a seal. Those belong to
whatever submitted the run, not to the host, and nothing here reads them.

| file | definition |
|---|---|
| `in.json` | What the host gave a plugin: the object path, keys, params, design, references. |
| `out.json` | What the plugin returned: figures, tables, objects, metrics, caveats, contradictions, status. **Absent** means the plugin died. **Present and empty** means it ran and found nothing, which is a result. |
| `report.json` | Everything the report is rendered from. `scprofile report` needs nothing else. |
| `RUN_CARD.json` | The run's own verdict per instance: `ok`, `empty`, `suspect`, `failed`. Written at the end of every run. |
| `LICENCES/*.json` | Evidence that an instance may be adopted by a later run, with the sha256 of every product it covers. |
| `FIGURE_REVIEW.jsonl` | Append-only record of figures looked at, bound to each image's sha256. |
| `PAPER_CLAIMS.jsonl` | Append-only record of claims written from the figures and the verdict of each review round, each claim bound to the sha256 of every figure it cites. |
| `ADOPTED.json` | Written into an instance that was adopted from another run: the source run, the grade, and how it was materialised. |

---

## Reuse

Three independent questions, all of which must be satisfied.

**1. Does it exist?** — `scprofile status`

| state | meaning | outstanding |
|---|---|---|
| `done` | `out.json` with entries | no |
| `empty` | `out.json`, no entries — the method ran and found nothing | no |
| `stale` | complete, but produced by a different plugin version | yes |
| `died` | inputs staged, no `out.json`, or a truncated one | yes |
| `absent` | never staged | yes |

**2. Is it the same thing?** — the reuse key. Any difference in plugin, version, unit, input
identity, params or keys means it is not. The run key, date and machine are excluded.

**3. Is it fit to build on?** — the run card verdict.

| verdict | meaning | reusable |
|---|---|---|
| `ok` | completed, nothing objected | yes |
| `empty` | ran and produced nothing | yes |
| `suspect` | the plugin contradicted its own output, or a diagnosis was raised against the method | no |
| `failed` | did not complete | no |
| `unknown` | the run published no card | no |

---

## Licence

A licence is the recorded evidence that one instance may be adopted into a later run. It covers
the instance's **products** — the figures, tables and objects named in its own manifest, plus
`in.json` and `out.json` — and stores the sha256 of each. It does not cover staged inputs.

### Criteria (version 1)

| criterion | requires | required for any licence |
|---|---|---|
| `integrity` | every product exists and hashes cleanly | yes |
| `completeness` | the instance finished, everything the plugin declares it `produces` is present, and every figure it marks `required` is in the manifest | yes |
| `provenance` | the reuse key is computable | yes |
| `self_report` | the producing run published a card and its verdict is trusted | no |
| `inspection` | every figure has a recorded look | no |

### Grades

| grade | when | adoptable |
|---|---|---|
| `refused` | a required criterion fails, or the producing run called the result suspect or failed | no |
| `retrospective` | the producing run published no card, so its own verdict cannot be recovered | by explicit policy |
| `provisional` | required criteria and `self_report` pass; the figures have not been looked at | yes |
| `full` | every criterion passes, inspection included | yes |

The grade is derived from evidence alone. Which grades a project accepts is set at adoption
(`adopt(min_grade=...)`) and recorded in `ADOPTED.json`.

### Adoption

Adoption re-verifies every hash, then **hardlinks** the products into the new run. A hardlink is
the same inode, so an adopted file cannot differ from the licensed one. Where a hardlink is
impossible the files are copied and the record says so.

### What a licence does not establish

- That the numbers are correct. Only that nothing available objected to them.
- That the input object is unchanged. Runs record its path, size and mtime, not a content hash.
- That any figure was looked at, unless `inspection` passed.

---

## Figures

### Where figures come from

A plugin declares its figures in `PLUGIN["report"]["figures"]` and draws them with
`ctx.emit_figure`. The host draws the design panel, the between-arm comparisons and the per-arm
networks from the plugin's `unit_network` declaration.

### `unit_network`

Declared in a plugin's `report` block. It names the per-unit table that holds a network:

```python
"unit_network": {"table": "tables/ccc_edges.csv", "source": "source",
                 "target": "target", "weight": "prob", "group": "pathway_name",
                 "member": "interaction_name"}
```

`weight` must be a **magnitude**, not a rank. Four keys are required — `table`, `source`,
`target`, `weight` — and each optional one earns further panels:

| declared | what it earns |
|---|---|
| the four required | `matrix`, `circle`, `chord`, `role_scatter` per arm; `diff_matrix` and `role_shift` per contrast |
| `+ group` | `flow_rank` and `role_heatmap` per arm; `flow_compare` per contrast |
| `+ group` and `member` | `contribution` per arm |

An unrecognised key here is an **error**, not a warning: a misspelt column name removes panels
in silence, and a plugin that has lost three of them looks exactly like a plugin that declared
less.

Any plugin that declares this gets those panels. No host code names a method.

### Panel kinds

`scprofile/panels.py` registers thirteen kinds, each declaring what it establishes and what it
does not: `matrix`, `diff_matrix`, `circle`, `chord`, `role_scatter`, `role_shift`, `flow_rank`,
`flow_compare`, `role_heatmap`, `patterns`, `similarity`, `contribution`, `coverage`.

The registry is a **specification**, not a dispatcher. It records what each kind must establish
and which rules bind it; the drawing code implements them.

**Each kind declares an OWNER, which is a different question from whether it is drawn yet.**

| owner | meaning | kinds |
|---|---|---|
| `host` | derivable from `unit_network` by aggregation alone, and therefore owed to every plugin that declares one | the other ten |
| `plugin` | needs an analysis the host may not perform, or information no declaration carries | `patterns`, `similarity`, `coverage` |

The three plugin-owned kinds are **not a backlog**. A latent decomposition and a similarity
embedding produce numbers that first exist at render time, which the reporter is forbidden to do
(`docs/ARCHITECTURE.md` §0); database coverage needs the reference funnel, which an edge list
does not carry. A plugin drawing one of these is complete, not a stopgap.

`gaps()` therefore means *host-owned and not drawn* — a debt, and it is currently empty. A test
asserts it stays empty, and a second asserts that a kind moved to `plugin` carries a reason, so
the debt cannot be cleared by reclassifying it. Until 2026-08-29 the two were counted together
and the catalogue read as five of thirteen drawn, which understated what a plugin inherits and
overstated what was outstanding.

### The chain a figure set goes through

```
run  ->  report  ->  standard  ->  review  ->  paper  ->  licence / promote
         draw it     is the page   did anyone  do these    build on it
                     readable?     look?       figures
                                               support the
                                               claim?
```

The first three can all pass on a figure set that supports nothing. `paper` is the one a reader
will put to you. Run it before promoting a run or reusing its results.

### The standard the figure set is held to

`docs/FIGURE_STANDARD.md` states it in one line: **a figure set is finished when someone can
write the Results section from it and that section survives review.** It carries the test, the
eleven rules the test produced, and the rule for choosing main against supplementary panels
(a main figure is one the Results section cites for a claim).

### Rules every panel obeys

| rule | requirement |
|---|---|
| the paper test | the set is finished when a Results section written from it survives review |
| a compositional readout | ranked on a second scale too, and disagreement disclosed on the panel |
| presence is not magnitude | an element absent from one side is marked and taken off the scale |
| a contrast declares its confounds | audited on the samples it compares, not on the cohort |
| provenance on the face | the unit, its kind and n are on the image, not only in the caption |
| shares where the weight is per-object | with both totals printed; per-object or absolute is declared |
| one scale across a grid | A grid of panels shares one maximum, printed, so a width converts back to a number. |
| absence is not zero | A measured absence and a never-tested element are marked differently, or the panel states it cannot distinguish them. |
| a cut names what it removed | Ring and chord panels state the fraction of strength kept and name anything left with no link. |
| declare a misleading denominator | Averaging over N when a value was measurable in fewer than N is stated. |
| a per-object scale is not comparable across objects | Where each unit is normalised within itself, widths compare within a panel and rank-order across panels. |
| no panel is gated on the sample axis | Group comparisons are drawn whatever the arm sizes; `n` is stated. |

### Statistics

Panels report the statistics of the method they wrap. The host computes none of its own. Where a
method ships no test, the panel is descriptive and says so — it shows observed differences with
no interval and no significance marking.

### Report pages

| page | contents |
|---|---|
| `<plugin>.html` | The cohort page: what ran, the design panel, and the main-effect comparisons. |
| `<plugin>_by_arm.html` | Every contrast the design supports, and each arm's own network. |
| `<plugin>_by_sample.html` | The per-sample panels. |
| `index.html` | What ran, what did not, and why. |

The cohort page is measured by the exit standard. The appendix pages are exempt only while the
cohort page links to them.

---

## Units and group-level analysis

A **unit** is a set of samples. A sample unit has one member; a group unit has the members of a
design arm. `_entry` subsets the object by membership in that set, so a plugin invoked on a
group unit sees the arm's pooled cells.

`scprofile/units.py` resolves the axis from the design:

- **Group first.** An arm is the combination of the design's biological factors. Technical
  factors — batch, chemistry, lane — are excluded from the arm label.
- **Sample as well**, where the design has more than one sample.
- A thin sample axis never withholds a group-level result.

`run --unit-by group|sample|both` selects the axis; the default is `both`.

Each instance's `in.json` carries `unit_members`, the samples that unit covers. Memory is
charged to a group unit as the sum of its members' cells.

**Group-level comparison** is separate and also active: the report pools each unit's results
into arms and draws every contrast the design supports, plus each arm's own network, whenever a
plugin declares `unit_network`.

---

## Environments

`scprofile install` groups every selected plugin's requirements into the fewest environments that
satisfy them. The grouping reads declarations, so it cannot see a solve that fails: a site that has
measured one names the member in `$SCPROFILE_ISOLATE` (plugin names, separated by commas or spaces),
and each listed plugin is then built alone ("isolated by the site") while the others share without
it. A failed shared build prints its members and this variable as the fix. A plugin declares ranges. What those ranges resolve to on one platform is recorded
once, by `scprofile lock`, in `setup/locks/<platform>/<members>.txt`. Each lock file carries:

- every package of the group's closure, at one exact version;
- the platform it was resolved for, as uv names it (for example `x86_64-manylinux_2_17`: linux
  x86_64). The tag is the resolver's target, not the floor of what installs. uv accepts a version for
  that target when it ships a source distribution, even if its wheels need a newer glibc. The shipped
  lock pins nine packages whose cp312 wheels need glibc 2.24 to 2.28, so its real wheel floor is
  **glibc 2.28** (KNOWN_ISSUES);
- the interpreter version;
- the resolver;
- the ranges and host constraints (`setup/locks/constraints.txt`) it was resolved from.

On a machine whose platform a lock covers, a group is in one of three states:

| state | when | what `install` does |
|---|---|---|
| locked | a lock exists for exactly these members and today's requirement | Applies it with `pip install --no-deps`, so pip resolves nothing; conda still solves the conda packages. Then checks that every installed version is the locked one; a difference is a failed build with no stamp. |
| stale | a lock names a member of this group, but its members or its requirement changed | Refuses before anything is built. The refusal names what changed and the `scprofile lock` command. A stale lock is never bypassed by resolving the ranges instead. |
| unlocked | no lock for this platform names any member | Resolves the ranges at install time, as before, and says so. |

Every build writes `.scprofile_resolved.txt` beside the environment: the pip and conda versions it
actually holds. Locks cover the pip half; the conda half (`requires.conda`, e.g. `r-base=4.3`) and
the R pins are applied as declared.

Environments are content-addressed. A locked group's directory name is a hash of its pins, its
interpreter, its platform and its conda, channel and R specs. An unlocked group's name is a hash of
its requirement set. So a changed pin or declaration is a different environment, no run can silently
use the old one, and rewording a lock's comments renames nothing.

The build is shared and the proof is per member. `install` proves the plugin it was asked about,
plus every member with no standing record. Each verdict is recorded beside the environment, and
`run` and `plan` refuse a plugin whose own record is absent, stale or failed.

---

## The exit standard

`scprofile standard` measures a rendered report, not the code that made it.

| criterion | requirement |
|---|---|
| `overview` | The page states what was compared before showing a number. |
| `arms` | At least one figure compares the design arms. |
| `count` | At most 12 figures on a page. |
| `captions` | At most 45 words in a caption's visible lead. |
| `caveats` | Caveats are capped separately and generously; they must stay visible. |
| `hidden` | At most 2500 words behind disclosures. |
| `repeats` | No figure id appears twice. |
| `identifiers` | No unmapped accession appears in a result. |
| `contradictions` | A refutation is shown once, at the top. |
