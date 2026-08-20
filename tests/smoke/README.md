# The end-to-end smoke test

`tests/test_contract.py` and `tests/test_perunit.py` drive the merge, schedule and report
functions directly. They are fast, they need no scientific stack, and they prove the rules in
isolation.

This is the other kind. It builds a synthetic object, runs the host over it as a user would, and
then opens **what was actually written** — the object, `report.json`, the HTML, the README, the
files in `tables/` and `objects/` — and asserts that the rules survived the trip through
subprocesses, a compatibility copy, concurrent threads, an h5ad write and an HTML render.

```
tests/smoke/run_smoke.sh <PYTHON> <WORKDIR> [<ENV_PREFIX>]
```

On a cluster, wrap that line in a batch job. It starts subprocesses and fits a model; a scheduler
exists so that work like this is accounted for.

## Why it is not optional

Four defects reached a tagged commit past a green unit-test suite, and every one was found here:

| what | why nothing else could see it |
|---|---|
| a keyword the wrapped scanpy function forbids | only a real call rejects it |
| `[None]` in a provenance field | nothing raises until `write_h5ad`, and no unit test writes one |
| the core budget divided twice, compounding | visible only by comparing the printed plan against the printed wave **in the same log** |
| a README describing a directory it was written before | the file count is only wrong on disk |

## `scprofile selftest`

Step 2 of the driver is `scprofile selftest`, which runs each plugin's selftest **with that
plugin's own interpreter**. It replaced a shell loop over `kernels/*/selftest.py` that used the
host python for all of them and died on `No module named scvelo` — reporting a missing dependency
that is not missing anywhere it matters.

The subcommand exists for a second reason. A selftest used to run only at *install* time, which
answers "did this environment work on the day it was built". Environments drift, and a plugin
declaring `needs_env: false` has no install step at all — so its selftest never ran automatically,
and that is precisely how a keyword the wrapped function forbids reached a real cohort.

It reports four outcomes and treats exactly one of them as success. *Passed*, *failed*, *could not
run* (no environment — which has a fix, and is not the same as a broken environment) and *has no
selftest*. Returning 0 because nothing could run would be a check that passes for its own reasons.

## The per-unit plugin

`tests/smoke/perunit/` is a plugin that computes nothing. It exists because **nine of the ten
defects fixed on 2026-08-20 lived on the per-unit path, and no plugin in the tree walks it** —
every `per_unit` plugin shipped so far is `status: planned`, and the host skips anything not
built. A code path that no delivered run exercises is one whose bugs are found by users.

So this one is supplied through `$SCPROFILE_KERNELS`, which is the supported route for a site
plugin and exactly how those defects would have arrived. It writes one of everything the contract
has — an obs column covering only its own unit's cells, an array it knows cannot cross units, a
table, a figure with a vector and a source, and a side-car object under a **deliberately fixed
basename**, so a filename collision between units would be visible rather than silent.

Four units across two other plugins is also what made the budget arithmetic observable. A wave of
one instance divides correctly however many times you divide it.

## What the fixture is, and is not

`tests/make_fixture.py` — one directory up, shared with the rest of the tests — generates every
value from a seeded generator. Nothing in it is data and no number produced from it means
anything.

Several of its features are load-bearing rather than decorative. `X` is **lognormalised, not
counts**, which is what an integrated object actually delivers and the thing that makes a second
log transform possible. Its unspliced counts **lead** spliced along a latent axis, so a velocity
fit has real signal to find rather than noise. It carries **annotator sentinels** in the label
column, because a sentinel is not a cell type and must be handled as one thing and not the other.
It carries **several samples**, because a sample column is what turns a `per_unit` plugin into
more than one instance. And it carries an upstream `constraint_on_use` in `uns`, so the host has
one to find and carry into the report.
