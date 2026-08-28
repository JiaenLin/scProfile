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
nothing is finished. Re-running it costs the same and answers the same, and a resume that
retries empty units silently converts a negative result into an unstable one — the next run may
differ for unrelated reasons and nobody will know which run the emptiness came from. Pass
`--force-all` to discard that judgement deliberately.

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
