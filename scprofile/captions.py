"""A figure's legend, written by whatever drew it, rather than derived from its filename.

WHY THIS EXISTS. The host names a panel by inverting the plugin's declaration - which file came
from which function - and that is enough to say where a figure came from. It is not remotely
enough to say what the figure SHOWS. With no better source the caption became the filename with
its underscores removed:

    "interaction flow  age response by diet, drawn by the tool itself."

That is a filename. It does not say what the axes are, what the dashed line means, what the colour
encodes, that the panel is a difference of two differences, or that no test applies to it. And the
caption is what travels into the written section, so everything a title says is lost the moment a
reader meets the panel anywhere else.

WORSE, THE FALLBACK ASSERTS A PROVENANCE IT CANNOT KNOW. "Drawn by the tool itself" is false for a
panel the PLUGIN drew from the tool's numbers - a second scale, a derived matrix - and the
distinction between those two is exactly what the upstream-plot accounting exists to protect. A
caption that gets it wrong undoes that accounting at the last step.

So whatever draws a figure writes its legend, next to it, in this format. The host prefers it and
keeps the filename fallback for anything undescribed, so nothing regresses for a plugin that has
not been changed.

Nothing here knows what a figure shows. It knows that a legend must exist, must not be empty, and
must say truthfully who drew it.

THE HOST OWNS THE FORMAT AND MUST THEREFORE OWN A WRITER FOR IT - both languages.

MEASURED ON A SEALED RUN: 711 panels, 69 with a written legend and 642 with none. The reason was
structural rather than careless. This module had FOUR read sites in the host and not one writer in
production: `write` below was dead code, and the only thing in the whole repository that produced
a `captions.tsv` was R embedded inside ONE plugin, which had copied the format into three separate
scripts of its own. A format that is host-owned in name and plugin-implemented in fact costs the
SECOND plugin the whole of the work again, from a specification that exists only as three copies
of somebody else's `write.table` call - and the third copy is where the copies start to disagree.

So this module hands the writer over instead of describing it:

  `write`          the Python writer, and the only one. Same bytes as the R writer below.
  `R_SOURCE`       the same writer in R, with a draw wrapper around it: open a device, evaluate
                   the caller's plotting expression, close the device, append the legend row.
                   Generated from the constants in this file, so there is one definition of the
                   format and the R is derived from it rather than parallel to it.
  `block`          both of those as plain JSON, for the channel a plugin already reads.

A PLUGIN NEVER IMPORTS THE HOST - it runs in another interpreter, often another environment - so
the writer travels the way everything else the host computes travels: inside `in.json`. See
`figure_context.build`, which is the block that already reaches every plugin, and the comment
there recording why this rides inside it.
"""

from __future__ import annotations

import csv
import os
from pathlib import Path

#: The file a plugin writes beside the figures it just drew.
NAME = "captions.tsv"

#: `file` is the figure's basename; `caption` is its legend; `drawn_by` is who drew it.
COLUMNS = ("file", "caption", "drawn_by")

#: WHO DREW A PANEL, and the two answers are not interchangeable. `tool` is the wrapped tool's own
#: plotting function, unmodified. `plugin` is this plugin drawing the tool's NUMBERS itself -
#: a second scale, a derived matrix, an annotation layer - which is a different claim about
#: provenance and must not be reported as the tool's own encoding.
DRAWN_BY = ("tool", "plugin")

#: THE BAR A LEGEND HAS TO CLEAR, in words. Named because three parties apply it and a number
#: typed out three times is a number that drifts: `check` below, `Context.emit_figure` when a
#: Python plugin emits a panel, and the R writer this module generates. Four words is a label -
#: "interaction flow by diet" - and a label in the place a description goes reads as the
#: description rather than as a fallback, which is the defect this whole module exists for.
MIN_LEGEND_WORDS = 5


class BadCaption(Exception):
    """A legend is missing, empty, or claims a provenance that is not one of the two."""


def _flat(value):
    """One line, always: whitespace collapsed, ends trimmed. The one normalisation.

    THE FILE IS TAB-SEPARATED AND UNQUOTED, so a field carrying a tab or a newline does not
    corrupt one row - it shifts every column after it, or splits the row in two, and the reader
    then drops what it cannot parse. Collapsing here is what makes the written file unable to
    express the broken shape, rather than trusting a caption not to contain a tab.

    `str.split()` and not a regular expression, because this is exactly what `read` below does to
    a caption it reads back: one definition of "collapse", so a row survives a write and a read
    unchanged. It folds every Unicode space, not only the ASCII ones - a non-breaking space
    arrives in a caption the moment somebody pastes a phrase in - and the R writer matches it
    with PCRE's `(*UCP)`, which is the flag that makes R's `\\s` agree with this.

    THE AGREEMENT IS NOT TOTAL, and the residue is recorded rather than chased. `str.split()`
    folds the C0 separators - U+001C..U+001F - and PCRE's `\\s` does not, `(*UCP)` included:
    measured, `a\\x1fb` leaves Python `61 20 62` and R `61 1f 62`. So byte-identity between the
    two writers is true of the captions anyone writes and is, strictly, fixture-bound. It costs a
    reader nothing: `read` collapses every caption through this same function on the way back, so
    both files parse to the same legend. Widening the R pattern to match would put a second,
    hand-maintained definition of "whitespace" in the generated source - which is the drift this
    module exists to remove - for a character no caption contains.
    """
    return " ".join(str("" if value is None else value).split())


def check(rows):
    """Raise unless every row has a file, a non-trivial legend, and a valid provenance."""
    bad = []
    for i, r in enumerate(rows or [], 1):
        f = _flat((r or {}).get("file", ""))
        c = _flat((r or {}).get("caption", ""))
        by = _flat((r or {}).get("drawn_by", ""))
        if not f:
            bad.append(f"row {i}: no file")
        elif len(c.split()) < MIN_LEGEND_WORDS:
            bad.append(f"{f}: a legend of {len(c.split())} word(s) is a label, not a legend")
        elif by not in DRAWN_BY:
            bad.append(f"{f}: drawn_by={by!r}, expected one of {DRAWN_BY}")
    if bad:
        raise BadCaption("; ".join(bad[:6]))
    return True


def header_line():
    """The first line of the file, without its newline."""
    return "\t".join(COLUMNS)


def row_line(row):
    """One legend as it appears in the file, without its newline.

    THE FORMAT IS ONE FUNCTION, in one language, and the R writer is generated from the same
    constants - because the alternative was measured: one plugin carried three copies of it, and
    a fourth party wanting to write legends had nothing to read but those copies.

    Unquoted, which is not an accident: R's `write.table(sep = "\\t", row.names = FALSE,
    quote = FALSE)` is what produced every legend file that exists today, and this writes the
    same bytes so a file from either writer is the same file. `_flat` above is what makes
    quoting unnecessary rather than merely absent.
    """
    r = row or {}
    # THE BASENAME, BECAUSE THAT IS WHAT THE COLUMN IS. `read` keys on `os.path.basename`, so a
    # caller handing over the path it just saved to writes a key nobody looks up under - and the
    # R wrapper, which is handed a path by construction, takes the basename too. Two writers that
    # normalise a column differently do not produce the same file for the same panel.
    vals = {c: r.get(c, "") for c in COLUMNS}
    vals["file"] = os.path.basename(str(vals.get("file") or ""))
    return "\t".join(_flat(vals[c]) for c in COLUMNS)


def write(path, rows):
    """Write the legends for one directory of figures. Refuses a row that fails `check`.

    STILL NOT WIRED, AND SAYING SO IS THE POINT. Nothing in production calls this - `grep -rn
    'captions.write'` over the host finds this definition and one test. What it is today is the
    format's REFERENCE implementation: the executable half of a specification that previously
    existed only as three divergent copies of a `write.table` call inside one plugin's R, and the
    thing `r_source` below is checked against byte for byte. Wiring a Python plugin's emit path
    through it is a later wave and is the maker's call, not this module's.

    THE ONLY PYTHON WRITER. It used to say the plugin-side file "is not written here" and to serve
    nothing at all - no reference, no test, no reader to check against - so the format's only
    implementation was those three copies. That is the state this replaces: a host that owns a
    format it cannot produce hands the next plugin a specification with nothing to compare to.

    REFUSES RATHER THAN WARNS, because this writer has the whole set in hand before it writes
    anything: a bad row can still be fixed by its author. The R writer cannot - by the time it
    sees a bad legend the panel is already on disk and the run is half an hour in - so it refuses
    THAT ROW, loudly, and keeps the rest. Both leave the same trace on the page: a panel with no
    legend says so, in the reader's own words, rather than showing a label as if it were a
    description.

    LF, EXPLICITLY. `csv.writer` terminates with CRLF by default, which is not what R writes and
    not what this file has ever contained; a writer that quietly changed line endings would make
    two byte-identical legend sets differ in every row.
    """
    rows = [dict(r) for r in (rows or [])]
    check(rows)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join([header_line()] + [row_line(r) for r in rows]) + "\n"
    with open(p, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    return p


def read(directory):
    """{figure basename: {caption, drawn_by}} for one directory, or `{}`.

    Looked for beside the figures AND one level up, because a plugin may write its figures into a
    `figures/` subdirectory and its tables beside it, and neither placement should be the one that
    silently loses the legends.
    """
    d = Path(directory)
    out, malformed = {}, []
    for cand in (d / NAME, d.parent / NAME):
        if not cand.is_file():
            continue
        try:
            with open(cand, newline="", encoding="utf-8") as fh:
                # QUOTE_NONE, BECAUSE THE FILE IS WRITTEN WITH quote = FALSE. Read with the
                # default QUOTE_MINIMAL, a field that merely STARTS with a double quote is
                # treated as a quoted field, and two things happen, neither of them visible:
                # a legend that quotes a term loses its quote marks, and a legend with an ODD
                # number of them swallows every remaining line of the file into itself. Measured
                # on a two-row file: one unbalanced quote in the first caption left one row whose
                # caption contained the whole of the second row, `drawn_by` missing - and the
                # surplus-field guard below could not see it, because there was no surplus.
                # Every legend after the first was gone and the page rendered normally.
                for r in csv.DictReader(fh, delimiter="\t", quoting=csv.QUOTE_NONE):
                    # A ROW WITH EXTRA FIELDS IS A CORRUPTED ROW, NOT A ROW TO GUESS AT. The
                    # file is tab-separated and a writer that does not quote turns one caption
                    # containing a tab into a row whose columns are all shifted. `DictReader`
                    # parks the surplus under the key `None`, which is the only signal that
                    # happens - and dropping such a row silently is how a figure comes to carry
                    # a neighbouring figure's legend.
                    if r.get(None):
                        malformed.append(str(r.get("file", "?")))
                        continue
                    f = os.path.basename(_flat(r.get("file", "")))
                    cap = _flat(r.get("caption", ""))
                    if f and cap:
                        out.setdefault(f, {"caption": cap,
                                           "drawn_by": _flat(r.get("drawn_by", ""))})
        except (OSError, ValueError):
            continue
    if malformed:
        # SAY IT, DO NOT ONLY SKIP IT. A legend file that lost rows renders as a page whose
        # figures fall back to their filenames, which is indistinguishable from a plugin that
        # never wrote legends at all.
        print(f"  {len(malformed)} malformed legend row(s) in {d}: {', '.join(malformed[:4])}")
    return out


def provenance(drawn_by, function=""):
    """The sentence naming who drew a panel, or "" when nothing is known.

    THE DEFAULT SAYS NOTHING RATHER THAN GUESSING. A caption that asserts the wrong provenance is
    worse than one that omits it: the first is checked and believed, the second is noticed.
    """
    by = str(drawn_by or "").strip()
    fn = str(function or "").strip()
    if by == "tool":
        return f"Drawn by the tool's own {fn}()." if fn else "Drawn by the wrapped tool."
    if by == "plugin":
        return (f"Drawn by this plugin from {fn}()'s own numbers, not by {fn}() itself."
                if fn else "Drawn by this plugin from the tool's own numbers.")
    return ""


# -------------------------------------------------------------------------------------------
# THE SAME WRITER, IN R.
#
# A PLUGIN THAT EMBEDS R CANNOT IMPORT THIS MODULE, so the host hands over source instead of an
# API. What it hands over is the whole draw site and not only the writer - `scp_draw` opens the
# device, evaluates the caller's plotting expression, closes the device and appends the row -
# because the three copies this replaces were all copies of the WRAPPER, and every defect they
# accumulated lived in the wrapper rather than in the format: a helper called in one script and
# defined only in its sibling, a legend recorded for a panel that then failed and was deleted, an
# abort that lost every legend written before it.
#
# A MODULE-LEVEL STRING RATHER THAN A `.R` FILE BESIDE THIS ONE, and the reason is packaging:
# `pyproject.toml` declares `packages = ["scprofile"]` and no package data, so a data file in
# this directory works from a checkout and is silently absent from an installed wheel. The
# failure would appear only after `pip install`, as a plugin whose legends stopped being written,
# which is precisely the shape of failure this module exists to remove.
#
# NAMED FROM THE HOST, NOT FROM ANY PLUGIN. Every name here is `scp_`-prefixed, so counting the
# plugins that took the host's writer - and the panels that went through it - is `grep -c
# 'scp_draw('`, mechanically, rather than an argument about which local wrapper is a copy of it.
_R_TEMPLATE = r"""
# scprofile: the host's figure-legend writer. GENERATED from the host's own constants - a plugin
# sources this text; it does not keep a copy of it, and a copy that has been edited is a fork of
# a format four host read sites parse.
scp_captions <- new.env(parent = emptyenv())
scp_captions$file      <- "@CAPTIONS_FILE@"
scp_captions$columns   <- c(@CAPTIONS_COLUMNS@)
scp_captions$drawn_by  <- c(@CAPTIONS_DRAWN_BY@)
scp_captions$min_words <- @CAPTIONS_MIN_WORDS@
scp_captions$dir       <- NULL
scp_captions$drawn     <- 0L
scp_captions$refused   <- character(0)
scp_captions$failed    <- character(0)
# EVERY DIRECTORY THIS PROCESS HAS ALREADY STARTED A FILE IN. A run draws into one directory per
# unit, so the file for the second unit is created by the first legend that lands there rather
# than by an `open` call - and it must be truncated exactly once, the same way an opened directory
# is, or a second run appends to the first run's rows and the reader (which keeps the FIRST row
# for a file name) serves the older legend forever.
scp_captions$started   <- character(0)

# ONE LINE, ALWAYS. The file is tab-separated and written unquoted, so a caption carrying a tab
# or a newline does not corrupt one row - it shifts every column after it, or splits the row in
# two, and the host's reader then drops what it cannot parse. Collapsing here makes the written
# file unable to express the broken shape.
#
# (*UCP) IS LOAD-BEARING. Without it R's \s is the ASCII whitespace class and Python's
# str.split() - which is what the host reader collapses with - also folds every Unicode space.
# A non-breaking space in a caption, which is what arrives whenever a phrase is pasted in, then
# survives on one side and not the other, and the two writers stop producing the same bytes.
scp_caption_field <- function(x) {
  x <- paste(as.character(x), collapse = " ")
  x <- gsub("(*UCP)\\s+", " ", x, perl = TRUE)
  gsub("^ | $", "", x)
}

scp_caption_line <- function(file, caption, drawn_by) {
  paste(c(scp_caption_field(file), scp_caption_field(caption), scp_caption_field(drawn_by)),
        collapse = "\t")
}

# START THE FILE FOR ONE DIRECTORY OF FIGURES, ONCE PER PROCESS. Truncating is deliberate: the
# rows are appended one at a time as panels are drawn, so a second run into the same directory
# would otherwise accumulate two runs' legends and the reader - which keeps the FIRST row for a
# file name - would serve the older one. Truncating TWICE is the same defect mirrored: a run that
# files legends beside the panels reaches this for every new subdirectory, and if it truncated
# whenever the directory looked new it would erase the rows it wrote a moment ago.
scp_captions_ensure <- function(dir) {
  dir.create(dir, showWarnings = FALSE, recursive = TRUE)
  # ONE KEY PER DIRECTORY, NOT PER SPELLING OF IT. "figures", "./figures" and the absolute path
  # are one file; keyed on the string the second spelling counts as unseen and truncates what the
  # first already wrote. `normalizePath` is called AFTER `dir.create` because with `mustWork =
  # FALSE` it returns a path that does not exist unchanged - it would resolve nothing.
  key  <- normalizePath(dir, winslash = "/", mustWork = FALSE)
  path <- file.path(dir, scp_captions$file)
  if (key %in% scp_captions$started && file.exists(path)) return(invisible(path))
  con <- file(path, open = "wb")
  on.exit(close(con), add = TRUE)
  writeLines(enc2utf8(paste(scp_captions$columns, collapse = "\t")), con, useBytes = TRUE)
  scp_captions$started <- unique(c(scp_captions$started, key))
  invisible(path)
}

# THE CALL A PLUGIN MAKES. It names the directory a bare file name belongs to and starts the file
# there. An explicit open always truncates - it is how a script says "these are this run's
# legends" - so the directory is dropped from the started set first.
scp_captions_open <- function(dir) {
  dir.create(dir, showWarnings = FALSE, recursive = TRUE)
  scp_captions$dir <- dir
  scp_captions$started <- setdiff(scp_captions$started,
                                  normalizePath(dir, winslash = "/", mustWork = FALSE))
  scp_captions_ensure(dir)
}

# APPENDED THE MOMENT THE PANEL EXISTS, not accumulated and written at the end. An abort in a
# later section of a script left the legend file unwritten, so panels drawn BEFORE the failure
# silently lost their legends and fell back to their filenames - a degradation that renders as a
# normal page. `on.exit` was the first answer to that and it is not one at the top level of a
# script; a row on disk per panel needs no exit handler to be correct.
#
# BYTES, NOT TEXT. `enc2utf8` plus useBytes = TRUE writes UTF-8 whatever the locale of the node
# happens to be. The host reader opens this file as UTF-8 and a UnicodeDecodeError is a
# ValueError, which it catches and treats as "no legends here" - so one accented word written in
# a latin-1 locale silently costs a whole directory its legends.
scp_legend <- function(file, caption, drawn_by = "tool", dir = NULL) {
  f  <- scp_caption_field(basename(file))
  cp <- scp_caption_field(caption)
  by <- scp_caption_field(drawn_by)
  n  <- if (nzchar(cp)) length(strsplit(cp, " ", fixed = TRUE)[[1]]) else 0L
  why <- NULL
  if (!nzchar(f)) {
    why <- "no file name"
  } else if (n < scp_captions$min_words) {
    why <- sprintf("a legend of %d word(s) is a label, not a legend", n)
  } else if (!(by %in% scp_captions$drawn_by)) {
    why <- sprintf("drawn_by=%s, expected one of %s", by,
                   paste(scp_captions$drawn_by, collapse = "/"))
  }
  # REFUSED, AND SAID OUT LOUD. Writing a four-word label anyway would put a label where the page
  # prints a description, and a label there reads as the description. The page says a panel has
  # no legend; that is noticed, and a wrong description is believed.
  if (!is.null(why)) {
    scp_captions$refused <- c(scp_captions$refused, f)
    cat("legend REFUSED for", f, "-", why,
        "- this panel will be reported as having no legend\n")
    return(invisible(FALSE))
  }
  # WHERE THE ROW IS FILED, and the order matters. An explicit `dir` wins because the only caller
  # that passes one - `scp_draw` - has the panel's real path in hand and files the legend BESIDE
  # it. Then the opened directory, for the ordinary `scp_captions_open` + bare-file-name shape.
  # `dirname(file)` is last and only when nothing was opened, because a caller that was handed a
  # path may have been handed a RELATIVE one that names the column value and not a location on
  # disk - "figures/flow.png" written from the run root is one row of the run root's file.
  if (is.null(dir)) dir <- scp_captions$dir
  if (is.null(dir)) {
    dir <- dirname(file)
    if (identical(dir, ".")) {
      cat("legend for", f, "not written: call scp_captions_open(<figure directory>) first,",
          "or pass a path rather than a bare file name\n")
      return(invisible(FALSE))
    }
  }
  path <- scp_captions_ensure(dir)
  con <- file(path, open = "ab")
  on.exit(close(con), add = TRUE)
  writeLines(enc2utf8(scp_caption_line(f, cp, by)), con, useBytes = TRUE)
  invisible(TRUE)
}

# THE DRAW SITE. `expr` is a promise and is evaluated HERE, inside the guard, so one failing
# plot costs its own file and not the run.
#
# `render = "force"` is not a second wrapper. The two scripts this replaces each carried an
# `npng` that prints its expression and an `ndev` that forces it - because some plotting
# functions return an object and others draw as a side effect - and one of the two scripts was
# written by copying the other and inherited the CALLS to `ndev` without its definition. R does
# not hoist, so the loop died at the first call with "could not find function", after one framing
# of two had been drawn and with the tally reporting no failure. One function with an argument
# cannot be half-copied.
#
# THE DEVICE IS CLOSED BY NUMBER. `dev.off()` closes whatever is current, and a plotting
# expression that opens a device of its own and leaves it open makes that somebody else's - so
# ours stays open, the file is never flushed, and the panel is written at some unrelated moment
# later in the run.
scp_draw <- function(path, expr, legend = "", drawn_by = "tool",
                     width = 1800, height = 1500, res = 200,
                     device = grDevices::png, render = "print", ...) {
  dir.create(dirname(path), showWarnings = FALSE, recursive = TRUE)
  dn <- NULL
  ok <- tryCatch({
    device(path, width = width, height = height, res = res, ...)
    dn <- grDevices::dev.cur()
    if (identical(render, "force")) force(expr) else print(expr)
    TRUE
  }, error = function(e) {
    cat("figure", basename(path), "FAILED:", conditionMessage(e), "\n")
    FALSE
  })
  if (!is.null(dn) && dn %in% grDevices::dev.list()) {
    try(grDevices::dev.off(dn), silent = TRUE)
  }
  # WHAT IS ON DISK, NOT WHAT THE EXPRESSION RETURNED. The device creates the file when it opens,
  # so a plot that failed leaves a zero-byte PNG behind - which the host would place on a page,
  # and a reader would meet as a broken image with a legend under it.
  size <- if (file.exists(path)) file.info(path)$size else 0
  if (ok && !is.na(size) && size > 0) {
    scp_captions$drawn <- scp_captions$drawn + 1L
    # BESIDE THE PANEL, NOT BESIDE THE `open` CALL. This passed no `dir` and fell back to
    # scp_captions$dir, which is correct only while every panel lands in the opened directory.
    # Open once and draw into a subdirectory per unit - the normal shape for this host - and every
    # legend went into ONE shared file: the host's reader searches one level up, finds it, and
    # keys on the BASENAME, so unitB/roles.png was served unitA's legend. MEASURED with real
    # Rscript: both units drew a `roles.png`, and both were reported with the FIRST unit's
    # sentence. Drawing outside the opened tree was worse still - the legend was filed where the
    # reader never looks and read() came back {}. Both are the failure this module's own header
    # calls WORSE than no caption at all: a caption asserting a provenance it cannot know.
    # `path` is the file the device just wrote, so its directory is not a guess.
    scp_legend(path, legend, drawn_by, dir = dirname(path))
    cat("figure", basename(path), "written\n")
    return(invisible(TRUE))
  }
  scp_captions$failed <- c(scp_captions$failed, basename(path))
  if (file.exists(path)) unlink(path)
  invisible(FALSE)
}

# WHAT THIS SCRIPT DREW, IN ONE LINE, so a run's log says how many panels and how many legends
# rather than leaving both to be counted from the directory afterwards.
scp_draw_tally <- function() {
  cat("figures:", scp_captions$drawn, "written,", length(scp_captions$failed), "failed,",
      length(scp_captions$refused), "legend(s) refused\n")
  invisible(list(drawn = scp_captions$drawn, failed = scp_captions$failed,
                 refused = scp_captions$refused))
}
"""


def r_source():
    """The R writer and draw wrapper, as text a plugin can `source()` or paste into its script.

    SUBSTITUTED, NOT RETYPED. The file name, the column names, the two valid provenances and the
    word bar come from the constants above, so the R cannot drift from the Python that reads what
    it writes. `str.format` is unusable here - R is written in braces - so the placeholders are
    `@NAMED@` and the substitution is plain.
    """
    return (_R_TEMPLATE
            .replace("@CAPTIONS_FILE@", NAME)
            .replace("@CAPTIONS_COLUMNS@", ", ".join(f'"{c}"' for c in COLUMNS))
            .replace("@CAPTIONS_DRAWN_BY@", ", ".join(f'"{b}"' for b in DRAWN_BY))
            .replace("@CAPTIONS_MIN_WORDS@", str(MIN_LEGEND_WORDS)))


def block():
    """The format and both writers, as plain JSON, for the channel that reaches every plugin.

    NO IMPORT, IN EITHER LANGUAGE. A plugin runs in its own interpreter and often its own
    environment; the only thing it is guaranteed to be able to read is its `in.json`. So the
    writer travels as data, the same way the colour map and the unit stamp do - see
    `figure_context.build`, which carries this - and a plugin that embeds R writes
    `ctx.figure_context["captions"]["r_source"]` to a file and sources it.

    The Python half is described rather than shipped: a plugin already running in Python has the
    host on its path through `ctx`, and what it needs from here is the shape it must produce.
    """
    return {"file": NAME,
            "columns": list(COLUMNS),
            "drawn_by": list(DRAWN_BY),
            "min_words": MIN_LEGEND_WORDS,
            "r_source": r_source()}
