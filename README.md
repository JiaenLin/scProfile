# scProfile

**A design-aware agentic research discovery workflow for single-cell data.**

Point it at an annotated single-cell or single-nucleus object and the experiment's design. It
works out what that experiment can ask, runs the methods that can answer, draws the figures, and
hands an agent everything needed to write the result — with every claim bound to the figure it
was read off.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Methods](https://img.shields.io/badge/methods-9-informational)

```bash
pip install -e '.[run]'

scprofile plan --h5ad cohort.h5ad --design design.csv --all --report plan/
scprofile run  --h5ad cohort.h5ad --design design.csv --all --out results/
open results/report/index.html
```

Works on any `.h5ad` with counts, a cell-type label and a sample column. Pairs directly with
[scQC](https://github.com/JiaenLin/scQC) → [scAnno](https://github.com/JiaenLin/scAnno) →
[scIntegrate](https://github.com/JiaenLin/scIntegrate).

**You never write a wrapper.** Install scProfile, point it at an object, run `plan` then `run`.
Writing or updating a method is a maintainer job — see
[docs/MAINTAINING_PLUGINS.md](docs/MAINTAINING_PLUGINS.md).

### What a run leaves behind

```
results/
├── report/index.html          the report, and one page per method
├── kernels/<method>/
│   ├── figures/               every panel, with its legend and source data
│   ├── tables/                every number the report quotes
│   ├── WRITING_BRIEF.md       the evidence to write the result from
│   └── AGENDA.md              what remains to be done, and in what order
└── objects/                   the merged object
```

---

## The design is the spine

One design table is the only place the experiment is described, and everything downstream is
derived from it. That is what
"design-aware" means here, and it is what joins the two halves below into one workflow:

| the design decides | what it produces |
|---|---|
| what a method is fitted to | units: one per design arm, one per level of each factor, one per sample |
| which questions the experiment supports | every marginal, simple and interaction comparison, enumerated |
| what each question needs to be answered | the evidence, stated as biology before any method is named |
| which figure answers it | the wrapped tool's own plot first, the host's own only where none exists |
| what the written result contains | one section per comparison, in the order the design gives them |

Nothing in that chain is configured per project. A three-factor design produces more comparisons,
more units and more sections from the same code.

## The three parts

**A platform harness** — takes the object and the design, resolves what can run, builds the
environments, runs plugins, merges the outputs. Plugins are plug-and-run: one file each,
declared, no host change to add one. Nine ship today: cell cycle, RNA velocity, pseudotime,
regulons, pathway and TF activity, cell–cell communication, differential abundance, differential
expression.

**An agentic figure harness** — takes those outputs and produces the figures and the written
result. It enumerates the comparisons, states what evidence each needs, prefers the wrapped
tool's own plots over reimplementing them, checks what was drawn, records what the agent saw, and
binds every written claim to the figures it was read off. It refuses rather than guesses: a
question with no panel is reported as a gap, and a claim with no figure behind it is not written.

**An agentic layer** — the interface the agent writes the run up through. A run
emits a *brief* (the evidence, with every number's file named), an *agenda* (the cycle as an
ordered list, each step's state read off the run's own artifacts), and a ledger of which figures
have actually been looked at. The agenda knows how the compute executes: under a scheduler it
says to submit the job, watch it, and collect its output the moment it seals, because a batch job
runs detached and cannot call anyone back.

**The tool measures; the agent writes.** That division is deliberate. The tool used to assemble
the section itself from format strings, and the result was traceable, reproducible prose that
could not decide what mattered or narrow to a focus. So the tool now produces the evidence and
refuses what it cannot support, and the writing is done against a general skill plus the template
each plugin declares for its own method. `docs/AGENT_CONTRACT.md` states which half is whose.

The boundary between the first two is the plugin runner: everything before it is about getting a
method to run correctly, everything after it about turning the output into something a reader can
check. The boundary of the third is the point where judgement starts.

---

> **Figures are held to a standard, and the standard is a test rather than a checklist:** a figure set is finished when someone can write the Results section from it and that section survives review. `docs/FIGURE_STANDARD.md`.

## What you get

| method | gives you | needs |
|---|---|---|
| `cellcycle` | phase, S and G2M scores per cell | — |
| `velocity` | direction of transcriptional change | spliced/unspliced layers |
| `pseudotime` | ordering along a trajectory, with fate probabilities | an embedding, `cellcycle` |
| `scenic` | regulon activity, from a network inferred from your data | counts, cisTarget databases |
| `decoupler` | TF and pathway activity, from curated priors | — |
| `liana` | cell–cell communication, consensus over several methods | — |
| `cellchat` | cell–cell communication, CellChat's scoring | R, CellChatDB |
| `abundance` | whether a population's share shifts across your design | a design table |
| `de` | which genes change, per cell type, across your design | a design table with replicates |

Run `scenic` with `decoupler` to compare a network inferred from your data against curated
priors. Run `liana` with `cellchat` to compare two communication methods. Both pairs write
separate outputs, so you can hold the results side by side.

## Plan before you run

```bash
scprofile plan --h5ad cohort.h5ad --design design.csv --all --audit --report plan/
```

`plan` reads the object, resolves every prerequisite, searches for inputs that live beside the
object rather than in it, and prints the command that closes each gap. It runs nothing and takes
seconds.

Every method gets one of four verdicts:

- **RUN** — with the capacity it will run at, and what would raise it
- **SKIP** — your design cannot support this test, citing the factor and its arm sizes
- **BLOCKED** — the data is absent; every directory searched is named
- **UNRESOLVED** — the scan could not determine. A defect in the plan, never a skip.

`--audit` checks the plan against rules that do not reuse its reasoning: every method accounted
for exactly once, nothing UNRESOLVED, every SKIP citing a fact the design table supports, every
BLOCKED naming where it looked.

`--report` writes an HTML page — what will run, in what order, with what settings, what each
result lets you say, and what it does not.

## Install methods

```bash
scprofile doctor                                    # what you have, what you need
scprofile install scenic --prefix ~/envs --dry-run  # which environment, shared with whom
scprofile install scenic --prefix ~/envs
```

Each method declares the versions it needs. The builder resolves them together and builds as few
environments as satisfy them all — sharing where that is provably safe, isolating where it is
not, and telling you which and why.

```
scprofile install decoupler --prefix ~/envs --dry-run
  environment scprofile-env-3cd799b82e
      shared by: decoupler, liana, pseudotime, velocity
```

Installing builds the environment and runs the selftest of **every** method in it — a real
computation, not a set of imports. Point at environments you already have with
`SCPROFILE_<METHOD>_PYTHON`.

The host itself needs only numpy and pandas; `[run]` adds anndata and scanpy. Method
environments are built with conda, mamba or micromamba.

## Run

```bash
scprofile run --h5ad cohort.h5ad --out results/ --prefix ~/envs --all
```

Keys, organism and assay are detected and printed, and any can be overridden with `--label-key`,
`--sample-key`, `--counts-layer`, `--organism`, `--assay` and the rest:

```
what this object is, and how each was decided:
  label          cell_type          detected: first of ['cell_type', ...] present
  sample         sample             detected
  counts_layer   counts             detected
  organism       mouse              6/6 probe genes are Title Case
  assay          nucleus            unspliced is 71% of counts, the nuclear pattern
```

Methods run in waves, several at a time. Each gets a share of the allocation — cores, memory and
GPUs — sized from what it declared and from how many cells it will actually touch. Memory is a
fixed cost plus a per-cell one, so a method processing one sample is not charged as though it were
processing the cohort.

Every run measures what each method actually cost and prints the two terms fitted from its own
instances, ready to paste into a declaration. A method that declares no memory is scheduled on a
conservative assumption and the run says so, every time.

The run also **cannot change underneath itself**: it copies the tool into the run directory and
runs from there, so updating your checkout mid-run cannot reach it, and the host refuses any
instance whose code has moved since the run began.

## Output

```
results/
  objects/cohort_profiled.h5ad   cell-level results, merged by barcode
  objects/<method>_*.h5ad        side-car objects a method ships whole
  tables/*.csv                   edge- and gene-level results, prefixed by method
  report/index.html              start here
  report/<method>.html           one page per method
  report.json                    every number, machine-readable
  README.md                      written by inspecting the directory
```

Cell-level results merge into the object by barcode, never by position. Communication results are
edge data — cell type × cell type × ligand–receptor — and go to CSV beside it. A method whose
result does not fit the merged object ships its own file.

`uns['scprofile']` records which methods ran, at which versions, against which references, and
the caveats each declared.

## Figures

A plugin declares its figures in `PLUGIN["report"]["figures"]` and draws them with
`ctx.emit_figure`.

The host draws three things itself, from a plugin's `unit_network` declaration:

- the **design panel** — every contrast the design supports, described;
- the **between-arm comparisons** — for each contrast, drawn from cells pooled within each arm;
- the **per-arm networks** — a ring and a chord for every arm.

```python
"unit_network": {"table": "tables/ccc_edges.csv", "source": "source",
                 "target": "target", "weight": "prob", "group": "pathway_name"}
```

`weight` must be a magnitude, not a rank. `group` is optional. Any plugin that declares this
gets the panels; no host code names a method.

Two rules apply throughout:

- **The group is the unit of comparison.** Arm-level panels pool each unit's results and are
  drawn whatever the arm sizes. The sample axis reports whether the members of a group agree; it
  never gates a panel. A plugin is invoked once per design arm over the arm's pooled cells, and
  once per sample as well — `run --unit-by group|sample|both`.
- **Statistics come from the wrapped method.** The host computes none of its own. Where a method
  ships no test, the panel is descriptive and says so.

`scprofile standard` measures the rendered cohort page. `scprofile review` records which figures
have been looked at.

**Panel kinds, the rules each obeys, and the report page layout are in
[docs/REFERENCE.md](docs/REFERENCE.md).**

## Inputs that are not in the object

Spliced and unspliced counts come from the aligner and are missing from almost every object that
has been through QC and annotation — while the aligner output is usually still on disk.

scProfile reads the upstream chain recorded in `uns`, hands those leads to the method, and
searches them for a velocyto `.loom`, an mtx triplet beside a barcode list, or an `.h5ad`
carrying both layers. Matching is on the barcode core, within each sample, with the match rate
printed for every source tried. A source below threshold is refused rather than partly applied.

`--search <dir>` adds directories for data that has moved. A method that finds nothing refuses
and lists every directory it looked in.

## Reference data

Some methods consult data that did not come from your object — a motif ranking, a
ligand–receptor database, a regulatory prior. These decide answers as much as the algorithm does.

```bash
scprofile fetch scenic --to ~/refs --organism mouse --dry-run   # size, and whether it fits
scprofile fetch scenic --to ~/refs --organism mouse             # resumable, verified
scprofile validate scenic --references ~/refs --deep            # hashes what is on disk
```

`fetch` checks free space before downloading, resumes a killed download, and takes one writer per
directory. A method whose references are unusable **refuses to run** — a missing motif database
does not fail loudly, it returns a smaller answer that looks like a real one.

Not every reference is a file you download. A method declares which kind each one is, so the plan
can tell you before you spend a queue slot:

| tier | meaning |
|---|---|
| `fetch` | downloadable and checksummed — scProfile gets it and verifies it |
| `bundled` | ships inside a package, pinned by that version and nothing else |
| `runtime` | fetched by the tool **while it runs** — needs network on the compute node |

That last one matters on a cluster: `plan` names every method that will reach the network mid-run,
so a batch node with no outbound route is a problem you find in the plan rather than an hour in.

[docs/REFERENCES.md](docs/REFERENCES.md) lists every reference, its publisher, its terms, and
which of them scProfile can verify.

## Reusing an earlier run

A run is expensive. scProfile can report what an earlier run already computed, whether it is
still valid, and whether it is fit to build on — and adopt it into a new run by hardlink.

```
scprofile status    --out RUNDIR                # what is left in this run
scprofile landscape --root RUNS --h5ad OBJ      # what earlier runs hold, and what to compute
scprofile licence   --out RUNDIR --grant        # evaluate results and licence them for reuse
scprofile review    --out RUNDIR                # which figures have not been looked at
```

Reuse requires three things to be true at once:

1. **The result exists and is finished** — `status` reads the instance directory.
2. **It is the same thing** — the reuse key covers plugin, version, unit, input identity, params
   and keys. Nothing else.
3. **It is fit to build on** — the producing run's `RUN_CARD.json` verdict.

A licence records the evidence for all three plus, optionally, that the figures were looked at.
Adoption re-verifies every hash and then hardlinks, so an adopted file cannot differ from the
licensed one.

Grades are `refused`, `retrospective`, `provisional` and `full`. The grade comes from evidence;
which grades you accept is set at adoption.

**Definitions of every criterion, grade, verdict and file are in
[docs/REFERENCE.md](docs/REFERENCE.md).**

## Reading the results

Every method states what its result cannot tell you, and that statement appears in the report
under the result itself. Composition is relative, and every effect is named against its reference
population. Velocity is a direction, not a rate. Co-expression with a motif is not regulation.

Guards refuse datasets where a method's output would not mean what its report says. `--allow
<method>` overrides, and every override is written to `guard_overrides.jsonl`.

When an upstream tool has recorded a constraint on the object — a factor that is not identifiable
because it never varies within a batch, say — scProfile reads it and reproduces it, and a method
whose claim it forbids refuses rather than returning a number.

### The report is measured, and it says so

A rendered report is held to a standard measured on the artifact itself — the HTML that was
written and the figures it references, never a fixture. Ten criteria: that a page opens with what
the cohort was, that something on it compares the design, that no panel is the same plot redrawn
per sample, caps on figures and on prose, that an unmapped identifier is named as one, and that a
refutation the method made against its own headline appears where the headline is.

Whatever writes a report measures it, so the verdict arrives with the run rather than when
somebody remembers to ask:

```bash
scprofile standard --out <run dir>     # non-zero when the standard is not met
```

`ok` means the criterion was checked and passed. `exempt` means the page declared, with a reason
printed beside it, that the criterion cannot apply — a cohort with no design table can never draw
a panel comparing arms. `n/a` means it could not be measured at all. None of the three is
reported as either of the others: a column of ticks that includes checks nobody could run stops
meaning anything.

## Adding a method

A plugin is **one file**: `kernels/<name>.py` with a `PLUGIN` dict and a `run(ctx)`. Dropping it
in is the whole installation.

```
scprofile scaffold <name> --new        # write a new plugin from the one-file template
scprofile validate  <name>             # check the declaration without running anything
scprofile scaffold  <name>             # a declared plugin's build skeleton
```
 The host reads the declaration without importing it, resolves the
environment, and runs it through a shared entrypoint that applies the contract.

```python
PLUGIN = {
    "api": 1,
    "summary": "what it gives you",
    "inject": {"required": ["counts", "label"], "optional": ["sample"]},
    "produces": ["obs[my_score]", "tables/my_result.csv"],
    "requires": {"python": ">=3.10,<3.13", "packages": {"scanpy": ">=1.10,<1.11"}},
    "cores": 4, "memory_gb_base": 4, "memory_gb_per_100k": 8,
    "cannot_show": ["what a reader must not conclude from this"],
}

def run(ctx): ...
def selftest(ctx): ...
def guard(g): ...        # optional: refuse datasets where the result would mislead
```

Methods ask for **capabilities**, not column names, so a plugin never binds itself to one
project's schema. `produces` may mark an output only some runs make — `"obs[latent_time]?"` — and
may glob a name chosen at run time — `"obsm[velocity_*]"`. Both are held to.

Plugins talk to the host through JSON: write your results, declare them in `out.json`, and the
host merges and reports them. Any language. A directory layout is also supported, which is what a
plugin written outside Python uses.

Point `$SCPROFILE_KERNELS` at your own directory to add methods without forking. Site methods
override shipped ones, and `doctor` reports when that happens.

Full contract: [docs/PLUGIN_DESIGN.md](docs/PLUGIN_DESIGN.md) ·
[docs/MAINTAINING_PLUGINS.md](docs/MAINTAINING_PLUGINS.md).

## Requirements

Python 3.10+.

## Documentation

**Running an analysis:** the agent runs scProfile end to end — plan, run, open every figure, write the result — and never writes a plugin.

| document | what it covers |
|---|---|
| [REFERENCE.md](docs/REFERENCE.md) | **Every element defined once** — concepts, commands, run-directory files, reuse, licences, figures, the exit standard |
| [RUN_PLAN.md](docs/RUN_PLAN.md) | How the plan is built and how to read it |
| [RESUME.md](docs/RESUME.md) | Resuming a run, and reuse across runs |
| [REPORTING.md](docs/REPORTING.md) | How the documents are assembled |
| [REFERENCES.md](docs/REFERENCES.md) | Reference data: declaring, fetching, verifying |

**Agents:** you run scProfile and write up what it produced.

| document | what it covers |
|---|---|
| [AGENT_CONTRACT.md](docs/AGENT_CONTRACT.md) | Which half of the work is the tool's and which is yours, why the tool does not write, the order of the writing phase, and what an agent must not do |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | Part three describes each element of the agentic layer: the composed fallback, the brief, the review ledger, the agenda and its execution modes, and how the skill and a plugin's template combine |
| [.claude/skills/result-section/](.claude/skills/result-section/) | The writing skill itself, and the per-method templates it is used with |

**Maintaining a plugin:** writing or repairing the methods themselves.

| document | what it covers |
|---|---|
| [PLUGIN_DESIGN.md](docs/PLUGIN_DESIGN.md) | Writing a plugin |
| [MAINTAINING_PLUGINS.md](docs/MAINTAINING_PLUGINS.md) | Keeping a plugin's declaration true |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | How the host, plugins and environments fit together |
| [EXECUTION.md](docs/EXECUTION.md) | Scheduling, cores, memory and waves |
| [DEVLOG.md](docs/DEVLOG.md) | Development history |
