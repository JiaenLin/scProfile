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


def _sha(text):
    import hashlib
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _scan(src):
    """(fit sites, statement sites, attribute names called) of one plugin's source.

    A FIT site is a call carrying a `FIT_KEYWORDS` argument. Its SPANS are the call's statement
    and the lines that define the names its arguments read - `formula = ...` for `design=formula`,
    `levels = ...` for `contrast=[term, levels[-1], levels[0]]`, the loop header binding `term` -
    in the function it is in: where a fit's frame, formula and levels are decided, and nothing
    else. It was the whole loop or function around the call, so an answer could change a filter
    threshold three lines away, or a selftest's gate, and be recorded as a design answer (W013's
    verifier, fix-up 2). A STATEMENT site is a `ctx.caveat(...)` or `ctx.refuse(...)` whose
    literal words are design words; its span is the statement and the comment block directly
    above it.
    """
    import ast
    import hashlib
    tree = ast.parse(src)
    par = {}
    for node in ast.walk(tree):
        for ch in ast.iter_child_nodes(node):
            par[ch] = node
    lines = src.splitlines()
    compound = (ast.For, ast.AsyncFor, ast.While, ast.If, ast.With, ast.AsyncWith, ast.Try,
                ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)

    def stmt_of(node):
        st = node
        while par.get(st) is not None and not isinstance(st, ast.stmt):
            st = par[st]
        return st

    def header_end(st):
        """A compound statement's header lines only; a simple statement whole."""
        body = getattr(st, "body", None)
        if isinstance(st, compound) and body:
            return max(st.lineno, body[0].lineno - 1)
        return st.end_lineno

    def bound(st):
        """The names a statement binds: its targets, and the object a target mutates."""
        if isinstance(st, (ast.Import, ast.ImportFrom)):
            return {(a.asname or a.name).split(".")[0] for a in st.names}
        targets = (st.targets if isinstance(st, ast.Assign) else
                   [st.target] if isinstance(st, (ast.AugAssign, ast.AnnAssign, ast.For,
                                                  ast.AsyncFor)) else
                   [i.optional_vars for i in st.items if i.optional_vars is not None]
                   if isinstance(st, (ast.With, ast.AsyncWith)) else [])
        out, todo = set(), list(targets)
        while todo:
            t = todo.pop()
            if isinstance(t, (ast.Tuple, ast.List)):
                todo.extend(t.elts)
                continue
            while isinstance(t, (ast.Attribute, ast.Subscript, ast.Starred)):
                t = t.value
            if isinstance(t, ast.Name):
                out.add(t.id)
        return out

    def fit_spans(node):
        st = stmt_of(node)
        keep = set(range(st.lineno, st.end_lineno + 1))
        reads = {n.id for a in list(node.args) + [k.value for k in node.keywords]
                 for n in ast.walk(a) if isinstance(n, ast.Name)}
        scope = par.get(st)
        while scope is not None and not isinstance(scope, (ast.FunctionDef,
                                                           ast.AsyncFunctionDef)):
            scope = par.get(scope)
        if scope is not None:
            # A PARAMETER IS GIVEN, NOT DEFINED HERE: `ctx` is read by `n_cpus=ctx.cores`, and
            # every `ctx.headline = ...` would otherwise count as a line defining it.
            a = scope.args
            reads -= {x.arg for x in (a.posonlyargs + a.args + a.kwonlyargs
                                      + [v for v in (a.vararg, a.kwarg) if v])}
        for t in ast.walk(scope if scope is not None else tree):
            if isinstance(t, ast.stmt) and t is not scope and bound(t) & reads:
                keep |= set(range(t.lineno, header_end(t) + 1))
        runs = []
        for ln in sorted(keep):
            if runs and ln == runs[-1][1] + 1:
                runs[-1][1] = ln
            else:
                runs.append([ln, ln])
        return [tuple(r) for r in runs]

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
            fits.append({"line": node.lineno, "call": name or "<call>", "kws": kws,
                         "spans": fit_spans(node)})
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


def _admit(before, after):
    """(ops, sites, outside, after with before's version) - may `before` become `after` as an
    answer to the worksheet?

    Every changed line must lie inside ONE span of a site the worksheet names in `before`, and an
    insertion strictly inside one - between two of its lines, never at its edge: inserted after
    a loop's last line, a statement belongs to no site however close it sits (W013's verifier,
    fix-up 2). The `version` line is the maker's and is not an answer's change. `sites` names
    every site an answer touches; `outside` every change no site holds.
    """
    import difflib
    _vl, vold = _version_node(before)
    norm = _set_version(after, vold) if vold else after
    fits, stmts, _c = _scan(before)
    spans = ([(f"fit:{f['line']}", a, b) for f in fits for a, b in f["spans"]]
             + [(f"statement:{x['line']}", x["span"][0], x["span"][1]) for x in stmts])
    b, a = before.splitlines(keepends=True), norm.splitlines(keepends=True)
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
    return ops, sorted(sites), outside, norm


def design_sites(kernel):
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
    """
    spec = kernel.spec or {}
    inj = spec.get("inject") or {}
    takes = (set(inj.get("required") or []) | set(inj.get("optional") or [])
             if isinstance(inj, dict) else set())
    out = {"design_aware": bool(takes & {"design", "contrast"}), "sites": [], "statements": [],
           "missing": [], "owes": False, "takes": sorted(takes)}
    path = Path(kernel.path)
    if not out["design_aware"] or not path.is_file():
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
    out["owes"] = bool(out["missing"])
    return out


def design_report(kernel, log=print):
    """Print `design_sites` as a worksheet. Returns 0 when nothing is owed, 1 otherwise."""
    d = design_sites(kernel)
    rel = Path(kernel.path).name
    if not d["design_aware"]:
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
        elif not acc.startswith("statement:"):
            log(f"         ctx.{acc}(...): {what}")
    if owed:
        log(f"         the statements at line(s) {', '.join(owed)}: {STATEMENT_OWES}")
    log(f"       HOW AN ANSWER IS MADE, and recorded in kernels/{design_record_path(kernel).name}:"
        f" change the file and hand it in whole - `scprofile design {kernel.name} --answer <file>"
        f" --why \"...\"` applies it only inside a site above - a fit call's statement and the"
        f" lines defining what its arguments read, or a statement and its comment - and records"
        f" the diff - or,"
        f" for a statement true as it stands, `scprofile design {kernel.name} --confirm <line> "
        f"--why \"...\"`.")
    return 1


def _version_node(src):
    """(line, current value) of the PLUGIN dict's `version`, or (None, None)."""
    import ast
    tree = ast.parse(src)
    for n in tree.body:
        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "PLUGIN"
                                             for t in n.targets) and isinstance(n.value, ast.Dict):
            for k, v in zip(n.value.keys, n.value.values):
                if isinstance(k, ast.Constant) and k.value == "version" \
                        and isinstance(v, ast.Constant):
                    return v.lineno, str(v.value)
    return None, None


def _set_version(src, value):
    line, old = _version_node(src)
    if line is None:
        return src
    lines = src.splitlines(keepends=True)
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


def design_answer(kernel, proposed, why, *, as_version=None, log=print):
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
    before = path.read_text(encoding="utf-8")
    try:
        ops, sites, outside, text = _admit(before, Path(proposed).read_text(encoding="utf-8"))
    except SyntaxError as e:
        log(f"  refused: a file does not parse ({e})")
        return 1
    if not ops:
        log("  refused: the file handed in is the file as it stands - nothing to answer")
        return 1
    if outside:
        log(f"  refused: line(s) {', '.join(outside)} of kernels/{path.name} are in no site the "
            f"worksheet names - an answer is made where the maker asks, or it is a hand edit")
        return 1
    if not sites:
        log("  refused: the answer names no site of the worksheet")
        return 1
    _vl, vold = _version_node(before)
    new_version = as_version or _bump(vold)
    after = _set_version(text, new_version) if vold else text
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
    diff = "".join(difflib.unified_diff(before.splitlines(keepends=True),
                                        after.splitlines(keepends=True),
                                        f"a/kernels/{path.name}", f"b/kernels/{path.name}", n=3))
    rec["answers"].append({"n": n, "why": str(why), "sites": sites, "version": new_version,
                           "before": _sha(before), "after": _sha(after), "diff": diff})
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
    src = text.splitlines(keepends=True)
    lines = diff.splitlines(keepends=True)
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
                if i >= len(src) or src[i] != body:
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
        # site does not replay (W013's verifier, fix-up 2).
        _ops, sites, outside, _n = _admit(text, new)
        if outside or not sites or sites != sorted(ans.get("sites") or []):
            log(f"  answer {ans['n']}: refused on replay - "
                + (f"line(s) {', '.join(outside)} are in no site the worksheet names"
                   if outside else f"it names {sites or 'no site'}, the record says "
                                   f"{ans.get('sites')}"))
            return 1
        text = new
        if _sha(text) != ans["after"]:
            log(f"  answer {ans['n']}: applied, and the result is not the file it made")
            return 1
        log(f"  answer {ans['n']} replayed at {', '.join(ans['sites'])} -> {ans['after']}")
    t.write_text(text, encoding="utf-8")
    log(f"  {len(rec['answers'])} answer(s) replayed into {t}")
    return 0
