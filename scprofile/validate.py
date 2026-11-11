"""Validate a plugin and its references, without running anything.

Every check here exists because something got through. They are not style rules: each one is a
defect that produced, or would have produced, a plausible wrong answer rather than an error.

    hard-coded column     a plugin naming `cell_type` works on one project and silently finds
                          nothing on the next
    os.cpu_count()        reports the NODE, not the plugin's share, so four concurrent plugins
                          each start the node's worth of threads
    an unfilled UPSTREAM  the template carries every heading a shallower check looks for, so a
                          file recording no reading at all passes one
    a lock with ranges    resolves differently later; the tool it pins was written against
                          versions two majors back
    a reference with no   cannot be shown to be the file the result was produced against, and a
    checksum              truncated database returns a smaller answer rather than an error
    a scaffold's TODO     a plugin that was generated and never implemented, whose empty result
                          is indistinguishable from a real one

`validate` is static. `validate --deep` additionally hashes the references on disk, which is what a
run does before trusting them.
"""
from __future__ import annotations

import re
from pathlib import Path

HEX64 = re.compile(r"^[0-9a-f]{64}$")

#: `a, b = ctx.populations()`, captured so the two names can be checked.
_POPS_UNPACK = re.compile(r"([A-Za-z_]\w*)\s*,\s*([A-Za-z_]\w*)\s*=\s*ctx\.populations\(")

#: THE ONLY CORRECT TWO-NAME READING. `populations()` returns `(mask, groups)` - a boolean mask
#: over every cell and the labels of the real ones - and FOUR plugins in this repository have
#: destructured it as `(populations, dropped)`, which is what its name asks for and not what it
#: gives. The wrong reading is silent in the worst way: `len(pops)` becomes the cell count, so a
#: refusal that should fire never does and a headline claims a hundred thousand populations, while
#: `if dropped:` asks the truth value of an array and raises. Four occurrences of one mistake is a
#: statement about the affordance, so the object now carries `.names` and `.dropped` too - and
#: this check is what stops the fifth.
_POPS_OK = {("mask", "groups"), ("real", "groups"), ("_mask", "groups"), ("mask", "_groups")}

#: Names a plugin must not hard-code where the profile defines a key for it.
DOMAIN_LITERALS = ("cell_type", "celltype", "leiden", "louvain", "X_umap", "X_pca",
                   "n_genes", "pct_counts_mt", "sample_id")


class Finding:
    __slots__ = ("level", "check", "detail")

    def __init__(self, level, check, detail=""):
        self.level, self.check, self.detail = level, check, detail

    def __repr__(self):
        return f"{self.level}: {self.check}" + (f" — {self.detail}" if self.detail else "")


def _src(p):
    """Source with comment-only lines stripped, so a check cannot pass on its own explanation."""
    return "\n".join(l for l in p.read_text(encoding="utf-8").splitlines()
                     if not l.strip().startswith("#"))


def validate_plugin(kernel):
    """Static checks on one plugin. Returns [Finding]."""
    f, d, spec = [], Path(kernel.path), kernel.spec
    built = kernel.status == "built"
    wraps = spec.get("wraps") or {}

    # A ONE-FILE PLUGIN carries its upstream record, its selftest and its environment IN the file.
    # Every check below was written against the directory shape and looked for siblings that a
    # one-file plugin does not have - so the shape the host now prefers failed its own validator.
    if not d.is_dir():
        # A DECLARATION THE HOST COULD NOT LOAD IS NAMED FIRST (W032): the host lists the plugin
        # with an empty spec and the sentence why (`kernels.read_declaration`), so every finding
        # below it is a consequence of this one.
        if getattr(kernel, "declaration_error", None):
            f.append(Finding("ERROR", "its declaration does not load", kernel.declaration_error))
        # ONE CHECK, SHARED. The builder refuses what validate refuses; a builder that accepts
        # what validate rejects installs something nobody can maintain.
        from . import declare
        for lvl, msg in declare.check(spec, kernel.name):
            f.append(Finding(lvl, msg.split(".")[0][:70], msg))
        src = d.read_text(encoding="utf-8", errors="replace")
        # AN AXIS THE SCRIPT HOLDING THE SITE DOES NOT DRAW BY, said here and not by the run
        # (harness ADR-0026, the static half of K-o).
        for lvl, msg in declare.draw_site_phase(src, spec):
            f.append(Finding(lvl, msg.split(".")[0][:70], msg))
        up_inline = spec.get("upstream") or {}
        if wraps and not up_inline:
            f.append(Finding("ERROR", "wraps a tool and records nothing about it",
                             "a one-file plugin carries PLUGIN['upstream']: the docs it was "
                             "read from, the defaults it changed and what it does not use"))
        for field, why in (("docs", "where the record came from"),
                           ("defaults_changed", "the defaults that are wrong for this contract"),
                           ("not_used", "what of the tool is deliberately not used")):
            if up_inline and not up_inline.get(field):
                f.append(Finding("WARN", f"upstream records no {field}", why))
        for m in _POPS_UNPACK.finditer(src):
            if (m.group(1), m.group(2)) not in _POPS_OK:
                f.append(Finding(
                    "ERROR", f"reads ctx.populations() as ({m.group(1)}, {m.group(2)})",
                    "it unpacks as (mask, groups) - a boolean mask over EVERY cell, and the "
                    "labels of the real ones. Four plugins have read it as (populations, "
                    "dropped): `len(...)` then returns the cell count and `if dropped:` asks the "
                    "truth value of an array. Use `p = ctx.populations()` and `p.names` / "
                    "`p.dropped`, or name the two `mask, groups`"))
        if "def selftest(" not in src:
            f.append(Finding("WARN", "no selftest(ctx) in the file",
                             "the builder runs it on every new machine to prove the call is "
                             "well-formed against the versions installed there"))
        if not spec.get("cannot_show"):
            f.append(Finding("ERROR", "declares no limits",
                             "almost every method here rests on an assumption a reader must be "
                             "told about"))
        return f


    for req in ("name", "summary"):
        if not spec.get(req):
            f.append(Finding("ERROR", f"{req} missing from kernel.yml"))
    if not kernel.cannot_show:
        f.append(Finding("ERROR", "cannot_show is empty",
                         "a result whose limits were never written down reads exactly as "
                         "authoritative as one whose limits were thought about"))
    if spec.get("layer") not in (None, "stack", "checkpoint"):
        f.append(Finding("ERROR", "layer must be stack or checkpoint", str(spec.get("layer"))))
    # EVERY BUILT PLUGIN, not only the ones being compared. The plan tells a user which of their
    # columns and layers each plugin will touch, and it can only do that from `sees` - so an
    # under-declared manifest makes a plugin look like it reads nothing at all. cellcycle scored
    # from a lognorm layer it never declared, and the plan dutifully reported no inputs.
    if spec.get("sees") is None and built:
        f.append(Finding("WARN", "sees is not declared",
                         "the plan reports which of a user's columns and layers each plugin will "
                         "read, and it reads that from here; without it the plugin appears to "
                         "consume nothing"))
    if spec.get("sees") is None and (kernel.needs_design or spec.get("per_unit")):
        f.append(Finding("WARN", "sees is not declared",
                         "any plugin that will be compared against others must declare what it "
                         "was shown; an empty list is a claim, not an omission"))

    entry = d / (spec.get("entry") or "run.py")
    if built and not entry.exists():
        f.append(Finding("ERROR", f"entry point {entry.name} does not exist"))
    if built and entry.exists():
        s = _src(entry)
        if "SCAFFOLD" in s or "this is a SCAFFOLD" in s:
            f.append(Finding("ERROR", "still a scaffold",
                             "declared built, but run.py refuses; implement it or set "
                             "status: planned"))
        if "os.cpu_count()" in s:
            f.append(Finding("ERROR", "run.py calls os.cpu_count()",
                             "that reports the node, not this plugin's share. Use "
                             "in.json['resources']['cores']"))
        lit = [x for x in DOMAIN_LITERALS if f'"{x}"' in s or f"'{x}'" in s]
        if lit:
            f.append(Finding("WARN", "hard-coded domain name(s) in run.py", ", ".join(lit)
                             + " — resolve through in.json['keys'] instead"))
        if "sentinels" not in s and kernel.needs_obs:
            f.append(Finding("WARN", "run.py never mentions sentinels",
                             "a sentinel is not a cell type and must not be dropped"))

    if spec.get("needs_env", True):
        lock = d / "lock.yml"
        if not lock.exists():
            # Only a BUILT plugin is required to have one; a planned plugin legitimately has not
            # been locked yet.
            if built:
                f.append(Finding("ERROR", "needs_env but no lock.yml"))
        else:
            # A LOCK THAT EXISTS IS CHECKED, built or not. These checks used to run only for a
            # built plugin, and four of the five locks in this tree belong to plugins that are
            # `status: planned` - environments that are installed, proved by their own selftests,
            # and were being validated by nothing at all. A plugin's status is about its run.py;
            # its lock is about its environment, and the two arrive in either order.
            # A lock has three kinds of `- ` line and only one is a dependency: channel
            # names, the bare `pip` that enables the pip section, and actual packages. Counting
            # all three reported `- conda-forge` as unpinned, which is noise that trains a reader
            # to ignore the check.
            pins, r_pins, section = [], [], None
            for raw in lock.read_text().splitlines():
                s = raw.split("#", 1)[0].strip()
                if s.endswith(":") and not s.startswith("- "):
                    section = s[:-1]
                    continue
                if s.startswith("- pip:"):
                    section = "pip"
                    continue
                if not s.startswith("- ") or section == "channels":
                    continue
                dep = s[2:].strip()
                if section == "r":
                    r_pins.append(dep)
                    continue
                if dep in ("pip", "python") or dep.startswith("python="):
                    continue
                pins.append(dep)
            loose = [x for x in pins if "==" not in x and "=" not in x]
            if loose:
                f.append(Finding("ERROR", "lock.yml has unpinned dependencies",
                                 ", ".join(loose[:5]) + " — a lock with ranges is not a lock"))
            # An `r:` entry is either a git commit or a CRAN version, and a tag or a branch is
            # neither: a branch moves, and a tag can be re-pointed at a different commit with no
            # version changing anywhere, so both read as pinned while neither is.
            from .runner import r_pin_kind
            loose_r = [x for x in r_pins if r_pin_kind(x) is None]
            if loose_r:
                f.append(Finding("ERROR", "lock.yml has r: entries that are not pinned exactly",
                                 ", ".join(loose_r[:5]) + " — each must be "
                                 "owner/repo@<40-char commit> or Package==<version>; a branch or "
                                 "a tag is not a pin"))
            if r_pins and not any(x.split("=", 1)[0].strip() == "r-base" for x in pins):
                f.append(Finding("ERROR", "lock.yml installs R packages but pins no r-base",
                                 "every r-* package is built against one R minor version, so "
                                 "without that pin the same lock resolves differently later"))
        if built and not (d / "selftest.py").exists() and not (d / "selftest.R").exists():
            f.append(Finding("ERROR", "needs_env but no selftest",
                             "an environment nothing proved is one that fails inside a run"))

    if built and not spec.get("needs_env", True) \
            and not (d / "selftest.py").exists() and not (d / "selftest.R").exists():
        # The environment is not the only thing a selftest proves. It proves the CALL IS
        # WELL-FORMED against the installed version, which is what changes underneath a wrapper.
        # A host-interpreter plugin skipped this requirement, so nothing ever ran it before a real
        # cohort did — and a keyword the wrapped function forbids reached that cohort.
        f.append(Finding("WARN", "no selftest, and needs_env is false",
                         "a host-interpreter plugin is still a wrapper: only a selftest proves "
                         "the call is well-formed against the version actually installed"))

    wraps = spec.get("wraps") or {}
    if wraps:
        up = d / "UPSTREAM.md"
        if not up.exists():
            f.append(Finding("ERROR", "wraps a tool but has no UPSTREAM.md"))
        else:
            s = up.read_text(encoding="utf-8")
            if "TODO" in s:
                f.append(Finding("ERROR", "UPSTREAM.md is still the template",
                                 f"{s.count('TODO')} TODO marker(s) — the template carries every "
                                 f"heading, so a shallower check would pass it"))
            for want, why in (("default", "the defaults that are wrong for this contract"),
                              ("http", "a link to what was read")):
                if want not in s.lower():
                    f.append(Finding("WARN", f"UPSTREAM.md does not mention {want}", why))
        for k in ("license", "cite"):
            if not wraps.get(k):
                f.append(Finding("WARN", f"wraps.{k} not recorded"))
    elif built and spec.get("plans_to_wrap"):
        f.append(Finding("WARN", "built, but still declares plans_to_wrap",
                         "promote it to `wraps:` so the UPSTREAM.md requirement takes effect"))
    return f


def validate_references(kernel, dest=None, organism=None, deep=False):
    """Checks on a plugin's declared references, and optionally on the files themselves."""
    f = []
    refs = kernel.references(organism)
    decl = (kernel.path / "references.yml")
    if not refs:
        if decl.exists() and "url:" in decl.read_text():
            f.append(Finding("WARN", "references.yml has entries the parser did not read",
                             "check the indentation — one level of nesting is supported"))
        return f

    from . import refs as _R

    for name, spec in refs.items():
        # THE CHECK IS DECIDED BY THE TIER, and this is the fix for a gate that was red on every
        # reference in the tree. `url` and `sha256` are the pins of a file THIS TOOL DOWNLOADS;
        # demanding them of a database that ships inside an R package reports a defect that
        # cannot be fixed, in the words of one that would "produce a plausible wrong answer".
        # `refs.status()` has honoured the three tiers since they were added - this function was
        # the copy that never heard about them. See `refs.TIERS`.
        tier = _R.tier_of(spec)
        if tier not in _R.TIERS:
            f.append(Finding("ERROR", f"reference {name!r} declares unknown tier {tier!r}",
                             f"one of {', '.join(_R.TIERS)} — an unrecognised tier is fetched as "
                             f"{_R.DEFAULT_TIER!r}, so a typo silently changes what pins it"))
            tier = _R.DEFAULT_TIER

        if tier == "fetch":
            if not spec.get("url"):
                f.append(Finding("ERROR", f"reference {name!r} has no url"))
            sha = str(spec.get("sha256") or "")
            if not sha:
                f.append(Finding("ERROR", f"reference {name!r} has no sha256",
                                 "it cannot be shown to be the file the result was produced "
                                 "against, and a truncated database returns a smaller answer "
                                 "than an error"))
            elif not HEX64.match(sha.lower()):
                f.append(Finding("ERROR", f"reference {name!r} sha256 is not a 64-char hex digest",
                                 sha[:20]))
            if not spec.get("size"):
                f.append(Finding("WARN", f"reference {name!r} declares no size",
                                 "the fetch cannot report the total or check it fits before "
                                 "starting"))

        elif tier == "bundled":
            # A BUNDLED REFERENCE IS PINNED BY ITS PACKAGE AND BY NOTHING ELSE, so the package is
            # the one field that carries any pin at all. Without it the declaration records that
            # a database was consulted and gives a reader no way to find which version.
            if not spec.get("package"):
                f.append(Finding("ERROR", f"reference {name!r} is bundled but names no package",
                                 "a bundled reference is pinned by the version of the package "
                                 "that ships it; with no package named, nothing pins it and "
                                 "nothing records what was consulted"))
            for k in ("url", "sha256"):
                if spec.get(k):
                    f.append(Finding("WARN", f"reference {name!r} is bundled but declares {k}",
                                     "the file used is the one inside the package; a url or "
                                     "digest here describes a copy the run does not read"))

        elif tier == "runtime":
            # NOTHING HERE PINS IT AND THE NETWORK IS NEEDED ON THE COMPUTE NODE. Both are facts
            # about the result, not defects in the declaration - a WARN a reader wants, not an
            # ERROR a maintainer cannot clear.
            if not spec.get("source"):
                f.append(Finding("ERROR", f"reference {name!r} is fetched at run time but names "
                                          f"no source",
                                 "a reader has no way to find out what was downloaded"))
            f.append(Finding("WARN", f"reference {name!r} is fetched at run time",
                             f"nothing pins it, so two runs may consult different data, and the "
                             f"COMPUTE NODE needs outbound access to "
                             f"{spec.get('source') or 'the network'} — a node without it fails "
                             f"after the queue slot is spent"))
        # A LIST OF WHAT THIS TOOL HAPPENS TO KNOW IS NOT A LIST OF WHAT IS VALID. Six species
        # were listed and every other one drew a warning - on a correct declaration, for a
        # correct organism, which is how a check trains people to ignore it. It stays only to
        # catch a typo in a name that is nearly one of these, and says which it is.
        _org = str(spec.get("organism") or "").lower()
        _known = ("human", "mouse", "rat", "zebrafish", "fly", "worm", "any")
        if _org and _org not in _known:
            import difflib
            _near = difflib.get_close_matches(_org, _known, n=1, cutoff=0.8)
            if _near:
                f.append(Finding("WARN", f"reference {name!r} organism {spec['organism']!r} "
                                         f"looks like a typo for {_near[0]!r}"))

    if dest:
        from . import refs as R
        for name, (state, path, detail) in R.status(kernel, dest, organism, verify=deep).items():
            if state != "present":
                f.append(Finding("ERROR", f"reference {name!r} is {state}", detail))
            elif "NO CHECKSUM" in detail:
                f.append(Finding("WARN", f"reference {name!r} present but unverifiable", detail))
            elif not deep:
                f.append(Finding("INFO", f"reference {name!r} size matches",
                                 "run with --deep to verify the checksum"))
    return f


def report(kernel, findings, log=print):
    """Print findings for one plugin. Returns the number of ERRORs."""
    errs = sum(1 for x in findings if x.level == "ERROR")
    warns = sum(1 for x in findings if x.level == "WARN")
    mark = "FAIL" if errs else ("warn" if warns else "ok  ")
    log(f"  {mark} {kernel.name:<12} {kernel.status:<8} "
        f"{errs} error(s), {warns} warning(s)")
    for x in findings:
        if x.level != "INFO":
            log(f"       {x.level:<5} {x.check}")
            if x.detail:
                log(f"             {x.detail}")
    return errs


# ------------------------------------------------- does a design-aware plugin take the host's model

#: The keywords by which a Python modelling library is told WHAT TO FIT or WHAT TO COMPARE. A call
#: carrying one of them is a site where a plugin turns the design into a model, and the site
#: where the reference level and the covariates are decided, whichever library it is.
FIT_KEYWORDS = ("design", "formula", "contrast", "design_factors", "ref_level", "reference")

#: What the host hands a design-aware plugin for those sites (`plugin.Context`).
HOST_MODEL = {"model_frame": "the fit's metadata: each term a categorical whose FIRST category "
                             "is the run's control, and every covariate the plan modelled, typed",
              "levels": "a term's levels in the order a contrast reads them - [0] is the "
                        "control - over the levels a subset actually has"}

#: The keyword arguments that carry a fit's DESIGN: the model (`design`, `formula`,
#: `design_factors`), the comparison (`contrast`, `ref_level`, `reference`, `levels`) and the sample
#: table the design is read from (`metadata`). A fit site is where THESE are decided. The call's
#: other arguments - the counts, a threshold, a flag such as `refit_cooks` or `alpha` - are the
#: method's, and no design answer changes them (W013's verifier, fix-up 3).
DESIGN_ARGUMENTS = FIT_KEYWORDS + ("levels", "metadata")

#: How far a fit site reaches back from its design arguments: the lines that define the names
#: they read (one hop), and the lines that define the names THOSE lines read (two). Two is what
#: the design takes in practice - the terms a formula is built from (`use, aliased =
#: _identifiable(...)`), the column an interaction contrast is picked from (`hits = ...`) - and
#: nothing further: a third hop reaches the counts and the configuration.
DESIGN_DEPTH = 2

#: Characters a line-oriented reader takes as a line break and Python's tokenizer does not, or
#: does differently. Eleven form feeds in a comment shifted every later line of a diff against the
#: `ast` line numbers its sites are counted in, and an edit in no site was admitted (fix-up 3).
#: A proposed file carrying any of them is refused; every line here is split on "\n" alone.
LINE_BREAKS = {"\x0b": "a vertical tab", "\x0c": "a form feed", "\x1c": "a file separator",
               "\x1d": "a group separator", "\x1e": "a record separator", "\x85": "a next-line",
               "\u2028": "a line separator", "\u2029": "a paragraph separator",
               "\r": "a carriage return"}

#: How a plugin STATES something to its reader at run time: the host's two calls for a sentence.
STATEMENT_CALLS = ("caveat", "refuse")

#: The words by which such a sentence says what was or was not CONTRASTED or MODELLED (GAP-C47).
#: Matched case-insensitively, as substrings, in the literal text of the call's arguments. Wide on
#: purpose: a sentence named here that says nothing about the design costs one confirmation, and
#: one missed is a claim about the design that nobody was asked to square with the host - which
#: is how a caveat came to say an interaction was "not contrasted" beside the row contrasting it.
DESIGN_WORDS = ("contrast", "interaction", "reference", "control", "covariate", "model",
                "formula", "baseline", "tested", "term", "fitted", "factor", "design")

#: What a statement owes the host.
STATEMENT_OWES = ("the design is the host's: which level each term is read against (`ctx.levels`) "
                  "and which covariates are modelled or refused (said once by `ctx.model_frame`). "
                  "The sentence says only what this plugin computed, and agrees with that decision")


def design_record_path(kernel):
    """`kernels/<plugin>.design.json`: the design worksheet's own record, beside the plugin.

    MAKER OUTPUT, written by `scprofile design --answer` and `--confirm` and by nothing else: every
    answer's diff with its reason and the digests of the file it was applied to and produced, and
    every statement taken as answered, by the digest of its syntax - so a sentence changed after
    it was answered owes again, and the plugin can be rebuilt from its base by replaying the
    maker's verb calls and then these answers (`--replay-into`).
    """
    p = Path(kernel.path)
    return p.with_name(p.stem + ".design.json")


def _read_record(kernel):
    import json
    p = design_record_path(kernel)
    rec = {}
    if p.is_file():
        try:
            rec = json.loads(p.read_text(encoding="utf-8"))
        except ValueError:
            rec = {"unreadable": str(p)}
    rec.setdefault("plugin", kernel.name)
    rec.setdefault("answers", [])
    rec.setdefault("statements", {})
    return rec


def _write_record(kernel, rec):
    import json
    design_record_path(kernel).write_text(json.dumps(rec, indent=1, sort_keys=True) + "\n",
                                          encoding="utf-8")


def _lines(text):
    """`text` as `ast` numbers its lines: split on "\n" alone, each line keeping its end."""
    parts = str(text).split("\n")
    return [x + "\n" for x in parts[:-1]] + ([parts[-1]] if parts[-1] else [])


def _line_breaks(text):
    """The characters of `LINE_BREAKS` a text carries, named, or []."""
    return [f"{name} (U+{ord(ch):04X})" for ch, name in LINE_BREAKS.items() if ch in str(text)]


def _sha(text):
    import hashlib
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _header_end(st):
    """A compound statement's header lines only; a simple statement whole."""
    import ast
    compound = (ast.For, ast.AsyncFor, ast.While, ast.If, ast.With, ast.AsyncWith, ast.Try,
                ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
    body = getattr(st, "body", None)
    if isinstance(st, compound) and body:
        return max(st.lineno, body[0].lineno - 1)
    return st.end_lineno


def _bound(st, mutated=False):
    """The names a statement binds: its targets, and the object a target mutates. With
    `mutated`, also the object an expression statement calls a method on (`x.update(...)`)."""
    import ast
    if isinstance(st, (ast.Import, ast.ImportFrom)):
        return {(a.asname or a.name).split(".")[0] for a in st.names}
    targets = (st.targets if isinstance(st, ast.Assign) else
               [st.target] if isinstance(st, (ast.AugAssign, ast.AnnAssign, ast.For,
                                              ast.AsyncFor)) else
               [i.optional_vars for i in st.items if i.optional_vars is not None]
               if isinstance(st, (ast.With, ast.AsyncWith)) else [])
    if mutated and isinstance(st, ast.Expr) and isinstance(st.value, ast.Call) \
            and isinstance(st.value.func, ast.Attribute):
        targets = [st.value.func.value]
    out, todo = set(), list(targets)
    while todo:
        t = todo.pop()
        if isinstance(t, (ast.Tuple, ast.List)):
            todo.extend(t.elts)
            continue
        while isinstance(t, (ast.Attribute, ast.Subscript, ast.Starred, ast.Call)):
            t = t.func if isinstance(t, ast.Call) else t.value
        if isinstance(t, ast.Name):
            out.add(t.id)
    return out


def _scan(src):
    """(fit sites, statement sites, attribute names called) of one plugin's source.

    A FIT site is a call carrying a `FIT_KEYWORDS` argument. Its SPANS are the call's statement
    and the lines that define the names its DESIGN arguments read (`DESIGN_ARGUMENTS`), up to
    `DESIGN_DEPTH` hops back, each definition above the line that reads it - `formula = ...` for
    `design=formula`, `levels = ...` and the loop header binding `term` for `contrast=[term,
    levels[-1], levels[0]]`, then the lines those read - in the function it is in: where a fit's
    frame, formula and levels are decided, and nothing else. A name the call also reads as one of
    its other arguments (the counts, the configuration), a parameter and an import are never
    followed. It was the whole loop or function around the call (fix-up 2), then every argument's
    names (fix-up 3). A STATEMENT site is a `ctx.caveat(...)` or `ctx.refuse(...)` whose literal
    words are design words; its span is the statement and the comment block directly above it.
    """
    import ast
    import hashlib
    tree = ast.parse(src)
    par = {}
    for node in ast.walk(tree):
        for ch in ast.iter_child_nodes(node):
            par[ch] = node
    lines = src.split("\n")              # as `ast` counts them (fix-up 3)
    def stmt_of(node):
        st = node
        while par.get(st) is not None and not isinstance(st, ast.stmt):
            st = par[st]
        return st

    header_end = _header_end
    bound = _bound

    def names_in(exprs):
        return {n.id for e in exprs for n in ast.walk(e) if isinstance(n, ast.Name)}

    def reads_of(t):
        """The names a defining statement READS - its header's, for a compound one."""
        parts = ([t.iter] if isinstance(t, (ast.For, ast.AsyncFor)) else
                 [t.test] if isinstance(t, (ast.While, ast.If)) else
                 [i.context_expr for i in t.items] if isinstance(t, (ast.With, ast.AsyncWith))
                 else [t])
        return {n.id for x in parts for n in ast.walk(x)
                if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}

    def fit_spans(node):
        """(spans, design names) of one fit call: its statement, and the lines defining the names
        its DESIGN arguments read, `DESIGN_DEPTH` hops back. A name the call also reads as one of
        its OTHER arguments (the counts, the configuration) is never followed, nor a parameter
        (given, not defined here), nor an import."""
        st = stmt_of(node)
        keep = set(range(st.lineno, st.end_lineno + 1))
        design = [k.value for k in node.keywords if k.arg in DESIGN_ARGUMENTS]
        other = list(node.args) + [k.value for k in node.keywords
                                   if k.arg not in DESIGN_ARGUMENTS]
        scope = par.get(st)
        while scope is not None and not isinstance(scope, (ast.FunctionDef,
                                                           ast.AsyncFunctionDef)):
            scope = par.get(scope)
        excluded = names_in(other)
        if scope is not None:
            # A PARAMETER IS GIVEN, NOT DEFINED HERE: `ctx` is read by `n_cpus=ctx.cores`, and
            # every `ctx.headline = ...` would otherwise count as a line defining it.
            a = scope.args
            excluded |= {x.arg for x in (a.posonlyargs + a.args + a.kwonlyargs
                                         + [v for v in (a.vararg, a.kwarg) if v])}
        body = [t for t in ast.walk(scope if scope is not None else tree)
                if isinstance(t, ast.stmt) and t is not scope
                and not isinstance(t, (ast.Import, ast.ImportFrom))]
        # EACH HOP: a name, and the line that READS it; a definition counts only above that line,
        # so a later statement reusing the name for something else (`hits = pd.DataFrame(...)`,
        # forty lines after the contrast that read another `hits`) is not part of the site.
        frontier = {(n, st.lineno) for n in names_in(design) - excluded}
        seen = {n for n, _at in frontier}
        for _hop in range(DESIGN_DEPTH):
            nxt = set()
            for t in body:
                hit = {n for n, at in frontier if n in bound(t) and t.lineno < at}
                if hit:
                    keep |= set(range(t.lineno, header_end(t) + 1))
                    nxt |= {(n, t.lineno) for n in reads_of(t) - excluded - seen}
            frontier = nxt
            seen |= {n for n, _at in nxt}
        runs = []
        for ln in sorted(keep):
            if runs and ln == runs[-1][1] + 1:
                runs[-1][1] = ln
            else:
                runs.append([ln, ln])
        return [tuple(r) for r in runs], sorted(seen)

    def statement_span(node):
        st = stmt_of(node)
        a = st.lineno
        while a > 1 and lines[a - 2].strip().startswith("#"):
            a -= 1
        return a, st.end_lineno

    fits, stmts, called = [], [], set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        name = (fn.attr if isinstance(fn, ast.Attribute) else
                fn.id if isinstance(fn, ast.Name) else "")
        if isinstance(fn, ast.Attribute):
            called.add(fn.attr)
        kws = [k.arg for k in node.keywords if k.arg in FIT_KEYWORDS]
        if kws:
            spans, design_names = fit_spans(node)
            fits.append({"line": node.lineno, "call": name or "<call>", "kws": kws,
                         "spans": spans, "design_names": design_names,
                         # THE CALL'S OTHER ARGUMENTS, as syntax: an answer may not change them
                         "other": ast.dump(ast.Call(
                             func=node.func, args=node.args,
                             keywords=[k for k in node.keywords
                                       if k.arg not in DESIGN_ARGUMENTS]))})
        if isinstance(fn, ast.Attribute) and fn.attr in STATEMENT_CALLS:
            consts = [n for a in list(node.args) + [k.value for k in node.keywords]
                      for n in ast.walk(a)
                      if isinstance(n, ast.Constant) and isinstance(n.value, str)]
            consts.sort(key=lambda n: (n.lineno, n.col_offset))       # as the sentence reads
            words = " ".join(n.value for n in consts)
            hit = [w for w in DESIGN_WORDS if w in words.lower()]
            if hit:
                stmts.append({"line": node.lineno, "call": fn.attr, "words": hit,
                              "digest": hashlib.sha256(ast.dump(node).encode()).hexdigest()[:16],
                              "span": statement_span(node),
                              "text": " ".join(words.split())[:96]})
    fits.sort(key=lambda d: d["line"])
    stmts.sort(key=lambda d: d["line"])
    return fits, stmts, called


def _statements(src):
    """[(first line, binds-or-mutates)] of every statement, a compound one by its header."""
    import ast
    return [(t.lineno, _bound(t, mutated=True)) for t in ast.walk(ast.parse(src))
            if isinstance(t, ast.stmt)]


def _admit(before, after):
    """(ops, sites, refusals, after with before's version) - may `before` become `after` as an
    answer to the worksheet? `refusals` is empty when it may, and says why when it may not.

    - ONE LINE MODEL: both files split on "\n" alone, as `ast` numbers them, and a file carrying
      a character another reader takes as a line break is refused (fix-up 3);
    - every changed line inside ONE span of a site `before` names, an insertion strictly inside
      one - never at its edge (fix-up 2);
    - a fit call's OTHER arguments - everything but `DESIGN_ARGUMENTS` - as they were;
    - an ADDED statement binds only design names the lines it replaces bound: a site line kept
      and `C = dict(C, alpha=0.5)` put after it is a hand edit riding on an answer (fix-up 3).

    The `version` line is the maker's and is not an answer's change.
    """
    import difflib
    refusals = [f"it carries {x}" for x in _line_breaks(after)]
    _vl, vold = _version_node(before)
    norm = _set_version(after, vold) if vold else after
    fits, stmts, _c = _scan(before)
    spans = ([(f"fit:{f['line']}", a, b) for f in fits for a, b in f["spans"]]
             + [(f"statement:{x['line']}", x["span"][0], x["span"][1]) for x in stmts])
    b, a = _lines(before), _lines(norm)
    ops = [o for o in difflib.SequenceMatcher(None, b, a, autojunk=False).get_opcodes()
           if o[0] != "equal"]
    sites, outside = set(), []
    for _tag, i1, i2, _j1, _j2 in ops:
        if i2 > i1:              # lines i1+1..i2 replaced or removed: all inside one span
            hold = [n for n, sa, sb in spans if sa <= i1 + 1 and i2 <= sb]
            where = f"{i1 + 1}-{i2}"
        else:                    # an insertion between lines i1 and i1+1: strictly inside one
            hold = [n for n, sa, sb in spans if sa <= i1 and i1 + 1 <= sb]
            where = f"after {i1}"
        if hold:
            sites.update(hold)
        else:
            outside.append(where)
    if outside:
        refusals.append(f"line(s) {', '.join(outside)} are in no site the worksheet names - an "
                        f"answer is made where the maker asks, or it is a hand edit")
    if refusals or not ops:
        return ops, sorted(sites), refusals, norm
    try:
        fits2, _s2, _c2 = _scan(norm)
        sb_, sa_ = _statements(before), _statements(norm)
    except SyntaxError as e:
        return ops, sorted(sites), [f"it does not parse ({e})"], norm
    was = [(f["call"], f["other"]) for f in fits]
    now = [(f["call"], f["other"]) for f in fits2]
    if was != now:
        changed = sorted({c for c, o in set(was) ^ set(now)}) or ["a fit call"]
        refusals.append(f"it changes {', '.join(changed)} beyond its design arguments "
                        f"({', '.join(DESIGN_ARGUMENTS)}) - the call's other arguments are the "
                        f"method's, not the design's")
    design = {n for f in fits for n in f["design_names"]}
    for _tag, i1, i2, j1, j2 in ops:
        old = [bset for ln, bset in sb_ if i1 + 1 <= ln <= i2]
        new = [bset for ln, bset in sa_ if j1 + 1 <= ln <= j2]
        if len(new) <= len(old):
            continue                 # statements changed or removed, none added
        pool = list(new)
        for o in old:                # each kept statement takes the new one most like it
            pool.pop(max(range(len(pool)), key=lambda k: len(pool[k] & o)))
        allowed = set().union(*old) & design if old else set()
        for added in pool:
            extra = sorted(added - allowed)
            if extra:
                refusals.append(f"a statement added at line {j1 + 1} binds {', '.join(extra)}, "
                                f"which the lines it replaces did not bind as design names")
    return ops, sorted(sites), refusals, norm


def _git_show(root, commit, relpath):
    """(text, how) of `relpath` at `commit` in the repository at `root`, or (None, why).

    The `git` binary first; where there is none - the cluster's compute nodes have none - the
    repository's own object store is read directly (loose objects, and packs with their deltas),
    so a checkout that carries its history can always be asked. A checkout without its history
    cannot, and says so: the base of a design record is then not established, and nothing passes.
    """
    import os
    import subprocess
    # THE REPOSITORY AT `root`, AND NO OTHER: git exports GIT_INDEX_FILE (relative), and may
    # export GIT_DIR, to whatever runs under a hook - the commit gate runs the suite under one.
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    try:
        r = subprocess.run(["git", "-C", str(root), "show", f"{commit}:{relpath}"],
                           capture_output=True, timeout=60, env=env)
        if r.returncode == 0:
            try:
                return r.stdout.decode("utf-8"), f"git show {commit}:{relpath}"
            except UnicodeDecodeError as e:
                return None, f"git show {commit}:{relpath} is not UTF-8 text ({e})"
        why = r.stderr.decode("utf-8", "replace").strip().splitlines()[-1:] or ["git failed"]
        git_says = f"git show {commit}:{relpath}: {why[0]}"
    except (OSError, subprocess.SubprocessError) as e:
        git_says = f"no git here ({type(e).__name__})"
    try:
        return _ObjectStore(root).show(commit, relpath), (f"{commit}:{relpath}, read from the "
                                                          f"repository's object store")
    except (OSError, ValueError, KeyError, IndexError) as e:
        return None, f"{git_says}; and the object store could not give {commit}:{relpath}: {e}"


class _ObjectStore:
    """Read-only access to a git object store with nothing but the standard library."""

    def __init__(self, root):
        g = Path(root) / ".git"
        if g.is_file():                                   # a linked worktree, or a submodule
            g = (Path(root) / g.read_text().split("gitdir:", 1)[1].strip()).resolve()
        if (g / "commondir").is_file():
            g = (g / (g / "commondir").read_text().strip()).resolve()
        self.objects = g / "objects"
        if not self.objects.is_dir():
            raise ValueError(f"no object store under {root}")
        # A CLONE MADE WITH --reference OR --shared keeps its objects in another store, named in
        # `objects/info/alternates` one directory per line.
        self.stores = [self.objects]
        alt = self.objects / "info" / "alternates"
        if alt.is_file():
            for row in alt.read_text(encoding="utf-8").split("\n"):
                row = row.strip()
                if row and not row.startswith("#"):
                    d = (self.objects / row).resolve()
                    if d.is_dir() and d not in self.stores:
                        self.stores.append(d)
        self.packs = []
        for store in self.stores:
            for idx in sorted((store / "pack").glob("*.idx")):
                self.packs.append((idx.with_suffix(".pack"), self._index(idx)))

    @staticmethod
    def _index(idx):
        import struct
        b = idx.read_bytes()
        if b[:4] != b"\377tOc" or struct.unpack(">I", b[4:8])[0] != 2:
            raise ValueError(f"{idx.name}: not a version-2 pack index")
        n = struct.unpack(">I", b[8 + 255 * 4:8 + 256 * 4])[0]
        shas = 8 + 256 * 4
        offs = shas + 20 * n + 4 * n
        large = offs + 4 * n
        out = {}
        for i in range(n):
            sha = b[shas + 20 * i:shas + 20 * (i + 1)].hex()
            o = struct.unpack(">I", b[offs + 4 * i:offs + 4 * (i + 1)])[0]
            if o & 0x80000000:
                k = o & 0x7FFFFFFF
                o = struct.unpack(">Q", b[large + 8 * k:large + 8 * (k + 1)])[0]
            out[sha] = o
        return out

    def resolve(self, ref):
        ref = str(ref).lower()
        if not re.fullmatch(r"[0-9a-f]{4,40}", ref):
            raise KeyError(f"{ref!r} is not a commit's hash")
        found = {sha for _p, ix in self.packs for sha in ix if sha.startswith(ref)}
        for store in self.stores:
            d = store / ref[:2]
            if d.is_dir():
                found |= {ref[:2] + f.name for f in d.iterdir()
                          if (ref[:2] + f.name).startswith(ref)}
        if len(found) != 1:
            raise KeyError(f"{ref} names {len(found)} object(s) here")
        return found.pop()

    def read(self, sha):
        import zlib
        for store in self.stores:
            loose = store / sha[:2] / sha[2:]
            if loose.is_file():
                raw = zlib.decompress(loose.read_bytes())
                head, _, body = raw.partition(b"\0")
                return ({b"commit": 1, b"tree": 2, b"blob": 3, b"tag": 4}[head.split(b" ")[0]],
                        body)
        for pack, ix in self.packs:
            if sha in ix:
                return self._packed(pack, ix[sha])
        raise KeyError(f"object {sha} is not in the store")

    def _packed(self, pack, offset):
        import zlib
        with open(pack, "rb") as fh:
            fh.seek(offset)
            c = fh.read(1)[0]
            typ = (c >> 4) & 7
            while c & 0x80:
                c = fh.read(1)[0]
            base = None
            if typ == 6:                                  # a delta against an earlier offset
                c = fh.read(1)[0]
                back = c & 0x7F
                while c & 0x80:
                    c = fh.read(1)[0]
                    back = ((back + 1) << 7) | (c & 0x7F)
                base = self._packed(pack, offset - back)
            elif typ == 7:                                # a delta against a named object
                base = self.read(fh.read(20).hex())
            d, out = zlib.decompressobj(), b""
            while not d.eof:
                chunk = fh.read(65536)
                if not chunk:
                    raise ValueError("a truncated pack")
                out += d.decompress(chunk)
        if base is None:
            return typ, out
        return base[0], self._undelta(base[1], out)

    @staticmethod
    def _undelta(src, delta):
        i = 0

        def varint():
            nonlocal i
            v = shift = 0
            while True:
                c = delta[i]
                i += 1
                v |= (c & 0x7F) << shift
                shift += 7
                if not c & 0x80:
                    return v
        varint()
        varint()
        out = bytearray()
        while i < len(delta):
            op = delta[i]
            i += 1
            if op & 0x80:
                off = size = 0
                for k in range(4):
                    if op & (1 << k):
                        off |= delta[i] << (8 * k)
                        i += 1
                for k in range(3):
                    if op & (1 << (4 + k)):
                        size |= delta[i] << (8 * k)
                        i += 1
                out += src[off:off + (size or 0x10000)]
            else:
                out += delta[i:i + op]
                i += op
        return bytes(out)

    def show(self, commit, relpath):
        typ, body = self.read(self.resolve(commit))
        while typ == 4:                                   # an annotated tag
            typ, body = self.read(body.split(b"\n", 1)[0].split()[1].decode())
        if typ != 1:
            raise ValueError(f"{commit} is not a commit")
        sha = body.split(b"\n", 1)[0].split()[1].decode()
        for part in str(relpath).split("/"):
            typ, tree = self.read(sha)
            if typ != 2:
                raise ValueError(f"{part}: not in a tree")
            j, found = 0, None
            while j < len(tree):
                sp = tree.index(b" ", j)
                nul = tree.index(b"\0", sp)
                if tree[sp + 1:nul].decode() == part:
                    found = tree[nul + 1:nul + 21].hex()
                    break
                j = nul + 21
            if found is None:
                raise KeyError(f"{relpath} is not in {commit}")
            sha = found
        typ, blob = self.read(sha)
        if typ != 3:
            raise ValueError(f"{relpath} at {commit} is not a file")
        return blob.decode("utf-8")


def _spent_commit(root, name):
    """The commit `name`'s record is anchored at, as DEVPOINTS declares it - never as the record
    says, so the record cannot move its own anchor. A spent plugin's is the commit its blind
    record was taken at (`rules.held_out.spent`); the plugin that was never held out is anchored
    at the commit its record starts from (`rules.end_to_end.anchor`, W035). A held-out plugin
    has neither, so nothing can record an answer for it before its own migration."""
    for want in (["rules", "held_out", "spent"], ["rules", "end_to_end", "anchor"]):
        v = _devpoints_value(root, want, name)
        if v:
            return v
    return None


def _devpoints_value(root, want, name):
    """The scalar at `want` -> `name` in DEVPOINTS.yaml, or None."""
    f = Path(root) / "DEVPOINTS.yaml"
    if not f.is_file():
        return None
    # READ AS TEXT, as every suite here reads DEVPOINTS (the host depends on numpy and pandas
    # only), and by its path: e.g. `rules:` -> `held_out:` -> `spent:` -> `<name>: <commit>`.
    path = []
    for raw in f.read_text(encoding="utf-8").split("\n"):
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip() or line.lstrip().startswith("- "):
            continue
        ind = len(line) - len(line.lstrip())
        while path and path[-1][0] >= ind:
            path.pop()
        k, _, v = line.strip().partition(":")
        k, v = k.strip(), v.strip().strip("'\"")
        if [p for _i, p in path] == want and k == name:
            return v or None
        if not v:
            path.append((ind, k))
    return None


def _outside_declaration(src):
    """`src` with its `PLUGIN = {...}` lines folded into one placeholder: its CODE."""
    span = _declaration(src)
    if span is None:
        return src
    lines = _lines(src)
    return "".join(lines[:span[0] - 1]) + "PLUGIN = ...  # the declaration\n" + \
        "".join(lines[span[1]:])


def _declaration_literal(src):
    """None when the file's declaration is one the host loads - ONE binding of `PLUGIN`, a
    top-level `PLUGIN = {...}` alone on its lines, a pure literal dict - or why it is not. The
    host's own reader (`kernels.read_declaration`), so the check and the host read one statement
    (W032, GAP-C72, GAP-C73); it never raises."""
    from .kernels import read_declaration
    return read_declaration(src)[2]


def _declaration(src):
    """(first line, last line) of the `PLUGIN = {...}` assignment, or None: the declaration, which
    the maker's verb `sch dev edit` changes and nothing else does. None too when the file has no
    declaration standing alone on its lines (`kernels.declaration_node`): only lines that hold the
    assignment and nothing else are ever folded or swapped as "the declaration"."""
    from .kernels import declaration_node
    _tree, node, why = declaration_node(src)
    return None if (why or node is None) else (node.lineno, node.end_lineno)


def _lone_declaration(text):
    """None when `text` is ONE declaration and nothing else - what a record's `after_declaration`
    must be, since it is swapped into the plugin as its declaration's lines - or why it is not."""
    from .kernels import declaration_node
    why = _declaration_literal(text)
    if why:
        return why
    tree, _node, _w = declaration_node(text)
    if len(tree.body) != 1:
        return f"it holds {len(tree.body)} statements, not the declaration alone"
    if not str(text).endswith("\n"):
        return "it does not end its last line"
    return None


def _swap_declaration(src, declaration):
    """`src` with its `PLUGIN = {...}` lines replaced by `declaration`'s text."""
    span = _declaration(src)
    if span is None:
        return src
    lines = _lines(src)
    return "".join(lines[:span[0] - 1]) + declaration + "".join(lines[span[1]:])


def _declaration_text(src):
    span = _declaration(src)
    return "" if span is None else "".join(_lines(src)[span[0] - 1:span[1]])


def _reverse_diff(diff):
    """The inverse of a unified diff: what turns its `after` back into its `before`."""
    out = []
    for row in _lines(diff):
        m = re.match(r"@@ -(\d+(?:,\d+)?) \+(\d+(?:,\d+)?) @@(.*)", row, re.S)
        if m:
            out.append(f"@@ -{m.group(2)} +{m.group(1)} @@{m.group(3)}")
        elif row.startswith("+") and not row.startswith("+++"):
            out.append("-" + row[1:])
        elif row.startswith("-") and not row.startswith("---"):
            out.append("+" + row[1:])
        else:
            out.append(row)
    return "".join(out)


def design_record_check(kernel, root=None):
    """(ok, sentence) - does the worksheet's record account for the plugin as it ships?

    THE RECORD VERIFIES ITSELF WHEREVER IT IS READ (W013's verifier, fix-ups 4 and 5), from the
    repository alone:
      1. the declaration is a pure literal - `ast.literal_eval` - so no run-time code hides in it;
      2. the shipped file, its declaration set back to the last answer's, is the file the last
         answer made; every recorded diff is then undone, last first, each landing exactly on the
         file it was made against, and admitted again, forward, at the sites it records;
      3. THE CHAIN'S END IS ANCHORED: the first answer's `before` - or, with no answer yet, the
         shipped file - is, outside its declaration, the plugin at the commit its blind record was
         taken at, as DEVPOINTS `rules.held_out.spent` declares it and git keeps it. A record
         rewritten to start from a doctored file, or a hand edit before the first answer, does not
         meet it. Where that commit cannot be read the base is not established, and this fails.
    The declaration is the maker's verb's to change after an answer; it is compared nowhere but
    in step 1 - and step 1 holds it to the host's own reader (`kernels.read_declaration`): one
    binding of `PLUGIN`, alone on its lines, a pure literal, in the shipped file and in every file
    of the chain (W032).

    IT FAILS CLOSED, NEVER WITH A TRACEBACK. The record is a file anyone can edit, so whatever it
    holds - a diff that is not text, sites that are not a list - is a sentence and a failure.
    """
    try:
        return _design_record_check(kernel, root)
    except Exception as e:                                       # noqa: BLE001 - fail closed
        return False, (f"the design record of {kernel.name} cannot be checked "
                       f"({type(e).__name__}: {e})")


def _design_record_check(kernel, root):
    path = Path(kernel.path)
    root = Path(root) if root else path.parent.parent
    try:
        shipped = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return False, f"kernels/{path.name} cannot be read as UTF-8 text ({type(e).__name__}: {e})"
    # THE DECLARATION AS THE HOST READS IT, OR NOTHING PASSES (W032): one binding of `PLUGIN`, a
    # top-level `PLUGIN = {...}` alone on its lines, a pure literal. Every file of the chain below
    # is held to the same, and so is each declaration the record swaps in: the lines this check
    # folds and swaps as "the declaration" are then lines that hold no code.
    bad = _declaration_literal(shipped)
    if bad:
        return False, f"kernels/{path.name}: {bad}"
    rec = _read_record(kernel)
    if rec.get("unreadable"):
        return False, f"the record {rec['unreadable']} does not parse"
    answers = rec.get("answers") or []
    if not isinstance(answers, list) or not all(isinstance(a, dict) for a in answers):
        return False, (f"the record {design_record_path(kernel).name}'s answers are not a list "
                       f"of entries")
    anchor = _spent_commit(root, kernel.name)
    if not answers and anchor is None:
        return True, ("no answer recorded, and not spent: DEVPOINTS names no blind-record commit "
                      f"for {kernel.name}")
    if anchor is None:
        return False, (f"a record with no anchor: DEVPOINTS `rules.held_out.spent` names no "
                       f"blind-record commit for {kernel.name}")
    cur = shipped
    if answers:
        last = answers[-1]
        if _sha(cur) != last.get("after") and last.get("after_declaration"):
            why = _lone_declaration(last["after_declaration"])
            if why:
                return False, (f"answer {last.get('n')}'s recorded declaration is not one "
                               f"declaration alone: {why}")
            cur = _swap_declaration(shipped, last["after_declaration"])
        if _sha(cur) != last.get("after"):
            return False, (f"kernels/{path.name} is not the file its last recorded answer "
                           f"({last.get('n')}) made, outside its declaration: changed since by "
                           f"hand, or by an answer the worksheet did not record")
        for ans in reversed(answers):
            if _sha(cur) != ans.get("after"):
                return False, f"answer {ans.get('n')} did not make the file the next answer met"
            why = _declaration_literal(cur)
            if why:
                return False, f"the file answer {ans.get('n')} made: {why}"
            if ans.get("kind") == "prose":
                # A PROSE ANSWER CARRIES NO TEXT THE PLUGIN NO LONGER CARRIES (W035): its file
                # before is read back from git at the commit it was made on, its recorded diff
                # must turn that file into this one, and the prose rule admits the change again.
                prev, how = _git_show(root, str(ans.get("made_on") or ""), f"kernels/{path.name}")
                if prev is None:
                    return False, (f"answer {ans.get('n')} (prose): the file it was made on "
                                   f"cannot be read ({how})")
                if _sha(prev) != ans.get("before"):
                    return False, (f"answer {ans.get('n')} (prose): the file at its commit is not "
                                   f"the file it records it was made on")
                try:
                    redo = _apply_unified(prev, str(ans.get("diff") or ""))
                except ValueError as e:
                    return False, f"answer {ans.get('n')} (prose): its diff does not apply ({e})"
                if redo != cur:
                    return False, (f"answer {ans.get('n')} (prose): its diff does not make the "
                                   f"file the record says it made")
                why = "; ".join(prose_refusals(prev, cur)) or (
                    "it changes nothing" if prev == cur else "")
                if why:
                    return False, f"answer {ans.get('n')} is not admissible as prose: {why}"
                cur = prev
                continue
            try:
                prev = _apply_unified(cur, _reverse_diff(str(ans.get("diff") or "")))
            except ValueError as e:
                return False, f"answer {ans.get('n')} does not undo from the shipped file: {e}"
            if _sha(prev) != ans.get("before"):
                return False, (f"answer {ans.get('n')} undone is not the file it records it was "
                               f"made on")
            why = _declaration_literal(prev)
            if why:
                return False, f"the file answer {ans.get('n')} was made on: {why}"
            try:
                _ops, sites, refusals, _n = _admit(prev, cur)
            except SyntaxError as e:
                return False, f"answer {ans.get('n')}: a file in the record does not parse ({e})"
            if refusals or not sites or sites != sorted(ans.get("sites") or []):
                return False, (f"answer {ans.get('n')} is not admissible as recorded: "
                               + ("; ".join(refusals) if refusals else
                                  f"it touches {sites or 'no site'}, the record says "
                                  f"{ans.get('sites')}"))
            cur = prev
    base, how = _git_show(root, anchor, f"kernels/{path.name}")
    if base is None:
        return False, (f"the base cannot be established: the plugin at its blind-record commit "
                       f"{anchor} could not be read ({how})")
    why = _declaration_literal(base)
    if why:
        return False, f"the plugin at its blind-record commit {anchor}: {why}"
    try:
        same = _outside_declaration(cur) == _outside_declaration(base)
    except SyntaxError as e:
        return False, f"the base or the record's first file does not parse ({e})"
    if not same:
        return False, ((f"answer 1 was made on a file whose code differs from the plugin at its "
                        f"blind-record commit {anchor}, outside the declaration")
                       if answers else
                       (f"kernels/{path.name} has changed outside its declaration since its "
                        f"blind-record commit {anchor}, and no answer records it"))
    if not answers:
        return True, (f"no answer recorded, and outside its declaration kernels/{path.name} is the "
                      f"plugin at its blind-record commit {anchor}")
    return True, (f"{len(answers)} answer(s) undo from the shipped file to the plugin at its "
                  f"blind-record commit {anchor}, and each is admitted again at the sites it "
                  f"records")


def design_sites(kernel, root=None):
    """{design_aware, sites, statements, missing, owes} - where a plugin fits a model, where it
    STATES what was contrasted or modelled, and what it owes the host at each.

    THE HOST DECIDES THE DESIGN AND THE PLUGIN FITS IT (GAP-039, GAP-040). A plugin that chooses
    a contrast's reference itself chooses it by whatever it reached for - `sorted(levels)[0]`,
    a formula library's alphabetical default - and on a design whose control sorts last its
    table runs the other way from every panel on the page; a plugin that builds its formula from
    the terms alone fits without the covariates the user named. Neither failure raises.

    AND WHAT A PLUGIN SAYS ABOUT THE DESIGN IS A CLAIM ABOUT THE HOST'S DECISION (GAP-C47). A
    caveat that an interaction "is not contrasted", printed beside the row contrasting it, is as
    wrong as a reversed sign and as silent. Every runtime statement carrying a design word is
    named, and owes until it is answered through the worksheet - changed (`--answer`) or
    confirmed true as it stands (`--confirm`) - each recorded by the digest of its syntax.

    READ FROM THE SOURCE, NOT FROM A RUN, so it is a build question. It cannot see a plugin that
    asks the host and then reorders anyway; the two-shape fixture, whose control sorts last on
    one shape, is the check that can (`agree` in the harness's ladder).

    IT NEVER RAISES (W032, GAP-C73): a declaration or a record this cannot read is an owe with
    its sentence, so the stage that runs it - and a job's first step - fails by name.
    """
    try:
        return _design_sites(kernel, root)
    except Exception as e:                                       # noqa: BLE001 - fail closed
        return {"design_aware": False, "sites": [], "statements": [], "takes": [],
                "missing": [("declaration", f"the design stage cannot read this plugin "
                                            f"({type(e).__name__}: {e})")], "owes": True}


def _design_sites(kernel, root):
    spec = kernel.spec or {}
    inj = spec.get("inject") or {}
    takes = (set(inj.get("required") or []) | set(inj.get("optional") or [])
             if isinstance(inj, dict) else set())
    out = {"design_aware": bool(takes & {"design", "contrast"}), "sites": [], "statements": [],
           "missing": [], "owes": False, "takes": sorted(takes)}
    path = Path(kernel.path)
    # A DECLARATION THAT DOES NOT LOAD IS NOT "NOT DESIGN-AWARE" (fix-up 5): the host reads an
    # empty spec from a `PLUGIN` that is not a pure literal, and this read "nothing to answer"
    # over a plugin whose import runs whatever the declaration hides. Read by the host's own
    # reader, so a second binding or code on the declaration's lines owes here too (W032).
    if path.is_file() and path.suffix == ".py":
        try:
            why = _declaration_literal(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError) as e:
            why = f"the file cannot be read as UTF-8 text ({type(e).__name__}: {e})"
        why = why or getattr(kernel, "declaration_error", None)
        if why or not spec:
            out["missing"].append(("declaration", why or "the host loaded no declaration"))
            out["owes"] = True
            return out
        # THE RECORD IS CHECKED FOR EVERY PLUGIN, DESIGN-AWARE OR NOT (W032). It was reached only
        # past "design-aware", so a declaration edited to drop `design` and `contrast` from
        # `inject` - or one the host read as empty - left this stage `ok` over any hand edit.
        # A plugin that is neither spent nor recorded passes it at once ("not spent").
        out["record"] = design_record_check(kernel, root=root)
    if not out["design_aware"] or not path.is_file():
        if not out.get("record", (True, ""))[0]:
            out["missing"].append(("record", out["record"][1]))
        out["owes"] = bool(out["missing"])
        return out
    try:
        fits, stmts, called = _scan(path.read_text(encoding="utf-8"))
    except SyntaxError as e:                                              # pragma: no cover
        out["missing"].append(("parse", f"the source does not parse: {e}"))
        out["owes"] = True
        return out
    out["sites"] = [(f["line"], f["call"], f["kws"]) for f in fits]
    out["spans"] = {f["line"]: f["spans"] for f in fits}
    answered = _read_record(kernel)["statements"]
    for s in stmts:
        s["answered"] = answered.get(s["digest"])
    out["statements"] = stmts
    if fits:
        for acc, what in HOST_MODEL.items():
            if acc not in called:
                out["missing"].append((acc, what))
        if "covariates" not in takes:
            out["missing"].append(("covariates", "the covariates the user named: `inject` names "
                                                 "no `covariates`, so none can be handed to it"))
    for s in stmts:
        if not s["answered"]:
            out["missing"].append((f"statement:{s['line']}", STATEMENT_OWES))
    if not out.get("record", (True, ""))[0]:
        out["missing"].append(("record", out["record"][1]))
    out["owes"] = bool(out["missing"])
    return out


def design_report(kernel, log=print, root=None):
    """Print `design_sites` as a worksheet. Returns 0 when nothing is owed, 1 otherwise."""
    d = design_sites(kernel, root=root)
    rel = Path(kernel.path).name
    if any(m == "declaration" for m, _w in d["missing"]):
        log(f"  OWES {kernel.name:<12} its declaration does not load: "
            + "; ".join(w for m, w in d["missing"] if m == "declaration"))
        return 1
    if not d["design_aware"]:
        rec = [w for m, w in d["missing"] if m == "record"]
        if rec:
            log(f"  OWES {kernel.name:<12} not design-aware (inject names neither `design` nor "
                f"`contrast`), and its design record (kernels/{design_record_path(kernel).name}) "
                f"does not account for it as it ships: " + "; ".join(rec))
            return 1
        log(f"  ok   {kernel.name:<12} not design-aware (inject names neither `design` nor "
            f"`contrast`): nothing to answer")
        return 0
    if not d["sites"] and not d["statements"]:
        log(f"  ok   {kernel.name:<12} design-aware, and no call here fits a model, takes a "
            f"contrast or states one: nothing to answer")
        return 0
    log(f"  {'OWES' if d['owes'] else 'ok  '} {kernel.name:<12} design-aware; "
        f"{len(d['sites'])} site(s) where a model is built or a contrast taken:")
    for line, name, kws in d["sites"]:
        sp = ", ".join(f"{a}" if a == b else f"{a}-{b}"
                       for a, b in d.get("spans", {}).get(line, []))
        log(f"         kernels/{rel}:{line}  {name}({', '.join(k + '=' for k in kws)}...)"
            + (f"  its site: lines {sp}" if sp else ""))
    log(f"       {len(d['statements'])} statement(s) of what was contrasted or modelled:")
    for s in d["statements"]:
        a = s.get("answered")
        state = (f"answered ({a.get('how')}: {str(a.get('why') or '')[:60]})" if a else "OWES")
        log(f"         kernels/{rel}:{s['line']}  ctx.{s['call']}(...)  [{', '.join(s['words'])}]"
            f"  {state}")
        log(f"             \"{s['text']}\"")
    if not d["owes"]:
        log("       it takes the frame and the order from the host, declares `covariates`, and "
            "every statement is answered")
        return 0
    log("       WHAT IT OWES THE HOST - answer each where it is named:")
    owed = [acc.split(":", 1)[1] for acc, _w in d["missing"] if acc.startswith("statement:")]
    for acc, what in d["missing"]:
        if acc == "covariates":
            log(f"         inject `covariates`: {what}. The maker's verb: "
                f"sch dev edit --root . --point kernel --name {kernel.name} "
                f"--list-add inject.optional=\"covariates\"")
        elif acc == "record":
            log(f"         the record (kernels/{design_record_path(kernel).name}): {what}")
        elif not acc.startswith("statement:"):
            log(f"         ctx.{acc}(...): {what}")
    if owed:
        log(f"         the statements at line(s) {', '.join(owed)}: {STATEMENT_OWES}")
    log(f"       HOW AN ANSWER IS MADE, and recorded in kernels/{design_record_path(kernel).name}:"
        f" change the file and hand it in whole - `scprofile design {kernel.name} --answer <file>"
        f" --why \"...\"` applies it only inside a site above - a fit call's statement and the"
        f" lines defining what its design arguments read, or a statement and its comment - and"
        f" records the diff - or,"
        f" for a statement true as it stands, `scprofile design {kernel.name} --confirm <line> "
        f"--why \"...\"`.")
    return 1


def _version_node(src):
    """(line, current value) of the PLUGIN dict's `version`, or (None, None) - read from the
    declaration the host reads (`kernels.declaration_node`), never from a second binding. A file
    that does not parse raises SyntaxError, as `ast.parse` did here before."""
    import ast
    from .kernels import declaration_node
    tree, n, why = declaration_node(src)
    if tree is None:
        raise SyntaxError(why)
    if n is not None and not why and isinstance(n.value, ast.Dict):
        for k, v in zip(n.value.keys, n.value.values):
            if isinstance(k, ast.Constant) and k.value == "version" \
                    and isinstance(v, ast.Constant):
                return v.lineno, str(v.value)
    return None, None


def _set_version(src, value):
    line, old = _version_node(src)
    if line is None:
        return src
    lines = _lines(src)
    lines[line - 1] = re.sub(r"""(["']version["']\s*:\s*)(["'])[^"']*(["'])""",
                             lambda m: m.group(1) + m.group(2) + value + m.group(3),
                             lines[line - 1], count=1)
    return "".join(lines)


def _bump(v):
    parts = (str(v or "0.0.0").split(".") + ["0", "0", "0"])[:3]
    try:
        return f"{int(parts[0])}.{int(parts[1]) + 1}.0"
    except ValueError:
        return str(v)


def design_answer(kernel, proposed, why, *, as_version=None, log=print, root=None):
    """Apply an author's answer to the design worksheet, by the sites it names, and record it.

    `proposed` is the whole plugin file as the author would have it. Every line it changes must
    lie inside a site the worksheet names - a fit site's loop, or a statement and the comment
    above it - or the answer is refused with the lines named: an answer is where the maker asked,
    or it is a hand edit. The `version` line is the maker's, as with `sch dev edit`: the author's
    copy keeps it, and the command raises it (the minor, or `as_version`). Returns 0 or 1.
    """
    import difflib
    if not str(why or "").strip():
        log("  refused: --why is the answer's reason, and a recorded answer carries one")
        return 1
    path = Path(kernel.path)
    # THE FIRST ANSWER IS MADE ON THE PLUGIN AS IT WAS BLIND (fix-up 5): the record's chain must
    # end at a commit DEVPOINTS names, and a file changed outside its declaration since then is
    # refused before anything is admitted - a hand edit does not become the base of the record.
    if _spent_commit(Path(root) if root else path.parent.parent, kernel.name) is None:
        log(f"  refused: DEVPOINTS `rules.held_out.spent` names no blind-record commit for "
            f"{kernel.name}, so a record of its answers would have no anchor")
        return 1
    ok, why_not = design_record_check(kernel, root=root)
    if not ok:
        log(f"  refused: the record does not meet kernels/{path.name} as it stands - {why_not}")
        return 1
    before = path.read_text(encoding="utf-8")
    # READ AS IT IS ON DISK: universal newlines would turn a carriage return into a line break
    # before the admission could see it (fix-up 3).
    with open(proposed, encoding="utf-8", newline="") as fh:
        proposal = fh.read()
    try:
        ops, sites, refusals, text = _admit(before, proposal)
    except SyntaxError as e:
        log(f"  refused: a file does not parse ({e})")
        return 1
    if refusals:
        log(f"  refused: kernels/{path.name} as handed in - " + "; ".join(refusals))
        return 1
    if not ops:
        log("  refused: the file handed in is the file as it stands - nothing to answer")
        return 1
    if not sites:
        log("  refused: the answer names no site of the worksheet")
        return 1
    _vl, vold = _version_node(before)
    new_version = as_version or _bump(vold)
    after = _set_version(text, new_version) if vold else text
    # AN ANSWER LEAVES A DECLARATION THE HOST LOADS (W032): a `global PLUGIN` added inside a site
    # binds nothing the admission counts, and would rebind the module's declaration at run time.
    why_decl = _declaration_literal(after)
    if why_decl:
        log(f"  refused: the answer leaves kernels/{path.name} with a declaration the host cannot "
            f"load - {why_decl}")
        return 1
    try:
        _f2, stmts2, _c2 = _scan(after)
    except SyntaxError as e:
        log(f"  refused: the answer does not parse ({e})")
        return 1
    rec = _read_record(kernel)
    n = len(rec["answers"]) + 1
    touched = [(j1 + 1, max(j2, j1 + 1)) for _t, _i1, _i2, j1, j2 in ops]
    hit = [x for x in stmts2 if any(not (hi < x["span"][0] or lo > x["span"][1])
                                    for lo, hi in touched)]
    for x in hit:
        rec["statements"][x["digest"]] = {"site": f"statement:{x['line']}",
                                          "how": f"answer {n}", "why": str(why)}
    diff = "".join(difflib.unified_diff(_lines(before), _lines(after),
                                        f"a/kernels/{path.name}", f"b/kernels/{path.name}", n=3))
    rec["answers"].append({"n": n, "why": str(why), "sites": sites, "version": new_version,
                           "before": _sha(before), "after": _sha(after), "diff": diff,
                           # THE DECLARATION IT LEFT, so the record still meets the plugin after
                           # the maker's verb edits the declaration (`design_record_check`)
                           "after_declaration": _declaration_text(after)})
    path.write_text(after, encoding="utf-8")
    _write_record(kernel, rec)
    log(f"  answer {n} applied to kernels/{path.name} at {', '.join(sites)}; version {vold} -> "
        f"{new_version}; recorded in kernels/{design_record_path(kernel).name}")
    log(f"  next: scprofile validate {kernel.name}, then scprofile design {kernel.name}")
    return 0


def design_confirm(kernel, line, why, log=print):
    """Record a statement as true as it stands, by the digest of its syntax. Returns 0 or 1."""
    if not str(why or "").strip():
        log("  refused: --why is the confirmation's reason, and a recorded answer carries one")
        return 1
    _f, stmts, _c = _scan(Path(kernel.path).read_text(encoding="utf-8"))
    s = next((x for x in stmts if x["line"] == int(line)), None)
    if s is None:
        log(f"  refused: no statement the worksheet names starts at line {line} "
            f"(it names {', '.join(str(x['line']) for x in stmts) or 'none'})")
        return 1
    rec = _read_record(kernel)
    rec["statements"][s["digest"]] = {"site": f"statement:{s['line']}", "how": "confirmed",
                                      "why": str(why)}
    _write_record(kernel, rec)
    log(f"  statement:{s['line']} confirmed as it stands; recorded by its digest {s['digest']}")
    return 0


def _apply_unified(text, diff):
    """`text` with one recorded unified diff applied, exactly: every context and removed line
    must be the line it names, or ValueError says where it is not."""
    src = _lines(text)
    lines = _lines(diff)
    out, i, k = [], 0, 0
    while k < len(lines) and not lines[k].startswith("@@"):
        k += 1
    while k < len(lines):
        m = re.match(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", lines[k])
        if not m:
            raise ValueError(f"not a hunk header: {lines[k]!r}")
        k += 1
        start = int(m.group(1)) - 1 if int(m.group(2) or 1) > 0 else int(m.group(1))
        if start < i:
            raise ValueError("hunks out of order")
        out.extend(src[i:start])
        i = start
        while k < len(lines) and not lines[k].startswith("@@"):
            row = lines[k]
            k += 1
            if row.startswith("\\"):
                continue
            tag, body = row[:1], row[1:]
            if tag in (" ", "-"):
                if i >= len(src) or not (src[i] == body or (body.startswith(REDACTED)
                                                            and body.strip() == REDACTED + _sha(src[i]))):
                    raise ValueError(f"line {i + 1} is not the line the answer was made against")
                if tag == " ":
                    out.append(src[i])
                i += 1
            elif tag == "+":
                out.append(body)
    out.extend(src[i:])
    return "".join(out)


def design_replay(kernel, target, log=print):
    """Apply every recorded answer, in order, to `target` - a copy of the plugin rebuilt from its
    base by the maker's verb calls. Each must meet the file it was made against (its `before`
    digest) and leave the file it made (its `after` digest). Returns 0 or 1."""
    rec = _read_record(kernel)
    t = Path(target)
    text = t.read_text(encoding="utf-8")
    if not rec["answers"]:
        log(f"  nothing to replay: kernels/{design_record_path(kernel).name} records no answer")
        return 1
    for ans in rec["answers"]:
        if _sha(text) != ans["before"]:
            log(f"  answer {ans['n']}: the target is not the file it was made against "
                f"({_sha(text)} != {ans['before']})")
            return 1
        try:
            new = _apply_unified(text, ans["diff"])
        except ValueError as e:
            log(f"  answer {ans['n']}: {e}")
            return 1
        # THE RECORD IS NOT TRUSTED: each diff is admitted again against the sites of the file
        # it meets, as `--answer` admitted it, so a record edited to carry a change outside every
        # site does not replay (W013's verifier, fix-up 2). A prose answer, by the prose rule.
        if ans.get("kind") == "prose":
            refusals = prose_refusals(text, new)
            if refusals:
                log(f"  answer {ans['n']}: refused on replay - " + "; ".join(refusals))
                return 1
            text = new
            if _sha(text) != ans["after"]:
                log(f"  answer {ans['n']}: applied, and the result is not the file it made")
                return 1
            log(f"  answer {ans['n']} replayed (prose) -> {ans['after']}")
            continue
        _ops, sites, refusals, _n = _admit(text, new)
        if refusals or not sites or sites != sorted(ans.get("sites") or []):
            log(f"  answer {ans['n']}: refused on replay - "
                + ("; ".join(refusals) if refusals else
                   f"it names {sites or 'no site'}, the record says {ans.get('sites')}"))
            return 1
        text = new
        if _sha(text) != ans["after"]:
            log(f"  answer {ans['n']}: applied, and the result is not the file it made")
            return 1
        log(f"  answer {ans['n']} replayed at {', '.join(ans['sites'])} -> {ans['after']}")
    t.write_text(text, encoding="utf-8")
    log(f"  {len(rec['answers'])} answer(s) replayed into {t}")
    return 0


# ------------------------------------------------------------------------- prose (W035, GAP-C80)
# A PLUGIN'S PROSE IS EDITED THROUGH THE MAKER TOO. A cohort's measured value sat in a comment of
# cellchat's R script, and no verb could reach it: `sch dev edit` edits the declaration by span,
# `design --answer` the sites the worksheet names, and a comment is neither - so the only way left
# was a hand edit, which the round's first rule forbids. By the rule of 2026-09-14 ("anything in a
# plugin that cannot be edited easily from the maker is a suite or maker design defect") the
# defect was the maker's. `prose_answer` is the verb: what it may change is PROSE, and everything
# else is CODE and refused, with its line.

#: An embedded script, as the suite reads one (tests/subject.py): a string of at least this many
#: characters holding `library(` and `<-` or `function(`.
R_SCRIPT_MIN = 200

#: A splice marker: text the plugin's own Python replaces in a script (`.replace("__R_CAP__", ...)`).
#: It is code wherever it sits, a comment included, so no prose edit may change one.
SPLICE_MARKER = re.compile(r"__[A-Za-z0-9]+(?:_[A-Za-z0-9]+)*__")

_R_RAW = re.compile(r"""[rR](["'])(-*)([(\[{])""")
_R_CLOSE = {"(": ")", "[": "]", "{": "}"}
_HEADER = re.compile(r"^#!|^[ \t\f]*#.*?coding[:=]")


def _is_r(value):
    return (isinstance(value, str) and len(value) >= R_SCRIPT_MIN and "library(" in value
            and ("<-" in value or "function(" in value))


def _r_code(text):
    """An R script's CODE: its non-blank lines, each without its comment and trailing space.

    A `#` starts a comment only outside a string, a backtick name and a raw string (`r"(...)"`,
    with its dashes and brackets), as R reads it; a blank line and trailing space say nothing to
    R. So two scripts with the same code differ only in comments, which is what a prose edit may
    change and nothing else."""
    out, i, n, q = [], 0, len(text), None
    while i < n:
        c = text[i]
        if q:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if c == q:
                q = None
            i += 1
            continue
        if c == "#":
            j = text.find("\n", i)
            i = n if j < 0 else j
            continue
        if c in "rR" and (i == 0 or not (text[i - 1].isalnum() or text[i - 1] in "._")):
            m = _R_RAW.match(text, i)
            if m:
                close = _R_CLOSE[m.group(3)] + m.group(2) + m.group(1)
                j = text.find(close, m.end())
                end = n if j < 0 else j + len(close)
                out.append(text[i:end])
                i = end
                continue
        if c in "'\"`":
            q = c
        out.append(c)
        i += 1
    return [ln.rstrip() for ln in "".join(out).split("\n") if ln.strip()]


def _prose_view(src):
    """[(what, line)] - the file as a prose edit must leave it: every Python token but comments
    and line breaks inside a statement; a docstring as `<docstring>`; the declaration's
    `version` as `<version>` (the maker raises it); an embedded R script as its code
    (`_r_code`) and its splice markers; the header lines (a shebang, an encoding cookie) as
    they stand. Raises SyntaxError when the file does not parse."""
    import ast
    import io
    import tokenize
    from .kernels import declaration_node
    tree = ast.parse(src)
    docs = set()
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) \
                and body and isinstance(body[0], ast.Expr) \
                and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
            docs.add((body[0].value.lineno, body[0].value.col_offset))
    vpos = None
    _t, decl, why = declaration_node(src)
    if decl is not None and not why and isinstance(decl.value, ast.Dict):
        for k, v in zip(decl.value.keys, decl.value.values):
            if isinstance(k, ast.Constant) and k.value == "version" and isinstance(v, ast.Constant):
                vpos = (v.lineno, v.col_offset)
    lines = src.split("\n")
    view = []
    try:
        toks = list(tokenize.generate_tokens(io.StringIO(src).readline))
    except (tokenize.TokenError, IndentationError) as e:
        raise SyntaxError(str(e))
    for t in toks:
        row, col = t.start
        if t.type == tokenize.COMMENT:
            if row <= 2 and _HEADER.match(lines[row - 1]):
                view.append((("header", t.string), row))
            continue
        if t.type in (tokenize.NL, tokenize.ENCODING):
            continue
        if t.type == tokenize.STRING:
            pos = (row, len(lines[row - 1][:col].encode("utf-8")))       # ast counts bytes
            if pos in docs:
                view.append((("docstring",), row))
                continue
            if pos == vpos:
                view.append((("version",), row))
                continue
            try:
                value = ast.literal_eval(t.string)
            except (ValueError, SyntaxError):
                value = None
            if _is_r(value):
                view.append((("R", tuple(_r_code(value)), tuple(SPLICE_MARKER.findall(value))),
                             row))
                continue
        view.append(((tokenize.tok_name[t.type], t.string), row))
    return view


def prose_refusals(before, after):
    """[] when `after` differs from `before` in prose alone: a Python comment (inside the
    declaration too), a docstring, a comment of an embedded R script. Otherwise one sentence
    naming the first line of `after` whose code differs. Never raises."""
    try:
        a = _prose_view(before)
    except SyntaxError as e:
        return [f"line 1: the file as it stands does not parse ({e})"]
    lb = _line_breaks(after)
    if lb and not _line_breaks(before):
        return [f"line 1: the edit carries {', '.join(lb)}, which moves the lines the record counts"]
    try:
        b = _prose_view(after)
    except SyntaxError as e:
        return [f"line {getattr(e, 'lineno', None) or 1}: the edit leaves a file that does not "
                f"parse ({e})"]
    if [x for x, _r in a] == [x for x, _r in b]:
        return []
    i = next((j for j, (x, y) in enumerate(zip(a, b)) if x[0] != y[0]), min(len(a), len(b)))
    row = b[i][1] if i < len(b) else (b[-1][1] if b else 1)
    old = a[i][0] if i < len(a) else None
    new = b[i][0] if i < len(b) else None
    if old and new and old[0] == "R" and new[0] == "R":
        what = ("a splice marker changed in the embedded R script" if old[2] != new[2] else
                "the embedded R script's code changed, not only its comments")
        k = next((j for j, (p, q) in enumerate(zip(old[1], new[1])) if p != q), None)
        if k is not None:
            what += f" (`{old[1][k].strip()[:60]}` -> `{new[1][k].strip()[:60]}`)"
        return [f"line {row}: {what} - code, which a prose edit may not change"]
    if (old and old[0] == "header") or (new and new[0] == "header"):
        return [f"line {row}: the file's header line (a shebang or an encoding cookie) is code"]
    show = (lambda x: "nothing" if x is None else
            "a docstring" if x[0] == "docstring" else
            f"`{str(x[1])[:60]}`" if len(x) > 1 else x[0])
    return [f"line {row}: code changed ({show(old)} -> {show(new)}) - a prose edit changes only "
            f"a comment, a docstring, or a comment of an embedded script"]


def prose_answer(kernel, replacements, why, *, as_version=None, dry=False, log=print, root=None):
    """The maker's verb for a plugin's prose: apply each `(old, new)` - `old` occurring exactly
    once - and record the edit, or refuse it. Returns 0 or 1.

    Admitted only when the edit changes prose alone (`prose_refusals`). Recorded like every
    answer outside the declaration, in the plugin's maker record (`design_record_path`), as
    `kind: prose`, with its diff, both digests, the reason and the declaration it left; the
    version is the maker's minor bump, or `as_version`. The record needs an anchor, as a design
    answer does: a plugin DEVPOINTS anchors nowhere - every held-out plugin - is refused, so the
    verb cannot spend one before its own migration."""
    import difflib
    path = Path(kernel.path)
    root = Path(root) if root else path.parent.parent
    if _spent_commit(root, kernel.name) is None:
        log(f"  refused: DEVPOINTS anchors no record for {kernel.name} (`rules.held_out.spent` or "
            f"`rules.end_to_end.anchor`) - a held-out plugin's file changes only in its own "
            f"migration, after it is spent")
        return 1
    if not str(why or "").strip():
        log("  refused: --why is the edit's reason, and a recorded edit carries one")
        return 1
    if not replacements:
        log("  refused: nothing to change - give --replace OLD NEW")
        return 1
    ok, why_not = design_record_check(kernel, root=root)
    if not ok:
        log(f"  refused: the record does not meet kernels/{path.name} as it stands - {why_not}")
        return 1
    with open(path, encoding="utf-8", newline="") as fh:
        before = fh.read()
    text = before
    for old, new in replacements:
        n = text.count(old) if old else 0
        if n != 1:
            log(f"  refused: {old[:80]!r} occurs {n} time(s) in kernels/{path.name}; name it by "
                f"enough of its text to occur exactly once")
            return 1
        text = text.replace(old, new, 1)
    if text == before:
        log("  refused: the edit changes nothing")
        return 1
    refusals = prose_refusals(before, text)
    if refusals:
        for x in refusals:
            log(f"  refused: kernels/{path.name} {x}")
        return 1
    _vl, vold = _version_node(before)
    new_version = as_version or _bump(vold)
    after = _set_version(text, new_version) if vold else text
    bad = _declaration_literal(after)
    if bad:
        log(f"  refused: the edit leaves a declaration the host cannot load - {bad}")
        return 1
    diff = "".join(difflib.unified_diff(_lines(before), _lines(after),
                                        f"a/kernels/{path.name}", f"b/kernels/{path.name}", n=3))
    if dry:
        log(diff.rstrip("\n"))
        log(f"  a dry run: nothing written (version {vold} -> {new_version} when applied)")
        return 0
    # MADE ON A COMMITTED FILE, so the record need not keep the text it removed: an edit that
    # takes a leak out of a plugin would otherwise put the same leak into its record. The record
    # check reads the file back from git at this commit, as it reads the anchor.
    head, how = _git_head(root)
    shown = _git_show(root, head, f"kernels/{path.name}")[0] if head else None
    if shown != before:
        log(f"  refused: kernels/{path.name} differs from the commit it would be made on "
            f"({how}) - commit it first: the record check reads a prose answer's file back from "
            f"git, so the record carries only the lines the edit writes")
        return 1
    rec = _read_record(kernel)
    n = len(rec["answers"]) + 1
    rec["answers"].append({"n": n, "kind": "prose", "why": str(why), "sites": [],
                           "version": new_version, "before": _sha(before), "after": _sha(after),
                           "made_on": head, "diff": _redact(diff),
                           "after_declaration": _declaration_text(after)})
    path.write_text(after, encoding="utf-8")
    _write_record(kernel, rec)
    log(f"  answer {n} (prose) applied to kernels/{path.name}; version {vold} -> {new_version}; "
        f"recorded in kernels/{design_record_path(kernel).name}")
    return 0


def after_edit_followers(root):
    """The followers the tool declares for a maker edit, in order: DEVPOINTS `plan.after_edit`,
    each a list of strings - the list `sch dev edit` runs after its own edits. Read as text, as
    `_spent_commit` reads DEVPOINTS: each entry is one `- [...]` line of quoted strings."""
    import json
    f = Path(root) / "DEVPOINTS.yaml"
    if not f.is_file():
        return []
    out, ind0 = [], None
    for raw in f.read_text(encoding="utf-8").split("\n"):
        s = raw.strip()
        if ind0 is None:
            if s == "after_edit:":
                ind0 = len(raw) - len(raw.lstrip())
            continue
        if not s or s.startswith("#"):
            continue
        if len(raw) - len(raw.lstrip()) <= ind0 or not s.startswith("- ["):
            break
        try:
            out.append([str(x) for x in json.loads(s[2:s.rindex("]") + 1])])
        except ValueError:
            break
    return out


#: How a recorded diff names a line it does not carry: by the digest of the line (`_sha`).
REDACTED = "\u2063sha256:"


def _redact(diff):
    """A unified diff with every line it did not WRITE - context and removed lines - replaced by
    its digest: the record of a prose answer carries no text but what the edit put in."""
    out = []
    for row in _lines(diff):
        if row[:1] in (" ", "-") and not row.startswith("--- "):
            body = row[1:]
            out.append(row[:1] + REDACTED + _sha(body) + "\n")
        else:
            out.append(row if row.endswith("\n") else row + "\n")
    return "".join(out)


def _git_head(root):
    """(commit, how) of HEAD in the repository at `root`, or (None, why)."""
    import os
    import subprocess
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    try:
        r = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True,
                           text=True, timeout=60, env=env)
    except (OSError, subprocess.SubprocessError) as e:
        return None, f"git rev-parse HEAD: {e}"
    if r.returncode:
        return None, f"git rev-parse HEAD: {(r.stderr.strip().splitlines() or ['failed'])[-1]}"
    return r.stdout.strip(), f"HEAD {r.stdout.strip()[:12]}"
