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
| `scprofile install` | Resolves every selected plugin's requirements into as few environments as satisfy them, builds those, and runs each plugin's selftest. A shared environment is not considered built until every plugin resolving to it passes. |
| `scprofile doctor` | Reports which environments exist, which plugins resolve to them, and what is missing. |
| `scprofile run` | Plans, runs the plugins, merges results into one object, writes the report and the run card. |
| `scprofile report` | Re-renders the documents from an existing run's `report.json`. Draws no new analysis. |
| `scprofile standard` | Measures a rendered report against the exit standard. |
| `scprofile status` | For one run directory: which instances are finished and which are outstanding. |
| `scprofile landscape` | Across many run directories: what earlier runs hold, and what a new run would still have to compute. |
| `scprofile licence` | Evaluates a run's results against the licence criteria and, with `--grant`, records licences for reuse. |
| `scprofile review` | Records that a figure has been looked at, and reports which have not. |
| `scprofile check` | One green/red line per element of scProfile. Exits non-zero if any is red. With `--out`, also checks what a run produced. |
| `scprofile validate` | Checks a plugin declaration and its references without running anything. |
| `scprofile scaffold` | With `--new`, writes a new one-file plugin from the template. Without it, writes an already-declared plugin's build skeleton. |
| `scprofile fetch` | Downloads a plugin's declared reference data. |
| `scprofile selftest` | Runs one plugin's selftest in its environment. |

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
└── FIGURE_REVIEW.jsonl          the record of which figures have been looked at
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

### Rules every panel obeys

| rule | requirement |
|---|---|
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

`scprofile install` resolves every selected plugin's requirements into the fewest environments
that satisfy them. Environments are content-addressed: the directory name is a hash of the
resolved requirement set, so a changed declaration is a different environment and no run can
silently use the old one.

A shared environment is not considered built until every plugin resolving to it passes its
selftest. `install` reports which members passed and refuses the environment otherwise.

---

## The exit standard

`scprofile standard` measures a rendered report, not the code that made it.

| criterion | requirement |
|---|---|
| `overview` | The page states what was compared before showing a number. |
| `arms` | At least one figure compares the design arms. |
| `count` | At most 12 figures on a page. |
| `captions` | At most 45 words in a caption's visible lead. |
| `prose` | At most 900 words of visible narration. |
| `caveats` | Caveats are capped separately and generously; they must stay visible. |
| `hidden` | At most 2500 words behind disclosures. |
| `repeats` | No figure id appears twice. |
| `identifiers` | No unmapped accession appears in a result. |
| `contradictions` | A refutation is shown once, at the top. |
