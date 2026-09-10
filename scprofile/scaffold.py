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
R_DRAW = '# __NAME__ - the draw wrapper. GENERATED by `scprofile scaffold`; prepend it to every embedded R\n# script this plugin runs, so ONE definition serves all of them:\n#\n#     script = _R_DRAW + _R_BODY        # in the Python that launches Rscript\n#\n# WHAT IT IS FOR. `at_most` in this plugin\'s declaration says how many files a family may write\n# per occurrence of its axis. The host resolves those ceilings and writes them into the figure\n# context as `ceiling:<family>` rows; this reads them and refuses past them BEFORE the panel is\n# computed. R is lazy - `expr` is a promise until it is forced - so a refusal costs the call and\n# nothing else.\n#\n# A CEILING THE DRAWING CODE DOES NOT READ IS A COMMENT. Remove the guard below and the plugin\n# still declares its ceilings, still reports them, and draws without bound. That state was reached\n# once and every build check reported the plugin finished; `sch dev convert placement` now asks.\n\n.ceil <- integer(0)\n.read_ceilings <- function(path) {\n  if (!nzchar(path) || !file.exists(path)) return(integer(0))\n  fc <- tryCatch(utils::read.delim(path, header = FALSE, sep = "\\t", quote = "",\n                                   comment.char = "", stringsAsFactors = FALSE,\n                                   col.names = c("k", "v")), error = function(e) NULL)\n  if (is.null(fc) || !nrow(fc)) return(integer(0))\n  cl <- fc[startsWith(fc$k, "ceiling:"), , drop = FALSE]\n  if (!nrow(cl)) return(integer(0))\n  stats::setNames(suppressWarnings(as.integer(cl$v)), sub("^ceiling:", "", cl$k))\n}\n\n.ndrawn <- new.env(parent = emptyenv())\n.at_ceiling <- function(id) {\n  if (!length(.ceil)) return(FALSE)\n  k <- names(.ceil)[startsWith(id, names(.ceil))]\n  if (!length(k)) return(FALSE)\n  k <- k[which.max(nchar(k))]        # longest prefix wins: a rule and its exception together\n  cap <- .ceil[[k]]\n  if (is.na(cap)) return(FALSE)\n  n <- if (is.null(.ndrawn[[k]])) 0L else .ndrawn[[k]]\n  if (n >= cap) {\n    cat("ceiling: ", id, " not drawn - ", k, " declares at most ", cap, " here\\n", sep = "")\n    return(TRUE)\n  }\n  .ndrawn[[k]] <- n + 1L\n  FALSE\n}\n\n# THE LEGEND SLOT IS THE PARAMETER WHOSE DEFAULT IS THE EMPTY STRING. That is how the maker finds\n# it without being told a name, in R or in Python, so keep the default as it is.\nnpng <- function(id, expr, w = 1800, h = 1400, res = 200, legend = "") {\n  if (.at_ceiling(id)) return(invisible(NULL))\n  grDevices::png(file.path(figdir, paste0(id, ".png")), width = w, height = h, res = res)\n  on.exit(grDevices::dev.off(), add = TRUE)\n  print(expr)\n}\n\n# Some functions DRAW rather than return - a base-graphics plot, a grid object that must be drawn.\n# `print` on those prints nothing or errors, so this second wrapper evaluates for the side effect.\nndev <- function(id, expr, w = 1800, h = 1400, res = 200, legend = "") {\n  if (.at_ceiling(id)) return(invisible(NULL))\n  grDevices::png(file.path(figdir, paste0(id, ".png")), width = w, height = h, res = res)\n  on.exit(grDevices::dev.off(), add = TRUE)\n  expr\n}\n'


def scaffold(kernel, *, force=False, log=print):
    """Write the build skeleton for a declared plugin. Returns the files created."""
    d = Path(kernel.path)
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
