"""Every name a plan entry's `expr` (or `when`, `file`, `args`) uses is bound somewhere in the
scripts that run it, or is an export of the wrapped tool or of R itself (harness ADR-0026, K-n).

FOUND BY THE RUN, NOT BY THE MAKER: an entry added to the plan named `pop`, a variable no script
defines; the validator, the build status and the companion's own syntax check all passed, and
six files failed on the cluster. R itself can say it before any job: the generated companion's
`quote(...)` expressions are parsed, `codetools::findGlobals` names their free variables, and
each is looked up against what the plugin's own R strings and the companion bind - assignments,
loop variables, function parameters - plus R's base packages and the recorded signatures of the
wrapped tool. Skipped, and said so, where no Rscript exists.

Run: python tests/test_an_expr_names_only_what_the_script_binds.py
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import subject                                                                  # noqa: E402

FAIL = []


def ck(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'} {name}" + (f" — {detail}" if not cond else ""))
    if not cond:
        FAIL.append(name)


FREE_R = r'''
args <- commandArgs(TRUE)
sigs_file <- args[1]; files <- args[-1]
sigs <- if (nzchar(sigs_file) && file.exists(sigs_file)) names(jsonlite::fromJSON(sigs_file)$functions) else character(0)
bound <- character(0); exprs <- list()
walk <- function(e) {
  if (is.call(e)) {
    fn <- if (is.name(e[[1]])) as.character(e[[1]]) else ""
    if (fn %in% c("<-", "=", "<<-") && length(e) >= 3 && is.name(e[[2]])) bound <<- c(bound, as.character(e[[2]]))
    if (fn == "for" && is.name(e[[2]])) bound <<- c(bound, as.character(e[[2]]))
    if (fn == "function" && !is.null(e[[2]])) bound <<- c(bound, names(e[[2]]))
    if (fn == "quote" && length(e) >= 2) exprs[[length(exprs) + 1]] <<- e[[2]]
    for (k in seq_along(e)) { a <- e[[k]]; if (!missing(a) && !is.null(a)) walk(a) }
  }
}
for (f in files) {
  p <- tryCatch(parse(f, keep.source = FALSE), error = function(e) NULL)
  if (is.null(p)) { cat("cannot parse ", f, "\n", sep = ""); next }
  for (e in p) walk(e)
}
pkgs <- c("base", "stats", "utils", "grDevices", "graphics", "methods")
known <- unique(c(bound, unlist(lapply(pkgs, function(p) ls(paste0("package:", p)))), sigs))
# NAMES UNDER NON-STANDARD EVALUATION ARE COLUMNS, NOT VARIABLES: `aes(x = resp1)` names a
# column of the data frame the plot is given, and R's own parser cannot tell. Everything under
# these calls is left alone.
nse <- c("aes", "aes_string", "vars", "with", "within", "subset", "transform")
under_nse <- function(e) {
  out <- character(0)
  if (is.call(e)) {
    fn <- if (is.name(e[[1]])) as.character(e[[1]]) else if (is.call(e[[1]]) && length(e[[1]]) == 3) as.character(e[[1]][[3]]) else ""
    if (fn %in% nse) out <- c(out, all.names(e))
    for (k in seq_along(e)) { a <- e[[k]]; if (!missing(a) && !is.null(a)) out <- c(out, under_nse(a)) }
  }
  out
}
bad <- 0
for (ex in exprs) {
  f <- eval(call("function", NULL, ex))
  g <- codetools::findGlobals(f, merge = FALSE)
  vars <- setdiff(g$variables, c(known, under_nse(ex)))
  if (length(vars)) { bad <- bad + 1; cat("UNBOUND ", paste(vars, collapse = ", "), " in: ", deparse(ex)[1], "\n", sep = "") }
}
cat("exprs ", length(exprs), " unbound ", bad, "\n", sep = "")
'''


def unbound(plugin, companion_text, r_strings, sigs=None):
    """[(names, expr)] - the free variables of every quote() in the companion that no script binds."""
    rs = shutil.which("Rscript")
    if not rs:
        return None
    with tempfile.TemporaryDirectory() as td:
        files = []
        (Path(td) / "companion.R").write_text(companion_text, encoding="utf-8")
        files.append(str(Path(td) / "companion.R"))
        for i, src in enumerate(r_strings):
            (Path(td) / f"s{i}.R").write_text(src, encoding="utf-8")
            files.append(str(Path(td) / f"s{i}.R"))
        (Path(td) / "free.R").write_text(FREE_R, encoding="utf-8")
        p = subprocess.run([rs, str(Path(td) / "free.R"), str(sigs or ""), *files],
                           capture_output=True, text=True, timeout=300)
        out = (p.stdout or "") + (p.stderr or "")
        return [(ln[len("UNBOUND "):].split(" in: ")[0], ln.split(" in: ")[1])
                for ln in out.splitlines() if ln.startswith("UNBOUND ")], out


rs = shutil.which("Rscript")
if not rs:
    print("  skip  no Rscript on this machine; an expr's free names were not checked")
    sys.exit(0)

print("the check itself, on a script that binds one name and an expr that uses two")
res, out = unbound("demo", 'x <- 1\n.plan <- list(a = list(expr = quote(f(x, idents.use = pop))))\n', [])
ck("the unbound name is named, the bound one is not",
   res and res[0][0] == "pop", str(res) + out[-300:])
res, out = unbound("demo", 'for (pop in 1:2) {}\n.plan <- list(a = list(expr = quote(f(pop))))\n', [])
ck("a loop variable binds", res == [], str(res))
res, out = unbound("demo", 'g <- function(pop) 1\n.plan <- list(a = list(expr = quote(f(pop))))\n', [])
ck("a function's parameter binds", res == [], str(res))

print("\nevery shipped plugin's companion names only what its scripts bind")
from scprofile import kernels as K                                              # noqa: E402
scripts = {}
for name, attr, src in subject.r_scripts():
    scripts.setdefault(name, []).append(src)
checked = 0
for name, k in sorted(K.discover().items()):
    comp = Path(k.path).with_name(f"{name}.draw.R")
    if not comp.is_file():
        continue
    sigs = Path(k.path).with_name(f"{name}.signatures.json")
    res, out = unbound(name, comp.read_text(encoding="utf-8"), scripts.get(name, []),
                       sigs=str(sigs) if sigs.is_file() else None)
    checked += 1
    ck(f"{name}: every expr's free variable is bound ({out.strip().splitlines()[-1] if out.strip() else ''})",
       res == [], "; ".join(f"{n} in {e[:60]}" for n, e in res)[:400])
ck("at least one companion was checked", checked >= 1)

if FAIL:
    print(f"\n{len(FAIL)} FAILED: " + ", ".join(FAIL))
    sys.exit(1)
print("\nan expr names only what the script binds")
