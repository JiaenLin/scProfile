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

## 2026-08-22 — cycle 6 (PBS 677509 build, 677510 build, 677555 build, ...)

The cycle that converted the last two plugins, and the one that found the most. Nothing here was
looked for: every finding is something the conversion, or the first attempt to build all nine
environments together, walked into.

converted: `velocity` (5 files, 1,286 lines) and `cellcycle` (2 files, 329 lines) to one file
        each. `kernels/` is nine `.py` files and no directories.

**THE SHAPE HAD TO GROW TO TAKE THEM, TWICE, AND BOTH GAPS DELETE RATHER THAN REFUSE.**

        [host] A ONE-FILE PLUGIN COULD NOT HAVE A GUARD. `guard_verdict` reached for
              `kernel.path / "guard.py"`, which for this shape is a path inside a file and can
              never exist - so converting a guarded plugin to the shape the host prefers removed
              its check with no error, no line in the log, and the first dataset the guard existed
              to refuse analysed and reported. `def guard(g)` in the file, launched by the SHAPE
              through `_entry.py --guard`, exactly as `argv` and `selftest_argv` already were
              → 5182ec6
        [host] `produces` COULD NOT DESCRIBE VELOCITY'S OUTPUTS. `obs[latent_time]` exists only
              in dynamical mode and `obsm[velocity_*]` is named at run time; `undeclared()`
              understood the glob and `declaration_drift()` understood neither - two functions
              reading one declaration and disagreeing. A correct run would have reported
              `obsm[velocity_*]` TWICE, as a promise broken and as an output undeclared. `?` marks
              an output whose absence is not drift, and both now glob on the NAME: in fnmatch
              `[phase]` is a character class, so globbing `slot[name]` makes `obs[phase]` match
              `obsp` and not itself → 5182ec6

The layer search MOVED into the host rather than being rewritten: `scprofile/sources.py`, reached
through `ctx.source_layers()`. It was never about velocity - any plugin needing what the ALIGNER
produced is in the same position, and the host is the only party holding the upstream chain.

found:  [host] **THE PLAN PROMISED A DIRECTORY THE RUN COULD NOT REACH.** Two walks for one
              question, in two layers. `plan` walks to depth 14 with 400,000 visits, pruning
              anything whose name CONTAINS `__STARtmp`; the walk a plugin runs went to depth 3,
              4,000 visits, and an exact-name skip list that `S1__STARtmp` does not match.
              STARsolo delivers `<sample>_Solo.out/Velocyto/filtered/` at DEPTH 9, so the plan
              could name the directory holding the spliced counts and the run, given exactly that
              root, could not reach it. Depth, cap and prune list are one statement each now, and
              `find` reports `exhausted` - the run side had never learned what the plan side
              already knew, that a search which gave up and a project that has nothing return the
              same empty list → e87e29e. Separately, `run` harvested fewer leads than `plan`:
              the recorded chain but not the directories around the object → 5182ec6
        [host] **THE WAVE STARTED EVERY INSTANCE AT ONCE.** `EXECUTION.md` §4 has stated
              `min(budget / smallest_declared, ready)` since it was written and nothing
              implemented it. `_budget` divides the share each instance is TOLD it has, which is
              a different question from how many run. Nine plugins, three of them `per_unit`, ten
              samples: 37 instances, 37 subprocesses, each opening a 3 GB object, on a node asked
              for eight cores - every one correctly told `cores: 1` → 623d186
        [host] **AND THE SHARE NEVER REACHED THE ONE POOL A PLUGIN CANNOT CONTROL.** numpy's BLAS
              sizes itself from `OMP_NUM_THREADS` at import, before any plugin code runs, and
              inherits what the job script exported for its own sake. Eight instances on sixteen
              cores is 128 BLAS threads, with every instance correctly told `cores: 1`. The
              runner sets all six thread variables from the manifest it just wrote → e4dfcf5
        [host] **FIVE PLUGINS READ `(mask, groups)` AS `(populations, dropped)`.** That is one bad
              affordance, not five mistakes: `len(pops)` becomes the CELL COUNT, so a refusal that
              should fire never does and a headline claims a hundred thousand populations, and
              `if dropped:` asks the truth value of an array and raises. liana, cellchat and
              abundance would each have died before reaching their method. It still unpacks as
              `(mask, groups)`, and it now carries `.names` and `.dropped`, which is what all five
              were reaching for. `validate` refuses the wrong destructuring by name - and caught
              the fifth, cellchat, within a minute of existing → 5584e3c
        [host] `ctx.emit_figure` overrode the publication DPI with a hard 200 and never closed a
              figure. Neither could be noticed: SEVEN one-file plugins had shipped and not one
              drew anything, so the figure half of the contract was entirely unexercised until
              the two plugins that draw were converted. With it, `ctx.plot()`, `ctx.figure` and
              `ctx.layers()` - a plugin should not import a host module to draw, and
              `list(adata.layers)` yields anndata's `None` alias for X → 5182ec6
        [host] **A FAILED BUILD TAUGHT US NOTHING ABOUT THE OTHER EIGHT.** The R step of an
              eight-member group failed; the pip half - 130 packages, 25 minutes - was complete,
              and eight selftests would have taken a minute. `install` raised before any of them,
              `doctor` reported all eight `stale`, and the job ended knowing nothing about eight
              plugins never proved on this machine. That is one defect learned per job for however
              many defects there are. The selftests now run anyway, reported as DIAGNOSTIC; no
              stamp is written and `install` still refuses → adf7d32
        [host] an aligner writes the same counts twice - `Velocyto/filtered/` beside
              `Velocyto/raw/` - and `attach` read both: 22 GB of MatrixMarket text parsed and
              discarded for identical cells. Cheapest first, from the size the walk already had,
              and a source whose scope is already covered is skipped BEFORE it is opened, which
              is decidable from its path → 5412b66, af1553c
        [host] **A PLUGIN COULD NOT REACH THE BINARIES ITS OWN ENVIRONMENT PROVIDES.** cellchat's
              method is R: it runs `Rscript`, found through PATH. Launching `<env>/bin/python` by
              absolute path does not put `<env>/bin` on PATH - that is what `conda activate` does
              - so the plugin searched the system's PATH and the failure read as
              `no Rscript on PATH - this plugin's environment did not provide R`, about an
              environment containing R 4.3 and a complete CellChat. `_install_r` learned exactly
              this at PBS 676357 and fixed it for the one subprocess IT launches; the runner,
              which launches every plugin and every selftest, did not → 9e20155
        [host] **A SELFTEST WITH A CAPTURED PIPE AND NO TIMEOUT IS A BUILD THAT HANGS.** Watched
              live on PBS 677555: decoupler's fetches a published prior over the network,
              `capture_output=True` held every byte until exit, and there was no limit - so
              `install` sat with no output, having proved nothing, and would have until the job's
              sixteen-hour walltime. `run` learned this already and streams to a named log;
              `selftest` had not. Named file, 30-minute default, reported as stuck rather than
              slow → 87f89bf
        [host] `sources.attach` had never executed on anything - velocity refused for want of
              counts in every previous cycle - and could not have survived a real object: a
              `lil_matrix((100_713, 34_290))` per layer is a Python list per row, filled through
              scipy's Python-level fancy-index assignment, one source at a time. Row/column/value
              arrays concatenated once instead; int32 indices, float32 values. The SEARCH half,
              which is the part that was proven, is untouched → 523b934

        [declaration] **abundance, liana and cellchat each destructured `ctx.populations()`
              wrongly** and would have crashed → 5584e3c. abundance was found by reading, cellchat
              by the check that reading produced.
        [declaration] **cellchat named five R packages; NMF, presto and CellChat need about
              forty-five.** `remotes` runs with `dependencies = FALSE` so nothing is chosen at
              install time, which makes a forgotten dependency a line to add rather than an
              unpinned install nobody sees - and the install receipt named them:
              `ERROR: dependencies 'registry', 'rngtools', ... are not available for package
              'NMF'` → adf7d32
        [declaration] **scenic started the node's worth of dask workers, once per sample.**
              `client_or_address="local"` builds a LocalCluster sized from
              `multiprocessing.cpu_count()`; scenic is `per_unit: sample`, so a ten-sample cohort
              is ten times the machine in workers. `ctx.effect` is the mechanism and the example
              in its own docstring → c49b3f1
        [declaration] cellcycle grouped its per-population figure by the RAW label column, so an
              annotator's refusal to call a cell type appeared as a population with a cycling
              fraction. velocity's per-population table did the same, marked with an
              `is_sentinel` column and sorted last. Both use `ctx.populations()` now → 5182ec6

**AND THEN THE SELFTESTS RAN — for the first time, all eight members of one environment, only
because a failed build now runs them anyway** (PBS 677555, `proved for 4 of 8 member(s): de,
liana, pseudotime, velocity`). Four failures, in three layers, none of which would have been seen
this cycle: the previous attempt's R step failed and `install` raised before any selftest ran.

        [declaration] **cellcycle: `TypeError: score_genes() got an unexpected keyword argument
              'layer'`** on scanpy 1.10.4. `score_genes` in the scanpy this plugin DECLARES takes
              no `layer` argument - it was added later - so `layer=` reaches it through
              `score_genes_cell_cycle`'s **kwargs and raises. Its UPSTREAM record quoted a
              signature that HAD it, read from whatever scanpy the host interpreter happened to
              carry. **This is the plugin that ran a whole cohort in cycle 1 with
              `needs_env: false`**, and giving it a declared environment is what exposed that its
              call was well-formed against nothing in particular → 01c93db
        [declaration] **abundance: `ModuleNotFoundError: No module named 'filelock'`.** pertpy
              imports it at module scope and does not declare it → 01c93db
        [declaration] **decoupler: `ModuleNotFoundError: No module named 'omnipath'`**, from
              INSIDE `get_collectri` - imported lazily, so nothing about installing or importing
              decoupler notices, and it surfaces on the one call this plugin exists to make
              → 7234fec
        [declaration] **cellchat named five R packages and CellChat needs about forty-five**, and
              the install receipt named the first twelve itself. Fixed in the declaration; the
              `no Rscript on PATH` half of the same plugin's failure was the HOST defect above.

        Three of those four are the same shape: **a dependency the wrapped tool needs and its own
        metadata does not declare.** filelock behind pertpy, omnipath behind decoupler,
        forty-four R packages behind CellChat. All three surfaced in a selftest rather than in
        somebody's run, which is what the selftest is for.

**AND THEN THE RUN** (PBS 677677, all ten plugins, `--all`, 100,713 cells, 12-core budget).

        `plan --audit --report` over every plugin: `checked: all 10 known plugin(s) appear exactly
        once`, `0 error(s), 0 warning(s)`, `wrote .../out/run_plan.html`. Every plugin `runnable`.
        `plan: 37 instance(s) in 1 wave(s), 12 core(s), 10 unit(s)` and the wave line ends
        **`[12 at a time of 27]`** - the concurrency cap 623d186 added, biting on a real wave.

        [declaration] **scenic's environment had no anndata.** Ten instances, one line each:
              `NOT RUN scenic[S1] - scenic's interpreter cannot read this object even
              re-encoded`, and above them `the compatibility copy did not help either:
              ModuleNotFoundError: No module named 'anndata'`. `_entry.py` reads the object before
              a plugin is called, so an environment without anndata cannot run ANY plugin - and
              the failure surfaces as a problem with the OBJECT → c7adf43
        [host] and nothing declared or checked THE CONTRACT'S OWN DEPENDENCY. `_entry.py` read
              with `scanpy.read_h5ad`, making scanpy an undeclared requirement of the contract
              imposed on every plugin's environment; it reads with anndata now, and
              `declare.check` refuses a requirement that brings python packages and does not name
              it. The check found **two more**: abundance and de work only because they SHARE an
              environment with plugins that do name anndata → c7adf43

        **THE LAYER SEARCH WORKED END TO END, on the real project, in its moved form** - the
        half of velocity that had never run on anything:

            visited 20,064 director(ies), found 503 candidate(s)
            mtx  filtered: 13,824/13,824 barcodes matched (100.0%) within sample S1   [x10]
            141 further candidate(s) not opened: every cell was already covered
            attached from 10 source(s): 98,627/98,627 cells (100.0%) have spliced/unspliced counts

        ...and velocity then refused, because of a COLUMN INDEX.

        [host] `features.tsv` is `<gene id>	<symbol>	<type>` and `sources.load` read column 0.
              The object is indexed by SYMBOLS: 466 of 34,290 genes matched,
              `filter_and_normalize` dropped 34,286 for want of shared counts, and velocity
              refused because `only 4 genes survived selection` - **a refusal about the DATA whose
              cause was a column index**, and one that would have been believed. Every field is a
              candidate now and `attach` takes whichever overlaps the object more → b318bcd
        [declaration] de raised `numpy.linalg.LinAlgError: Singular matrix` from inside pydeseq2.
              `~ age + diet + chemistry + batch`: chemistry takes one value for every aged sample
              and another for every young one. `RUN_PLAN.md` says an imbalance, a confound, even
              a COMPLETE confound all run with a caveat - so the terms that add no estimable
              column are dropped, in the order given, and NAMED → b318bcd
        [host] and the loop could only say `no known failure signature matched, so the layer is
              not established`. Correct, and useless. A singular model matrix is now a METHOD
              signature saying the terms are collinear and that it is a property of the DESIGN
              TABLE, not of the data or the tool → b318bcd

        [method] velocity's refusal on the FIRST run was not a method finding at all - see the
              column index above. `pseudotime` reported `No velocity field was on this object, so
              the ordering comes from CONNECTIVITY alone`, which is correct and is the caveat
              that plugin exists to write.

harness: **three of my own, all in the job script or the suites, and all of the same family.**

        `[ -n "$MANAGER_PATH" ] && export PATH=...` is the last command of its statement, so with
        the variable unset the test fails, `set -e` fires, and the job ends before the live log is
        even opened - which looks exactly like a job that produced nothing → b27ed62.

        `$PY "$t" | tail -25 | sed ...` in a failing branch is a PIPELINE, and under
        `set -o pipefail` its status is the failing python's - so the `if` returned non-zero and
        `set -e` ended PBS 677608 on the first failing suite instead of reporting all seven. The
        exact trap this file's own header warns about, reintroduced by the block added to report
        suite failures → 0e5f951.

        And running the suites from a directory other than the repository root, for the first
        time ever, found that **three checks in `test_perunit` had been passing on ZERO FILES**:
        `Path("scprofile").rglob(...)` returns nothing from anywhere else, so `no file uses a
        module it did not import` and `nothing iterates layers raw any more` were both green over
        an empty list. That is the failure `test_portability` guards its own scan against - "a
        clean report from a check that ran on zero files is the worst kind" - written down in one
        suite and not applied in the next. Rooted at `__file__`, file counts asserted, and all
        seven pass from `/tmp` → 0e5f951.

        The job script also grew `ALL=1`, `SEARCH`, `CORES` and `MANAGER_PATH` → 2a28a40, 5f719d1.
        `MANAGER_PATH` matters more than it looks: micromamba solved a 51-package conda-forge +
        bioconda spec in seconds where the classic conda solver had taken minutes on 7. And the
        line that added it was written as `[ -n "$X" ] && export ...`, which under `set -e` ends
        the job when X is unset - before the live log is opened, so it looks exactly like a job
        that produced nothing → b27ed62.

**THE SECOND RUN** (PBS 677757, after scenic was given anndata and de learned to check its
design). `ran: ['abundance', 'cellchat', 'cellcycle', 'de', 'decoupler', 'liana', 'pseudotime',
'scenic', 'silhouette', 'velocity']` - all ten, one merged object. `de ok 531s  779
gene-population-term results below padj 0.05 across 10 population(s), formula ~ age + batch +
diet`: chemistry dropped as aliased with age, and NAMED. Two refusals left, both this host's:

        [host] **`ctx.reference_for_role()` COULD NEVER RETURN ANYTHING.** `Context` has accepted
              `reference_specs` from the start and NOTHING EVER PASSED THEM - `in.json` carried
              `{name: path}` and not the declarations behind them - so the search had an empty
              mapping and answered None for every role, of every plugin, always. That is the whole
              mechanism that keeps a SPECIES out of a plugin, failing closed: the mouse and human
              entries of one reference are different FILES with different NAMES, so asking by name
              would mean a plugin picking a species. scenic refused on all ten units with `the
              cisTarget references are not available` while its own `in.json` listed all three of
              them, verified, by absolute path → a5314fa
        [host] and the gene-column fix BROKE THE SHAPE IT WAS FIXING. `genes` became a list per
              FIELD of features.tsv, so `len(genes)` was 2, and the orientation check compared
              34,290 against 2 and refused every source as `matches neither 15,046 barcodes nor 2
              genes`. A fix that turned partial sourcing into none, found on the run that was
              meant to prove it → a5314fa

**THE THIRD RUN** (PBS 677891). velocity produces a real result on the real cohort for the first
time in this project's history: `partial - velocity fitted on 2,000 genes (stochastic); median
confidence 0.42; unspliced 23.9% of counts`, `wrote velocity.h5ad (98,627 x 2,000, velocity graph
included)`, `transitions: 11 directed label transition(s)`. `partial` is the DECLARED behaviour
below `min_confidence` 0.5, not a failure.

observation, not a defect: ten `per_unit` GRNBoost2 fits on ONE node get one core each, because
the budget is divided over a 37-instance wave. That is arithmetic, and `EXECUTION.md` §5 already
names the answer - the `pbs` executor submits one job per instance, and wave 1 of this cohort is
up to eighty independent jobs limited by the queue rather than by one node.

conversion: **did the two plugins lose behaviour?** No, and what they GAINED is the point.

        cellcycle's converted form produces the same shape - `status ok`, `obs [phase, S_score,
        G2M_score]`, two captioned figures with source data, the same headline format - and its
        selftest passes the same assertions with one added. What changed is that it now goes
        through `_entry.py`: `100,713 cells x 34,290 genes` -> `4,225 sentinel-labelled cells
        kept` -> `excluded 2,086 cells with NaN in X_scanvi` -> scored 98,627. **The directory
        shape read `in.json` itself and applied NONE of that**, which is what "the contract is the
        host's" means in numbers rather than in prose.

        velocity's selftest passes in one file with an added check that its plotting path imports
        and draws, and the search half - the part that was proven and was MOVED rather than
        rewritten - found its counts on the real project for the first time. Three behaviours
        changed deliberately and are recorded rather than assumed: its `--params` are now typed
        `config` validated before the run; its per-population table and its directed transitions
        exclude annotator sentinels instead of marking them `is_sentinel` and sorting them last;
        and `attach` assembles COO arrays rather than filling a `lil_matrix`, which is a rewrite
        of a half that had never executed.

format: the plugin FORMAT had to change twice, and both changes are the same lesson - **a shape
        that cannot express something deletes it silently rather than refusing it.** Neither
        change was needed by a plugin somebody else wrote; both were found by moving two plugins
        the project already had into the shape the project already preferred, which is the
        cheapest possible test of a format and had never been run.

clean:  7 suites and `validate` green on the workstation AND on the cluster, at every commit of
        this cycle. `plan --audit --report` over all ten plugins: `checked: all 10 known plugin(s)
        appear exactly once`, `0 error(s), 0 warning(s)`, `wrote .../run_plan.html`.

## 2026-08-23 — cycle 6 closed by PBS 679143: ten of ten, every one with a result

The run the whole cycle was for, at `bc4a356`, over 100,713 cells and ten samples:

    ran : ['abundance', 'cellchat', 'cellcycle', 'de', 'decoupler', 'liana',
           'pseudotime', 'scenic', 'silhouette', 'velocity']
    10 plugin(s) ran, 0 did not          <- out/README.md
    [4 at a time of 37]                  <- the allocator, admitting by CORES
    wrote .../out/objects/cohort_profiled.h5ad  (3.50 GB)

Every plugin, including the third-party one, produced a result:

    scenic[S1]   ok  3149s  111 regulon(s) over 10,837 cells, inferred from this unit  [x10]
    de               ok   609s  779 gene-population-term results below padj 0.05 across 10
                                population(s), formula ~ age + batch + diet
    velocity         partial 530s  velocity fitted on 2,000 genes (stochastic); median
                                confidence 0.42; unspliced 23.9% of counts
    cellchat[...]    ok         1,654 interactions over 9 populations, CellChatDB.mouse  [x10]
    liana[...]       ok        27,002 interactions over 9 populations  [x10]
    abundance        ok    61s  2 credible compositional effect(s) at fdr 0.05
    cellcycle        ok    89s  45.5% of cells score S or G2M
    decoupler        ok    69s  674 regulators scored per cell
    pseudotime       ok    70s  3 terminal state(s) over 96,488 cells
    silhouette       ok    26s  median silhouette 0.265 over 13 population(s)

`velocity`'s `partial` is its DECLARED behaviour below `min_confidence` 0.5, not a failure - the
field is reported as unresolved rather than presented as a direction.

And the one thing that did NOT reach the object was refused for a reason worth reading:

    NOT MERGED: unit 'S1' obsm['X_regulon_auc'] came back with different widths across
    units ([37, 42, 48, 57, 65, 73, 88, 111]), so the columns are not the same quantity and
    stacking them would invent one.

Ten GRN inferences over ten samples find different numbers of regulons; column 12 of one sample's
matrix is not column 12 of another's. The merge says so, keeps each unit's copy in its own
directory, and records the absence in the object's provenance rather than in a line of console
output nobody keeps.

clean:  7 suites green on the cluster, `validate` 0 errors over all ten plugins, 10 selftests
        passed, audit 0/0.

---

## 2026-08-24 — the allocator learns memory, and the tool stops moving underneath a run

Five defects, each of the same shape: a field that was declared, read, and then discarded.

**The core budget was divided proportionally across a whole wave**, as though every instance in it
ran at once. Only a resident subset does. On any wave larger than the budget the arithmetic
collapsed — 37 instances declaring 313 cores against a budget of 12 gave a plugin declaring 16
`int(16 × 12 / 313)` = 0, floored to 1. Ten GRN fits ran on one core each for 4h23m of a 12h
timeout, while the plan printed `(1c)` and nothing anywhere printed the 16.

**A declaration read and then discarded is worse than one never read**, because the plan prints
its consequence and never prints the declaration. That is the third time the same sentence has
been written in this log about a different field.

**The allocator was blind to memory entirely.** `memory_gb_per_100k` had existed since the
executor block and nothing ever read it. A job died at 260 GB against a 200 GB request while each
of its ten instances correctly held one core: the core budget was satisfied throughout and could
not have prevented it. `ResourcePool` now admits on cores, memory and GPUs.

**And the memory metric was wrong in the dangerous direction.** `peak / n × 100_000` reads as a
rate and is not one — memory is a baseline plus a per-cell term, and dividing by `n` charges the
fixed cost to the slope. On a fixture with a known 6 GB baseline and 12 GB per 100k it reported
94 GB per 100k off a 7,296-cell instance, eight times the truth.

Worse, the fix's own first version failed the wrong way: with one point it attributed the whole
peak to the *baseline* and the docstring called that conservative. It is conservative only at the
size measured. 7.2 GB at 98,627 cells would charge 7.2 GB for 500,000, where the truth is nearer
36 — a five-fold under-request, which is precisely the failure that kills a job at the end of its
longest step. It now attributes to the rate, which over-charges the smaller instances instead,
where the error is bounded by the baseline and nothing dies.

All nine plugins now declare measured values, fitted from their own instances. The estimate they
replaced for the most expensive plugin was wrong in **both** terms.

**A cohort fit was added without checking it was tractable.** A method that infers its own output
vocabulary produces per-unit results that are not comparable with each other — measured: two
samples shared 17% of their transcription factors — so a shared fit is needed to compare them.
Added, and then it thrashed: 8,929 garbage-collection warnings and eight lines of progress over
six hours on an 11 GB dense frame. It does not fail, it thrashes, which is worse — a job that is
3% productive looks exactly like one that is merely slow. It now infers from a balanced subsample
and still scores every cell, in chunks, because building one dense frame over all of them is the
same allocation that caused the thrash.

Then the same fit died after 3,867 seconds of *completed* work, writing a caveat, on
`ctx.constraint` — a name set on `Guard`, thirty lines above `Context` in the same file. Maximum
cost, minimum signal. Two static checks now make that class impossible: every `ctx.<attr>` a
plugin names must exist, and no module may read a name nothing defines. Both were verified to
bite by planting a fault — which mattered, because the first version of the second check filtered
on `not sym.is_global()`, which excludes exactly the case it was hunting, and reported clean on a
file with a planted undefined name.

**The tool could change underneath a running run.** Code is read at every subprocess launch, so a
pull at hour one of a three-hour run is picked up by everything after it: two versions used, one
reported. Silent and unattributable, because both versions are correct alone and only the mixture
is wrong. Handling it by checking `qstat` first is discipline, not a mechanism. Now: the host
fingerprints the tool and re-checks before every instance, and the job runs from a snapshot so
the race cannot arise.

**Overfitting found in two places the leak guard cannot see.** It looks for project names;
restricting a user to the shapes one project happens to have is quieter. `--assay` carried
`choices=[None, "cell", "nucleus"]`, so argparse refused the flag before the tool could reason
about it — the identical defect `--organism` was fixed for one flag away, with the reasoning
written directly above it. And a reference check warned on any organism outside a list of six. A
list of what this tool knows is not a list of what is valid.

clean:  7 suites green, 415 checks in the contract suite alone; all nine plugins declare memory
        and pass `declare.check` with no ERROR and no WARN; a run of all ten plugins at 38/38
        instances, 0 failures, 0 merge refusals, 0 tool-drift refusals.

### The same day, after the entry above

**The drift check was proven, and the diagnosis it produced pointed at the wrong thing.** A run
deliberately started with the snapshot disabled, so it read the live checkout; two files touched
while its wave was in progress. Six instances refused, each in 0s, naming exactly the two files
that moved, while the four launched before the touch completed normally. An unfired safety check
is indistinguishable from a broken one, and this one is no longer unfired.

It also classified every refusal `[method] … the plugin is the place to start`. The plugin was
untouched; a `git pull` was not. Now `host`, not repairable, saying outright not to debug the
plugin.

**And the closing run caught a regression in the fix above it.** The memory report listed three
plugins where the previous run listed ten. `if _b is None: continue` was written when a `None`
baseline meant "no usable measurement"; making the one-point case attribute to the rate gave it a
second meaning, and every plugin that produced a single instance was silently dropped from the
report — the ones with the least data and the most need of it.

That is the fourth defect of one shape in this round: **a sentinel value gained a meaning and not
every reader was re-checked.** The others were the core budget, the reference specs and the
constraint. It is worth naming, because the fix is never local — changing what a value means is a
change to every place that reads it, and the compiler will not say so.

clean:  PBS 683117 — all ten plugins, 38/38 instances, 0 failures, 0 merge refusals, 0 tool-drift
        refusals, Exit_status 0. The fitted memory figures reproduced the previous run's to within
        a rounding step, which is the measurement being repeated rather than carried forward.

## 2026-08-25 — the plugin declares what its own page should contain

Seven of nine shipped plugins emitted no figure and every gate passed. The reporter was the third
consumer of a plugin's own words — after the builder and the planner — and the only one still
discovering rather than reading: it rendered whatever arrived, in emission order, with nothing on
the page saying what a panel was for or that one was missing.

A `report` block in the declaration. Per panel: an `id` (the name `emit_figure` is called with),
`shows` (`diagnostic` / `result` / `comparison`), the `question` printed above it, the `source`
table it must be drawable from, and `required` or a `when_absent` reason. Plus `reads_with`, for a
plugin answering the same question from different evidence.

**The reporter knows that vocabulary and no figure.** It positions by `shows`, captions by
`question`, links by `source`. That is the `_who_produces` defect kept out of a third domain, and
it is asserted rather than intended: no host module may name a figure id — computed from what the
shipped plugins declare, so it tightens as plugins are added — and the layout's own text may name
no plugin. The leak check needed a word boundary before it was usable: `de` is a plugin's name and
a syllable in half of English, and the substring version failed on the word "declared".

Diagnostics are ordered before results. A result under a failed check is a number, not an answer.

### Two defects, and the second is why the first was invisible

`manifest._figure` builds a fresh mapping from a **fixed key list** written before this existed.
Nine panels emitted with their ids arrived at the host as nine `null`s — the join severed at
serialisation, neither end noticing, because the plugin had written one and the host was reading a
field that no longer came.

And the check that exists to catch exactly that reported clean, because `figure_drift` exempted
`partial` as well as `refused` — a guard copied from `declaration_drift`, where it belongs. A
refusal produced nothing by design. A **partial** run produced results, wrote a page and drew
figures, and `partial` is the ordinary status of a method that fitted on a subset or scored below
its own threshold. Velocity's was partial. Only a refusal is exempt now; a panel that genuinely
cannot be drawn is what `required: False` and `when_absent` are for, and the status is the wrong
place to say it.

Both halves passed their own tests and the pair did not, so the test is the round trip a real run
makes: emit → `write_output` → read back → drift-check.

**Found by reading the payload of a run that exited 0.** Nothing about the exit status said so, and
a check whose input has been silently emptied is worse than no check.

### And the verification made the same mistake the tool is built against

The first probe of the fixed check reported SILENT on the real payload. It was reading
`$RUNDIR/.tool` — a snapshot left by an earlier run — while the job had run from
`$RUNDIR/out2/.tool`. Two trees, one name apart, and the stale one answers every question
plausibly. That is the drift this tool snapshots to prevent, arriving in the check of the check.

clean:  PBS 689055 — velocity and cellcycle on a 100,713-cell object. velocity: 9 declared, 9
        drawn, 0 findings; its page carries five diagnostic panels under their questions, then
        four results. cellcycle declares no block and renders as it always did, which is the
        path a plugin written outside this repository takes. Proven live on the real payload,
        not on a fixture: remove a required panel -> 1 finding naming it; remove an optional one
        -> 0; add an undeclared one -> 1 naming it.
