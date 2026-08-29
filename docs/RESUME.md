# Resuming a run: what is already on disk, and what is left

`scprofile status --out <RUNDIR>` reads a run directory and says, per instance, whether it is
finished and whether it is still valid. `scprofile run --resume` then computes only what is
outstanding.

```
scprofile status --out runs/<tool>/<stage>/<RUNKEY>          # ask first, costs nothing
scprofile run --resume --out runs/<tool>/<stage>/<RUNKEY> …  # then run only what is left
```

## Why this exists

Re-running what is already done is not a neutral cost. It is the cost that decides whether a
change gets checked against **real data** or against a fixture: a change to a figure does not
need the inference recomputed, but if the only way to see the figure is a full run, the figure
gets checked on synthetic data, or on nothing. **That is a correctness problem wearing a
performance problem's clothes.**

## The five states

They are `manifest.py`'s, not new ones. A unit directory means what the manifest already says
it means, and this is the vocabulary for reading it back.

| state | on disk | outstanding? |
|---|---|---|
| `done` | `out.json` with entries | no |
| `empty` | `out.json`, no entries | **no** — see below |
| `stale` | complete, but a different plugin version produced it | yes |
| `died` | inputs staged, no `out.json` (or a truncated one) | yes |
| `absent` | never staged | yes |

**`empty` is a RESULT, not a failure.** A unit where the method ran correctly and returned
nothing is finished. Re-running it costs the same and answers the same, and Re-running an empty unit costs the same and returns the same. Pass `--force-all` to redo
empty units deliberately.

**`stale` is what makes `--resume` safe to use at all.** The check compares the plugin version
recorded in `out.json` against the version that would run now. Without it, a resume across a
plugin change silently produces one run directory holding units from two versions of the code —
each internally consistent, the set of them describing nothing, and no field anywhere saying so.
That is the same failure as a run key naming a commit the run did not use.

A corollary that is easy to get backwards: **`empty` from an older version is `stale`, not
`empty`.** A negative result from code that has since changed is not evidence about the new
code, and "it found nothing last time" is the least safe thing to carry across a change. The
version check therefore runs *before* the empty check.

## Reusing a finished run WITHOUT re-running it

`status` answers what is on disk. For development, the more useful fact is that **a finished run
already contains its own inputs to every figure.** Each per-unit directory holds what the kernel
was given (`in.json`, the staged matrices) and what it returned (`out.json`, `tables/`), and the
per-unit tables are the same quantities the panels are drawn from.

So a figure can be developed against a completed run's tables directly, at no compute cost,
before anything is submitted. That is the intended loop:

1. `status --out` — confirm the run is complete.
2. Read the per-unit table the panel draws from.
3. Iterate on the drawing locally, looking at the rendered figure each time.
4. Only then bump the plugin version and re-run, which `status` will now report as `stale`.

Step 4 is not optional and `status` will say so: a figure change *does* change what a unit
produces, so the units that predate it are stale and the tool will decline to reuse them. The
saving is not in skipping the final run — it is in not paying for the twenty runs it took to
get the figure right.

## What `--resume` does not do

- It does not check the **input object**. If the `.h5ad` changed underneath a run directory,
  nothing here detects it; the run key and `INPUTS.json` are what record that.
- It does not re-render figures without re-running the kernel. Drawing happens inside the
  kernel, so a figure change requires the instance to run again. Splitting inference from
  drawing would remove that, and is the obvious next step for this module.
- It does not merge across run directories. A resume reuses instances **in the directory it was
  pointed at** and nowhere else.

---

# Across runs: the landscape, and why provenance alone is not enough

`resume` answers *"what is left in THIS directory"*. It cannot help the ordinary case, because
**every run gets a new run key** — so a result computed last week sits one directory away and is
recomputed from nothing. On a wrapped method taking hours per unit, that is the difference
between iterating and not.

```
scprofile landscape --root runs/<tool>/<stage>                 # inventory
scprofile landscape --root runs/<tool>/<stage> --h5ad OBJ      # a PLAN
```

Without `--h5ad` it is an inventory. With it, it is a plan — because **the input decides
reusability as much as the code does**, and without knowing the input nothing can honestly be
called reusable.

## The decision has three independent inputs

A result is reused only if all three agree. They fail for different reasons and none substitutes
for another.

### 1. Does it exist, and in what state? — `resume`

Read from the unit directory, using `manifest.py`'s own vocabulary:

| state | on disk | outstanding |
|---|---|---|
| `done` | `out.json` with entries | no |
| `empty` | `out.json`, no entries | **no — it is a RESULT** |
| `stale` | complete, but a different plugin version made it | yes |
| `died` | inputs staged, no `out.json`, or a truncated one | yes |
| `absent` | never staged | yes |

### 2. Is it still valid? — the reuse key

A hash of **only** what determines the result:

```
plugin · version · unit · input path · input size · input mtime · params · keys
```

The run key, the date, the machine and who launched it are **excluded on purpose** — include any
of them and nothing is ever reusable. When the key differs, the map names the fields that differ,
so `version: '0.3.1' -> '0.4.0'` tells you that you changed the code and `input_mtime` tells you
the object was rebuilt underneath you.

**What this cannot check, printed on every report:** a run records the input's PATH and no digest
of its contents. An object rebuilt at the same path with the same size and mtime is
indistinguishable from the original by anything written down. The report states which parts of
the key were verified against the filesystem just now and which were taken on trust from what the
run wrote.

### 3. Is it TRUSTWORTHY? — `RUN_CARD.json`

**Provenance is not trust, and reuse on provenance alone launders errors.** A unit that ran to
completion and produced nonsense has the same inputs and the same code as one that did not. The
key cannot tell them apart, and reusing the bad one carries it into every later run with a trail
that makes it look verified.

So each run publishes its own verdict on its own output, per instance:

| verdict | what it means | reusable |
|---|---|---|
| `ok` | completed, nothing objected | yes |
| `empty` | ran and produced nothing — a RESULT | yes |
| `suspect` | the plugin **contradicted its own output**, or a diagnosis was raised against the **METHOD** | no |
| `failed` | did not complete | no |
| `unknown` | no card, or a card predating this field | **no** |

`unknown` defaulting to not-reusable is the only safe default: **a map that treats silence as
approval launders every result it has no information about.** Every run made before the card
existed is therefore `unknown`, and correctly not reused.

A **method**-layer diagnosis makes a result suspect. An **environment**- or **host**-layer one
does not — those are about the machinery around the answer, not the answer itself.

The card also records what the run could NOT check about itself:
- whether any figure was **looked at** (`scprofile review`),
- whether the numbers are **correct**, as opposed to merely unobjected-to.

## So: run, re-run, or reuse?

| the map says | why | what to do |
|---|---|---|
| `REUSE` | key matches, state finished, verdict trusted | nothing — it is already computed |
| `RUN` … *version changed* | you changed the plugin | re-run: the old result is a different quantity |
| `RUN` … *input_mtime changed* | the object was rebuilt | re-run: nothing downstream of it is valid |
| `RUN` … *calls it 'suspect'* | the producing run objected to its own output | look at it before anything else |
| `RUN` … *calls it 'unknown'* | no card | re-run, or inspect and decide deliberately |
| `RUN` … *never run here* | genuinely new work | run it |

## What is NOT yet automatic

**The landscape reports; adoption is a separate, explicit step.** `scprofile licence`
grants a licence and `licence.adopt()` materialises a licensed instance into a new run by
hardlink. There is no flag that adopts automatically as part of `run`.

