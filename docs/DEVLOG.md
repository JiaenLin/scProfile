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
