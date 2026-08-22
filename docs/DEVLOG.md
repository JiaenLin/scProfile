# Development log

One entry per test-fix cycle against a real cohort. Every finding is prefixed with the LAYER that
owns it — environment, declaration, method, host — and names the commit that fixed it. A cycle
that found nothing says so in one line: a log of only the interesting cycles is a log that hides
the boring evidence that things worked.

`method` findings are usually **not defects**. They are said plainly, because a log that records
only faults teaches the next reader that every failure is somebody's fault.

---

## 2026-08-22 — cycle 1 (PBS 676908)

tested: validate / doctor / selftest / plan --audit --report / run(cellcycle, silhouette) /
        deliberate environment breakage and the repair loop

found:  [host] a ONE-FILE plugin was executed directly instead of through `_entry.py`, so it
              defined its names, exited 0 and wrote nothing — indistinguishable from a plugin that
              finished with no results. The shape now says how it is launched → 667eec0
        [host] `selftest` looked for `kernel.path / "selftest.py"`, a path inside a file for that
              shape, so every one-file plugin was listed as shipping none. It ships one, and it
              would have caught the above at install time → 667eec0
        [host] `in.json` carried `counts_layer`/`lognorm_layer` and never `counts`/`lognorm`, so
              `ctx.counts()` returned None on an object with a counts layer and `ctx.X` fell back
              to `.X` silently → 2807f90
        [host] `plan` truncated the upstream constraint on use at 100 characters, cutting the
              "it must NOT" clause — the half that says what may not be claimed → 2807f90
        [host] a run in which every plugin refused still wrote a 3.21 GB `cohort_profiled.h5ad`
              that was a copy of its input → 2807f90
        [method] velocity's guard refused because `--assay` was neither passed nor detectable.
              NOT a defect — the guard is correct and the job script should pass `--assay`.

not observed: the repair loop. The deliberate breakage never ran, because the assay guard refused
        velocity before the environment was touched. The chain diagnose → rebuild → retry-once →
        report-drift remains UNWITNESSED end to end.

clean:  6 suites, validate 0 errors. cellcycle ran to completion on 100,713 cells in 63 s;
        all 6 environments that ship a selftest passed.

format: nothing in the format needed changing to accommodate the third-party plugin. The host had
        never implemented the format its own docs describe. That is the strongest reading of the
        format test available: the plugin was right and the host was wrong.

---

## 2026-08-22 — cycle 2 (PBS 676943 fast, 676944 repair-loop)

Split in two so the repair loop's rebuild could not eat the walltime of everything else.

tested: cycle 1's four fixes on real data; the repair loop with `--assay` passed so the guard
        would not refuse before the environment was reached

confirmed: the third-party plugin RAN — 51 s, 14 populations, obs + table merged, its own report
        page; its selftest ran for the first time and passed; `in.json` carries `counts` and
        `lognorm`; `cellcycle` changed from "Scored from X" to "Scored from `layers['lognorm']`";
        the constraint printed whole, including the "must NOT" clause cycle 1 cut.

**REPAIR LOOP OBSERVED END TO END** (676944): `FAILED velocity (3s)` →
        `ModuleNotFoundError: No module named 'scvelo'` → `[environment] a package the plugin
        imports is not in its environment` → `REPAIRING: rebuilding velocity's environment and
        retrying once` → conda rebuild + 16 pinned pip packages → install-time `selftest ok` →
        `RECOVERED after rebuild (13s)` → `[environment] ... The installed environment had
        DRIFTED` → `repaired: ['velocity']`. Retried once, did not loop, was not silent, right
        layer.

found:  [host] `objects/` was the only mkdir creating the run's output directory; making it
              conditional killed `report.json` on a run where everything refused → b3bbf4e
        [host] `merged_slots` is truthy for a plugin that ran and REFUSED, so 676944 still wrote
              3.21 GB for a velocity run that contributed nothing → 79e12b4
        [host] the sentinel guarantee was asserted and unenforceable. Every plugin's caveats said
              sentinels "are not treated as a population" beside a table whose worst population
              was `UNRESOLVED` (-0.142, 475 cells). `ctx.real_cells()` is the mechanism,
              `feedback.sentinel_as_population` the check → 905480f
        [method] velocity refused for want of spliced counts. NOT a defect — `plan` had already
              said `[data] velocity --search <project>` and the flag was not passed.

harness: 676943 and 676944 shared `--prefix` concurrently, so the repair job's `--force` rebuild
        deleted `scprofile-velocity` while the other job's selftest read it. That is the two jobs
        colliding, not the tool. One prefix, one job, from cycle 3 on.

clean:  6 suites, validate 0 errors.

## 2026-08-22 — cycle 3 (PBS 676969)

tested: the three cycle-2 fixes, each against the exact log line that had shown the defect

found:  nothing.

        sentinel: `separation_by_label.csv` has 13 rows and no sentinel among them (was 14 with
        `UNRESOLVED` worst); the host's own check reported nothing; both the host caveat — now
        naming counts, `EXCLUDED 2,086, UNRESOLVED 2,139` — and the plugin's appear.
        empty run: `README.md`, `report/index.html`, `report.json`, `object: None`, no crash.
        ran-but-produced-nothing: velocity refused, `object: None`, no `cohort_profiled.h5ad`,
        and the message names velocity rather than claiming nothing ran.

open:   a run that produces nothing still leaves its 3.14 GB compatibility copy
        (`input_for_kernels.h5ad`) behind. It is a legitimate cached working file and reusable,
        so it is recorded here rather than deleted on a guess.

clean:  6 suites, validate 0 errors.
