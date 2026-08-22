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

## 2026-08-22 — cycle 4 (PBS 677258 build, 677295 run, 677296 repair)

Split into phases as separate jobs, one at a time against one `--prefix`. `setup/dev_cycle.pbs`
runs them and names no project.

tested: resolve + install of a SHARED environment / selftest of all 8 / plan --audit --report over
        every plugin and over a restricted one / run(decoupler, silhouette) merging into one object

**SHARED ENVIRONMENT BUILT AND USED, for the first time** (677258): `shared by: decoupler, liana,
        pseudotime, velocity` -> one conda create + one pip resolve of 24 pins ->
        `proved for 4 of 4 member(s)` -> `installed at .../scprofile-env-3cd799b82e`. 11m38s.
        Afterwards `doctor` reports all four as `installed ... shared with ...`, and 677295's
        selftest ran each of them out of that one directory.

**A ONE-FILE PLUGIN WITH ITS OWN ENVIRONMENT RAN THROUGH `_entry.py`** (677295): `decoupler ok
        281s  674 regulators scored per cell`, `prior: 39,961 edges, 1,114 regulators for mouse`,
        `merged obsm: X_tf_activity`. Two plugins into one 3.48 GB object, one report, one README.

**THE REPAIR LOOP CLOSED ON A SHARED ENVIRONMENT** (677296): `scvelo` removed from the resolved
        environment by hand -> `FAILED velocity (2s)` -> `ModuleNotFoundError: No module named
        'scvelo'` -> `[environment] a package the plugin imports is not in its environment` ->
        `REPAIRING: rebuilding velocity's environment and retrying once` + `that environment is
        scprofile-env-3cd799b82e, SHARED WITH decoupler, liana, pseudotime - all of them are
        rebuilt and re-proved` -> `proved for 4 of 4 member(s)` -> `RECOVERED after rebuild (12s)`
        -> `[environment] ... The installed environment had DRIFTED` -> `repaired: ['velocity']`.
        Retried once, did not loop, was not silent, right layer - and this time it named what a
        `--force` rebuild of a shared environment actually does.

found:  [host] `install` read the named plugin's own `lock.yml`. Resolution decided the DIRECTORY
              and the lock decided the CONTENT, so an environment shared by four was built from
              one of them and the other three would have found a finished-looking directory with
              a current stamp and none of their packages. A `requires`-shaped plugin has no lock
              at all and could not be installed by any path -> e2c5b0a
        [host] a requirement could express only python and pip. An R plugin pinning `r-base` and
              60 conda packages resolved to NOTHING: absent from the environment count, handed a
              private path nobody planned. Five fields now, and conda specs are carried verbatim
              because `petsc4py=3.20` is a prefix match and `==3.20` is a version that does not
              exist -> e2c5b0a
        [host] NOT CLASHING IS NOT BEING COMPATIBLE. That same R requirement contradicts nothing,
              so greedy first-fit put it in the python group: one 6 GB environment holding two
              language stacks, on an absence of evidence. Sharing now needs an overlap -> e2c5b0a
        [host] `env_state` looked only at the per-plugin path, so a built, stamped, proved shared
              environment read as `missing` to doctor, plan and install. And the search is not the
              same question as "is THIS directory finished": a half-built group directory made the
              search walk past it and report the old environment as current -> e2c5b0a
        [host] `inject` gated the run and was invisible to the plan. `declare.available` is now the
              one answer both ask -> e2c5b0a
        [host] `plan --kernel a,b --audit` reported an ERROR for every plugin left out, because the
              completeness rule was stated over every plugin on disk. An audit that cannot be run
              clean on a legitimate invocation is one people learn to silence -> 8ea8c2c
        [host] **"an array carries no barcodes" was a gap, stated as a fact about arrays.** The
              host excludes NaN-embedding cells from every plugin, so decoupler was handed 98,627
              of 100,713 cells, returned 98,627 rows, and the merge refused it for not covering
              100,713 - refused a plugin for returning exactly the cells it was given. `emit_obsm`
              writes the barcodes; the merge aligns by them, and a per-unit plugin's arrays can
              cross units for the same reason -> 16aaf4b. Log: `decoupler obsm['X_tf_activity']:
              98,627 of 100,713 cells covered; the rest are NaN`
        [host] the 3 GB `input_for_kernels.h5ad` was called "a reusable cached working file" and
              was neither: nothing read it again and nothing named it. A receipt makes it reusable
              and `report.json`/`README` name it as what the plugins ACTUALLY read -> ba9ec53
        [declaration] decoupler reported the annotator sentinel `UNRESOLVED` as a group in
              `activity_by_label.csv`, over 2,139 cells. The host's own check caught it. That is
              the SECOND of two plugins to make this exact mistake, which is a statement about the
              affordance: `ctx.populations()` now answers it once and attaches the caveat -> fd5d664
        [docs] README, PLUGIN_DESIGN, MAINTAINING_PLUGINS and plugin.py's own docstring still
              described `PLUGIN["env"]` and one pinned environment per kernel -> 55579de, bf436b1

clean:  7 suites, validate 0 errors. plan --audit over all 10 plugins: `0 error(s), 0 warning(s)`,
        `wrote .../out/run_plan.html`. Restricted: `checked: all 2 known plugin(s) appear exactly
        once`, which was impossible before 8ea8c2c.

format: nothing in the plugin format had to change to accommodate anything. The third-party
        plugin ran unchanged (`silhouette ok 161s`); decoupler needed a builder that could read
        the format's own `requires` block, which is a host defect and not a format one.

## 2026-08-22 — cycle 5 (PBS 677332)

A confirmation cycle at the final commit, `fb0e7b4`, against the exact log lines that had shown
cycle 4's last two defects.

tested: the sentinel affordance / the compatibility copy's receipt / the whole path again on the
        final code — validate, 8 selftests, plan --audit --report over every plugin, run

found:  nothing.

        sentinel: `decoupler_activity_by_label.csv` has 13 rows and no sentinel among them (was
        14, with an `UNRESOLVED` row over 2,139 cells), the host's own check reported nothing —
        `diagnoses: []` where cycle 4 had one — and the caveat `ctx.populations()` attaches is in
        the run: *"2,139 cells carry an annotator sentinel and are NOT summarised as a
        population"*.
        compatibility copy: `reusing the compatibility copy already at input_for_kernels.h5ad
        (3.14 GB); it was made from this same object` — a 3.14 GB rewrite that every previous run
        into the same `--out` had done. `report.json` carries `input_read_by_kernels` and the
        README says what that file is.
        merge by barcode, again: `decoupler obsm['X_tf_activity']: 98,627 of 100,713 cells
        covered; the rest are NaN` -> `merged obsm: X_tf_activity`, on the final code.
        plan: `0 error(s), 0 warning(s)` over all 10 plugins; `wrote .../out/run_plan.html`.
        restricted: `checked: all 2 known plugin(s) appear exactly once`.

clean:  7 suites, validate 0 errors, on `fb0e7b4`.
