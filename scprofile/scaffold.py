"""Generate a plugin's build skeleton from its declared manifest.

`plan` names the gap; this closes the mechanical half of it. The manifest already says what the
plugin needs, produces and cannot show — everything derivable from that is written here, so the
author starts at the part that needs judgement rather than at boilerplate.

WHAT IS DELIBERATELY LEFT BLANK, AND WHY

`run.py` gets the protocol, the key resolution, the sentinel handling and the output writing. The
method call is a `TODO` and the file REFUSES TO RUN until it is replaced. A scaffold that produced
a runnable no-op would produce empty results that look like real ones, which is the failure this
whole tool is arranged against.

`lock.yml` is a skeleton with no versions. A lock is captured from a resolve that WORKS; one
generated from declared bounds is the thing `UPSTREAM.md` warns about.

`UPSTREAM.md` is a template with its required sections and nothing in them. It cannot be generated
because it is the record of having READ the tool's documentation, and generating it would produce
a file asserting that reading happened.
"""
from __future__ import annotations

from pathlib import Path

RUN_PY = '''#!/usr/bin/env python3
"""{name} — {summary}

SCAFFOLD. The method call below is a TODO and this file refuses to run until it is replaced.

Before writing it, read UPSTREAM.md — specifically the section on defaults that are wrong for this
contract. The defaults that matter are the ones that do NOT error.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scprofile import manifest                                            # noqa: E402

VERSION = "0.0.1"


def main(argv):
    import numpy as np                                                    # noqa: F401
    import pandas as pd
    import scanpy as sc

    inp = manifest.read_input(argv[1] if len(argv) > 1 else os.environ["SCPROFILE_IN"])
    out = Path(inp["out_dir"])
    for d in ("tables", "figures", "obs"):
        (out / d).mkdir(parents=True, exist_ok=True)

    keys = inp["keys"]
    sentinels = set(inp.get("sentinels") or ())
    # THE CORE SHARE, not the machine's. See docs/EXECUTION.md.
    cores = int((inp.get("resources") or {{}}).get("cores", 1))
    unit = inp.get("unit")                     # set when this plugin runs per design unit
    organism = (inp.get("organism") or "").lower()

    A = sc.read_h5ad(inp["h5ad"])
    print(f"{{A.n_obs:,}} cells x {{A.n_vars:,}} genes"
          + (f", unit {{unit}}" if unit else "") + f", {{cores}} core(s)")

    label = keys.get("label")
    if label and label in A.obs:
        lab = A.obs[label].astype(str)
        n_sent = int(lab.isin(sentinels).sum())
        # A sentinel is the annotator declining to call a cell type. Never a population, never a
        # denominator, and NEVER DROPPED - they are cells.
        if n_sent:
            print(f"{{n_sent:,}} cells carry an annotator sentinel; they are kept and are not "
                  f"treated as a population")

    # Cells withheld upstream carry NaN in a computed embedding. Handle them explicitly or refuse:
    # a NaN row in a neighbour graph either raises or silently yields a graph they are absent from.
    emb = keys.get("embedding")
    if emb and emb in A.obsm:
        bad = int(np.isnan(np.asarray(A.obsm[emb])[:, 0]).sum())
        if bad:
            print(f"{{bad:,}} cells have NaN in {{emb}} - withheld upstream. Excluding them here.")

    raise SystemExit(
        "{name}: this is a SCAFFOLD. Implement the method call, then delete this line.\\n"
        "  1. read UPSTREAM.md and set every default the contract needs changed\\n"
        "  2. resolve keys through inp['keys'], never a hard-coded column name\\n"
        "  3. use `cores`, never os.cpu_count()\\n"
        "  4. write declared outputs, then out.json")

    manifest.write_output(                                                # noqa: W0101
        out, kernel="{name}", version=VERSION, status="ok",
        headline="",
        tables=[], figures=[], caveats=[])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
'''

SELFTEST = '''#!/usr/bin/env python3
"""Prove this environment can run {name}, before a real run is spent on it.

An import proves the package is on the path. Every failure worth catching is downstream of the
import: an API that moved, a numpy that removed an alias, a pandas that dropped a method. So this
runs the WHOLE path on a synthetic fixture and asserts shapes and finiteness — never a biological
answer, because the fixture is synthetic and a selftest asserting a result is testing the fixture.
"""
from __future__ import annotations

import sys


def main():
    print("{name} selftest")
    # TODO: import the wrapped tool, print its version, and run the real computation on a small
    # synthetic fixture. Assert shapes and finiteness. See kernels/velocity/selftest.py.
    print("  NOT IMPLEMENTED - a selftest that passes without running anything is worse than none")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
'''

LOCK = '''# {name}'s environment. Built with:  scprofile install {name} --prefix <dir>
#
# EVERY DEPENDENCY MUST BE PINNED WITH `==`. A lock with ranges is not a lock.
#
# Capture these from a resolve that WORKS - `setup/resolve_probe.pbs` reports what a package
# resolves to against a real interpreter, and whether it needs its own environment at all.
# Do NOT compose this from the bounds the package declares: a lower bound is honest about what a
# tool was written against and silent about what it still works with.

name: scprofile-{name}
channels:
  - conda-forge
dependencies:
  - python=3.11
  - pip
  - pip:
      # - {tool}==X.Y.Z          <- TODO, from a working resolve
'''

REFERENCES = '''# Reference data for {name}. Fetched with:  scprofile fetch {name} --to <dir>
#
# READ THE URLS OFF THE UPSTREAM RESOURCE LISTING. Do not write them from memory: a wrong URL that
# 404s is harmless, and a right-looking URL to a different build of a database is not - it returns
# a smaller result that looks like a real one.
#
# Each entry needs a sha256. A file that cannot be verified is a file that cannot be trusted to be
# the one the result was produced against, and `status()` reports the absence explicitly.
#
# Entries may be organism-keyed; `references(organism)` filters on it.

# <name>:
#   url: https://...
#   sha256: ...
#   size: 1.2GB
#   organism: mouse
'''

UPSTREAM = '''# Upstream: {tool}

**What the tool's own documentation says, recorded so the wrapping can be checked against it
rather than against memory.** This file cannot be generated — it is the record of having read the
documentation, and a generated one would assert that reading happened.

- Docs: TODO
- Paper / citation: TODO
- Licence: TODO
- Version wrapped: TODO

---

## The signature, as documented

TODO — every parameter and its default, and where results are written.

## The defaults that are wrong for this contract, and why

**This is the section that earns the file.** A default that errors is harmless. A default that
silently returns a plausible wrong answer is what this is for.

Check at least:

- **organism** — does a default resource or gene set assume human? Run against another species it
  may not error; it may match almost nothing and return a small believable table.
- **which values it reads** — does it prefer `.raw`, or a layer, or `X`? An object whose `.raw`
  holds something else gets scored on different values with nothing saying so.
- **parallelism** — is it serial by default on work that is parallel? That is under-use.
- **anything bounding a statistic** — a permutation count sets the p-value floor at 1/n.

## What it drops at its defaults

TODO — a group below a minimum size, a feature below a threshold. Each becomes a NAMED ABSENCE:
an identity missing because it had four cells looks identical to one with no result.

## What it can do that this plugin does not use

TODO — so under-use is deliberate and visible. Wrapping a framework as though it were one function
is the commonest way to waste one.

## What its own literature says it cannot establish

TODO — carried into `cannot_show`.
'''


#: THE DRAW WRAPPER, GENERATED. A plugin that draws OUT OF PROCESS - through R, or any
#: interpreter the host cannot reach into - must refuse past its own declared ceilings,
#: because the host cannot intervene in another program's graphics device. That refusal is
#: MECHANISM, identical in every such plugin, and while it was written by hand one plugin
#: carried three copies of it, one per embedded script, checked by nothing.
#:
#: `sch dev convert placement` requires it; this is what satisfies that requirement, so a
#: scaffolded plugin passes the check on the day it is created.
#:
#: NOT PASSED THROUGH `str.format`. R is mostly braces and doubling every one of them to
#: survive a format call is a transcription error waiting to happen.
R_DRAW = r'''# __NAME__ - the host-to-plugin drawing protocol, in R.
#
# GENERATED by `scprofile scaffold __NAME__`. Do not edit it here; edit the template in
# scprofile/scaffold.py and regenerate, or the next scaffold silently reverts you. `sch dev
# convert placement` regenerates this file and refuses a plugin whose copy has drifted.
#
# HOW A PLUGIN USES IT. Prepend it to every embedded R script the plugin runs, so ONE definition
# serves all of them:
#
#     script = _R_DRAW + _R_BODY            # in the Python that launches Rscript
#
# and configure it once per script, after `figdir` is known:
#
#     .figures(prefix = "native_", what = "native plot", w = 1800, h = 1500,
#              context = ctx_file, visible = function(id) draw_figs || id %in% profile_plots)
#
# WHY THIS IS ONE FILE AND NOT A BLOCK IN EACH SCRIPT. It was three blocks in one plugin, and the
# copies drifted. One of them recorded the cost in its own comment: a script "was written with only
# `npng` and then called `ndev` for the interaction heatmaps - could not find function ndev halted
# the whole framing loop after the first framing's scatter plots, so one framing of two was drawn
# and neither heatmap was. The sibling script had both wrappers; this one had one." A generated
# definition cannot have that defect. Three hand-written ones cannot avoid it.
#
# WHAT IS DELIBERATELY NOT HERE: anything about the method. This file knows about ceilings,
# captions, colours, devices and a phase clock - the things the HOST and the plugin agree on. It
# names no plotting function and no biology.

.figcfg <- new.env(parent = emptyenv())
.figcfg$prefix <- ""
.figcfg$what <- "figure"
.figcfg$w <- 1800
.figcfg$h <- 1400
.figcfg$res <- 200
.figcfg$visible <- function(id) TRUE

# WHAT THE HOST COMPUTED AND THE PLUGIN APPLIES. The host writes one tab-separated file beside the
# run and every row of it is a term of this contract: the provenance stamp, the sentence that says
# what an absent population means, the colour map that keeps one population one colour across every
# panel of the whole report, and the ceilings.
.fctx <- list(stamp = "", absence = "", colours = character(0))
.ceil <- integer(0)

.plots <- new.env(); .plots$ok <- 0L; .plots$bad <- character(0)
.caps <- new.env(); .caps$rows <- list()
.ndrawn <- new.env(parent = emptyenv())

.figures <- function(prefix = "", what = "figure", w = 1800, h = 1400, res = 200,
                     context = "", visible = NULL) {
  .figcfg$prefix <- prefix
  .figcfg$what <- what
  .figcfg$w <- w
  .figcfg$h <- h
  .figcfg$res <- res
  if (!is.null(visible)) .figcfg$visible <- visible
  if (nzchar(context) && file.exists(context)) {
    fc <- tryCatch(utils::read.delim(context, header = FALSE, sep = "\t", quote = "",
                                     comment.char = "", stringsAsFactors = FALSE,
                                     col.names = c("k", "v")), error = function(e) NULL)
    if (!is.null(fc) && nrow(fc)) {
      .fctx$stamp <<- paste(fc$v[fc$k == "stamp"], collapse = "")
      .fctx$absence <<- paste(fc$v[fc$k == "absence"], collapse = "")
      cr <- fc[startsWith(fc$k, "colour:"), , drop = FALSE]
      if (nrow(cr)) .fctx$colours <<- stats::setNames(cr$v, sub("^colour:", "", cr$k))
      cl <- fc[startsWith(fc$k, "ceiling:"), , drop = FALSE]
      if (nrow(cl)) .ceil <<- stats::setNames(suppressWarnings(as.integer(cl$v)),
                                              sub("^ceiling:", "", cl$k))
    }
  }
  invisible(NULL)
}

# THE VECTOR A PLOTTING FUNCTION WANTS: IN THE OBJECT'S LEVEL ORDER, AND NAMED.
#
# Ordered, because a plotting function takes a colour vector POSITIONALLY against the object's
# factor levels and any other order colours the wrong populations. NAMED, because some upstream
# functions refuse an unnamed one outright while others accept it either way - so the vector
# satisfies the stricter of them. Dropping the names once cost 36 circle plots across 18 units in
# one run, and the per-unit tallies reported the failure while the run-level count said nothing.
#
# Returns NULL when the host gave no map or when any level is unmapped, because a partial vector is
# worse than none: the plotting function would recycle it silently.
.cols_for <- function(levs) {
  if (!length(.fctx$colours)) return(NULL)
  levs <- as.character(levs)
  if (!all(levs %in% names(.fctx$colours))) return(NULL)
  out <- .fctx$colours[levs]
  names(out) <- levs
  out
}

# A PHASE CLOCK, DEFINED AT THE TOP BECAUSE R DOES NOT HOIST. Twice the cost of a round has been
# diagnosed by assumption and been wrong: the inference was assumed dominant and was not, then the
# matrix write was, and it takes one to five seconds. Guessing where a run spends its time is what
# makes every round of development expensive, so the run measures itself.
#
# t0 IS ZERO, NOT "NOW". `proc.time()` elapsed is measured from the moment R STARTED, so anchoring
# the clock at zero makes the first mark cover everything before it - interpreter start-up and
# loading the wrapped tool and its dependencies. Anchored at "now" the first phase reported 0 while
# the cost it was supposed to name sat outside the clock entirely, and a line that says zero is
# worse than no line because it reads as a measurement.
.clock <- new.env(); .clock$t0 <- 0; .clock$marks <- list()
mark <- function(what) {
  now <- proc.time()[["elapsed"]]
  .clock$marks[[what]] <- now - .clock$t0
  .clock$t0 <- now
  invisible(NULL)
}

.legend <- function(fname, text, by) {
  if (!nzchar(text)) return(invisible(NULL))
  .caps$rows[[length(.caps$rows) + 1L]] <-
    # ONE LINE, ALWAYS. The file is tab-separated and written with quote = FALSE, so a caption
    # carrying a tab or a newline does not corrupt one row - it shifts every column after it, or
    # splits the row in two, and the reader then drops what it cannot parse WITHOUT SAYING SO.
    # Collapsing whitespace here matches what the reader does anyway and makes the written file
    # unable to express the broken shape.
    list(file = fname, caption = gsub("[[:space:]]+", " ", trimws(text)), drawn_by = by)
  invisible(NULL)
}

.write_captions <- function() {
  # CALLED ON EXIT AS WELL AS AT THE END. An abort in a later section left `captions.tsv`
  # unwritten, so panels drawn BEFORE the failure silently lost their legends and fell back to
  # their filenames - a degradation that renders as a normal page.
  if (!length(.caps$rows)) return(invisible(NULL))
  # ONCE PER SET OF ROWS. This is called explicitly at the end of a script AND by the finalizer
  # below, and writing the same file twice put a duplicate line in every run's log.
  if (identical(.caps$written, length(.caps$rows))) return(invisible(NULL))
  .caps$written <- length(.caps$rows)
  d <- do.call(rbind, lapply(.caps$rows, function(r) as.data.frame(r, stringsAsFactors = FALSE)))
  utils::write.table(d, file.path(figdir, "captions.tsv"),
                     sep = "\t", row.names = FALSE, quote = FALSE)
  cat("wrote", nrow(d), "figure legend(s)\n")
}

# WHEN THE SCRIPT ENDS, HOWEVER IT ENDS - AND `on.exit` IS NOT THAT. An abort in a later section
# left `captions.tsv` unwritten, so panels drawn BEFORE the failure silently lost their legends
# and fell back to their filenames, which renders as a perfectly normal page. The guard written
# against it was `on.exit(.write_captions(), add = TRUE)` at the top level of the script, and a
# top-level `on.exit` in `Rscript` NEVER RUNS - not on error and not on a clean exit. Measured
# both ways. A finalizer registered with `onexit = TRUE` runs in both cases, so the protection
# the comment described exists for the first time.
invisible(reg.finalizer(.caps, function(e) .write_captions(), onexit = TRUE))

# THE CEILING, ENFORCED BEFORE THE PLOT IS COMPUTED. R is lazy - `expr` is a promise until it is
# forced - so refusing here costs the call and nothing else. Longest prefix wins, as everywhere
# else a plugin states a rule and an exception together, and a family no ceiling covers is
# unbounded exactly as it was before this existed.
#
# WHY IT IS HERE AND NOT IN THE LOOPS. The bounds a plugin honoured were `head(paths, 6)` and
# `head(.ranked, 8)`, typed in by hand beside a declaration that said 12 and 8. The plan read the
# declaration, the run obeyed the literals, and they agreed only while somebody kept them in step.
# The number now exists once, in the declaration, and arrives here.
#
# A CEILING THE DRAWING CODE DOES NOT READ IS A COMMENT. Remove this guard and the plugin still
# declares its ceilings, still reports them, and draws without bound. That state was reached once
# and every build check reported the plugin finished; `sch dev convert placement` now asks.
.at_ceiling <- function(id) {
  if (!length(.ceil)) return(FALSE)
  k <- names(.ceil)[startsWith(id, names(.ceil))]
  if (!length(k)) return(FALSE)
  k <- k[which.max(nchar(k))]
  cap <- .ceil[[k]]
  if (is.na(cap)) return(FALSE)
  n <- if (is.null(.ndrawn[[k]])) 0L else .ndrawn[[k]]
  if (n >= cap) {
    cat("ceiling: ", id, " not drawn - ", k, " declares at most ", cap, " here\n", sep = "")
    return(TRUE)
  }
  .ndrawn[[k]] <- n + 1L
  FALSE
}

# THE ONE DEVICE PATH. `force_it` is the only thing the two public wrappers disagree about, and it
# is the difference between a function that RETURNS a plot object and one that DRAWS as a side
# effect - see `ndev` below.
#
# THE LEGEND SLOT IS THE PARAMETER WHOSE DEFAULT IS THE EMPTY STRING. That is how the maker finds
# it without being told a name, in R or in Python, so keep the default as it is.
.draw_one <- function(id, expr, force_it, w = .figcfg$w, h = .figcfg$h,
                      res = .figcfg$res, legend = "", by = "tool") {
  if (!isTRUE(.figcfg$visible(id))) return(invisible(NULL))
  full <- paste0(.figcfg$prefix, id)
  if (.at_ceiling(full)) return(invisible(NULL))
  path <- file.path(figdir, paste0(full, ".png"))
  .legend(basename(path), legend, by)
  ok <- tryCatch({
    grDevices::png(path, width = w, height = h, res = res)
    dn <- grDevices::dev.cur()
    # THE SAFETY NET NAMES ITS OWN DEVICE. An unqualified `dev.off()` here closes whatever is
    # current, which after the explicit close below is somebody else's device.
    on.exit(if (dn %in% grDevices::dev.list()) grDevices::dev.off(dn), add = TRUE)
    if (force_it) force(expr) else print(expr)
    # CLOSED BEFORE THE FILE IS ASKED ABOUT, and this is not tidiness. `on.exit` fires when the
    # FUNCTION returns, so with the close left to it the `file.exists` below runs while the
    # device is still open - and whether the file is there by then is a property of the platform:
    # the Linux png device creates it on open, the macOS one on close. Measured, on a wrapper
    # written exactly that way: every panel drawn correctly was counted as FAILED on macOS and as
    # written on the cluster, from one line of R.
    grDevices::dev.off(dn)
    TRUE
  }, error = function(e) {
    cat(.figcfg$what, id, "FAILED:", conditionMessage(e), "\n")
    FALSE
  })
  # THE FILE, NOT ONLY THE ABSENCE OF AN ERROR. A plotting call that returns quietly without
  # putting anything on the device leaves a path that does not exist, and counting that as drawn
  # is how a declared plot came to be promised and never produced.
  if (ok && file.exists(path)) {
    .plots$ok <- .plots$ok + 1L
    cat(.figcfg$what, id, "written\n")
  } else {
    .plots$bad <- c(.plots$bad, id)
    if (file.exists(path)) unlink(path)
  }
  invisible(NULL)
}

npng <- function(id, expr, w = .figcfg$w, h = .figcfg$h, res = .figcfg$res,
                 legend = "", by = "tool") {
  .draw_one(id, expr, FALSE, w, h, res, legend, by)
}

# Some functions DRAW rather than return - a base-graphics network, a grid object that must be
# drawn, a function whose value is NULL. `print` on those prints nothing or errors, so this second
# wrapper evaluates for the side effect instead.
ndev <- function(id, expr, w = .figcfg$w, h = .figcfg$h, res = .figcfg$res,
                 legend = "", by = "tool") {
  .draw_one(id, expr, TRUE, w, h, res, legend, by)
}
'''

def draws_through_r(spec):
    """Does this plugin draw in R? Read from its declared requirements, not from its source."""
    req = spec.get("requires") or {}
    return bool(req.get("r") or [c for c in (req.get("conda") or {}) if str(c).startswith("r-")])


def companion(path, what):
    """Where a generated companion of a ONE-FILE plugin lives: beside it, carrying its name.

    NAMED FOR ITS PLUGIN OR IT IS SOMEBODY ELSE'S. Nine one-file kernels share one `kernels/`
    directory, so a bare `draw.R` in it would be read as every one of their own - and eight of
    them would pass a check on a file they never load. `kernels/cellchat.draw.R` cannot be
    mistaken for `kernels/liana.py`'s.
    """
    return Path(path).with_suffix("").with_name(Path(path).stem + "." + what)


def _one_file(kernel, *, force=False, log=print, out_dir=None):
    """Scaffold a ONE-FILE plugin: its generated companions, and nothing that belongs to a layout
    this repository no longer has.

    THIS PATH DID NOT EXIST AND THE COMMAND CRASHED FOR EVERY KERNEL IN THE REPOSITORY. `scaffold`
    was written for the six-file directory layout - `run.py`, `selftest.py`, `lock.yml` - which
    `scprofile/plugin.py` replaced, and it took `kernel.path` for a directory. A one-file kernel's
    path is the FILE, so it wrote to `kernels/<name>.py/run.py` and raised NotADirectoryError on
    the first template. Nothing caught it because nothing had run it since the format changed:
    the generated draw wrapper added to this module had therefore never been generated once, on
    any plugin, while being reported as the reason the wrapper was no longer hand-written.
    """
    made, skipped = [], []
    if draws_through_r(kernel.spec):
        p = companion(kernel.path, "draw.R")
        if out_dir:
            p = Path(out_dir) / p.name
            p.parent.mkdir(parents=True, exist_ok=True)
        if p.exists() and not force:
            skipped.append(p.name)
        else:
            p.write_text(R_DRAW.replace("__NAME__", kernel.name), encoding="utf-8")
            made.append(p.name)
    log(f"  {kernel.name}: wrote {', '.join(made) or 'nothing'}"
        + (f"   (kept existing {', '.join(skipped)}; --force overwrites)" if skipped else ""))
    if not made and not skipped:
        log("  a one-file plugin declaring no R has no generated companion: its selftest and its")
        log("  guard are functions inside it, and its environment comes from `requires`.")
        return made
    log("  next:")
    log(f"    prepend it to every embedded R script this plugin runs, so ONE definition serves")
    log(f"    all of them, and configure it once per script after `figdir` is known:")
    log(f"        .figures(prefix = \"native_\", what = \"native plot\", context = <ctx file>)")
    log(f"    `sch dev convert placement` regenerates it and refuses a copy that has drifted.")
    return made


def scaffold(kernel, *, force=False, log=print, out_dir=None):
    """Write the build skeleton for a declared plugin. Returns the files created."""
    d = Path(kernel.path)
    # ONE FILE OR A DIRECTORY, AND THE ANSWER IS ON DISK. Both shapes are a `kernel` to the rest
    # of this tool and only this function writes files, so this is the one place that has to know.
    if not d.is_dir():
        return _one_file(kernel, force=force, log=log, out_dir=out_dir)
    spec = kernel.spec
    tool = spec.get("plans_to_wrap") or (spec.get("wraps") or {}).get("tool") or "TODO"
    ctx = {"name": kernel.name, "summary": spec.get("summary", ""), "tool": tool}

    files = {"run.py": RUN_PY, "selftest.py": SELFTEST}
    if spec.get("needs_env", True):
        files["lock.yml"] = LOCK
    if tool != "TODO":
        files["UPSTREAM.md"] = UPSTREAM
    if spec.get("needs_references") or kernel.references():
        files["references.yml"] = REFERENCES
    # A PLUGIN THAT DRAWS THROUGH R GETS THE WRAPPER THAT HONOURS ITS CEILINGS. The host enforces
    # `at_most` for the figures IT writes; it cannot reach into another interpreter's device, so
    # the plugin's own wrapper has to - and that wrapper is the same in every such plugin.
    _req = spec.get("requires") or {}
    if (_req.get("r") or [c for c in (_req.get("conda") or {}) if str(c).startswith("r-")]):
        files["draw.R"] = R_DRAW

    made, skipped = [], []
    if out_dir:
        d = Path(out_dir)
        d.mkdir(parents=True, exist_ok=True)
    for fn, tpl in files.items():
        p = d / fn
        if p.exists() and not force:
            skipped.append(fn)
            continue
        p.write_text(tpl.replace("__NAME__", kernel.name) if fn == "draw.R"
                     else tpl.format(**ctx), encoding="utf-8")
        if fn.endswith(".py"):
            p.chmod(0o755)
        made.append(fn)

    log(f"  {kernel.name}: wrote {', '.join(made) or 'nothing'}"
        + (f"   (kept existing {', '.join(skipped)})" if skipped else ""))
    log("  next, in this order:")
    log(f"    1. UPSTREAM.md   read the tool's documentation and write down its wrong defaults")
    log(f"    2. lock.yml      from a resolve that works, every line pinned with ==")
    log(f"    3. selftest.py   run the real computation on a fixture, not an import")
    log(f"    4. run.py        the method call. It refuses to run until you replace the TODO")
    if "draw.R" in made:
        log("    5. draw.R        prepend it to every embedded R script, so one definition serves")
        log("                     all of them. It already refuses past the ceilings this plugin")
        log("                     declares; `sch dev convert placement` checks that it still does.")
    return made
