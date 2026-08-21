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

    for req in ("name", "summary"):
        if not spec.get(req):
            f.append(Finding("ERROR", f"{req} missing from kernel.yml"))
    if not kernel.cannot_show:
        f.append(Finding("ERROR", "cannot_show is empty",
                         "a result whose limits were never written down reads exactly as "
                         "authoritative as one whose limits were thought about"))
    if spec.get("layer") not in (None, "stack", "checkpoint"):
        f.append(Finding("ERROR", "layer must be stack or checkpoint", str(spec.get("layer"))))
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

    if spec.get("needs_env", True) and built:
        lock = d / "lock.yml"
        if not lock.exists():
            f.append(Finding("ERROR", "needs_env but no lock.yml"))
        else:
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
            # An `r:` entry is a GIT source, so `==` means nothing there and the pin is a commit.
            # A tag or a branch reads as pinned and is not: a branch moves, and a tag can be
            # re-pointed at a different commit with no version changing anywhere.
            from .runner import R_PIN
            loose_r = [x for x in r_pins if not R_PIN.match(x)]
            if loose_r:
                f.append(Finding("ERROR", "lock.yml has r: entries that are not commit-pinned",
                                 ", ".join(loose_r[:5]) + " — each must be "
                                 "owner/repo@<40-char commit>; a branch or a tag is not a pin"))
            if r_pins and not any(x.split("=", 1)[0].strip() == "r-base" for x in pins):
                f.append(Finding("ERROR", "lock.yml installs R packages but pins no r-base",
                                 "every r-* package is built against one R minor version, so "
                                 "without that pin the same lock resolves differently later"))
        if not (d / "selftest.py").exists() and not (d / "selftest.R").exists():
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

    for name, spec in refs.items():
        if not spec.get("url"):
            f.append(Finding("ERROR", f"reference {name!r} has no url"))
        sha = str(spec.get("sha256") or "")
        if not sha:
            f.append(Finding("ERROR", f"reference {name!r} has no sha256",
                             "it cannot be shown to be the file the result was produced against, "
                             "and a truncated database returns a smaller answer than an error"))
        elif not HEX64.match(sha.lower()):
            f.append(Finding("ERROR", f"reference {name!r} sha256 is not a 64-char hex digest",
                             sha[:20]))
        if not spec.get("size"):
            f.append(Finding("WARN", f"reference {name!r} declares no size",
                             "the fetch cannot report the total or check it fits before starting"))
        if spec.get("organism") and str(spec["organism"]).lower() not in (
                "human", "mouse", "rat", "zebrafish", "fly", "worm", "any"):
            f.append(Finding("WARN", f"reference {name!r} organism {spec['organism']!r} "
                                     f"is not one the profile recognises"))

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
