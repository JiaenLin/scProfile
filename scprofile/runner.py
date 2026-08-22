"""Resolving a kernel's environment and running it. The host never imports a kernel.

WHY A SUBPROCESS AND NOT AN IMPORT

pySCENIC has pinned old numpy; CellChat is R. They cannot share an interpreter with each other or
with the host, and they do not need to. A kernel is an executable behind a file contract, so the
only thing that has to agree between the host and a kernel is JSON.

The consequence to keep in mind: the host cannot catch a kernel's exception. It sees an exit code
and whatever the kernel wrote. That is why `manifest.read_output` validates rather than trusts, and
why a missing `out.json` and an empty one mean different things.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

from . import manifest

#: Where an installed kernel environment lives, relative to the prefix. One per kernel, named so
#: two tools sharing a prefix cannot collide.
ENV_DIRNAME = "scprofile-{kernel}"


def with_env_bin(exe, base=None):
    """The subprocess environment for a plugin, with ITS OWN environment's `bin` on PATH.

    AN ENVIRONMENT IS NOT ONLY AN INTERPRETER. It provides binaries, and a plugin whose method
    lives in another language reaches them by name: cellchat runs `Rscript`, and `shutil.which`
    inside it searches PATH. Launching `<env>/bin/python` by absolute path does NOT put
    `<env>/bin` on PATH - that is what `conda activate` does and the host was not doing - so the
    plugin found the system's Rscript, or none, and the failure reads as "R is not installed"
    about an environment that contains R and a complete CellChat.

    `_install_r` learned this at PBS 676357 and fixed it for the one subprocess it launches. The
    RUNNER, which launches every plugin and every selftest, did not - the same door, one room
    over.
    """
    e = dict(os.environ if base is None else base)
    d = str(Path(exe).resolve().parent)
    e["PATH"] = d + os.pathsep + e.get("PATH", "")
    return e


def env_prefix(kernel_name, prefix):
    """The PER-PLUGIN environment path. Kept, and kept at this signature.

    Resolution happens in `resolved_prefix` below rather than here, because this function is
    called and stubbed by other code: widening its signature broke a test that legitimately
    replaces it, and a change that forces every caller to be edited is a change in the wrong
    place.
    """
    return Path(prefix).expanduser() / ENV_DIRNAME.format(kernel=kernel_name)


def resolved_prefix(kernel, prefix, *, group=None):
    """Where this plugin's environment actually lives, after resolution.

    The group's content-addressed directory when one was resolved; the per-plugin path otherwise
    - which is also the path an installation built before resolution existed already uses.
    Resolution must not invalidate an environment somebody already has for a reason they did not
    cause.
    """
    if group is not None:
        return Path(prefix).expanduser() / group.name
    return env_prefix(kernel.name, prefix)


def config_override(kernel_name):
    """An interpreter the site has already built, from the environment.

    `SCPROFILE_<KERNEL>_PYTHON` / `_RSCRIPT`. Sites with a module system or a shared env should not
    be made to rebuild what they have; `doctor` reports which route each kernel took so the answer
    is never ambiguous.
    """
    up = kernel_name.upper().replace("-", "_")
    for suffix in ("PYTHON", "RSCRIPT"):
        v = os.environ.get(f"SCPROFILE_{up}_{suffix}")
        if v:
            return v, f"$SCPROFILE_{up}_{suffix}"
    return None, ""


def interpreter(kernel, prefix=None):
    """(path, source) for the thing that runs this kernel, or (None, why-not).

    Order: an explicit site override, then an installed env, then - for a kernel that declares it
    needs none - the host's own interpreter.
    """
    over, src = config_override(kernel.name)
    if over:
        return (over, src) if Path(over).exists() else (None, f"{src} points at {over}, which "
                                                             f"does not exist")
    if not kernel.needs_env:
        import sys
        return sys.executable, "the host interpreter (this kernel declares needs_env: false)"
    if prefix:
        # THE RESOLVED ENVIRONMENT FIRST. A plugin sharing one with others finds it here; a
        # plugin whose own older per-plugin environment exists still finds that, because
        # resolution must not invalidate an installation somebody already has.
        grp, gpath = env_for(kernel, prefix)
        if gpath is not None and gpath.exists():
            exe = gpath / "bin" / ("Rscript" if kernel.language == "r" else "python")
            if exe.exists():
                shared = [m for m in grp.members if m != kernel.name]
                return str(exe), ("installed at " + str(gpath)
                                  + (f", shared with {', '.join(shared)}" if shared else ""))
        p = env_prefix(kernel.name, prefix)
        exe = p / "bin" / ("Rscript" if kernel.language == "r" else "python")
        if exe.exists():
            return str(exe), f"installed at {p}"
        return None, (f"no environment at {p}.  Fix: scprofile install {kernel.name} "
                      f"--prefix {prefix}")
    return None, (f"no --prefix given and no $SCPROFILE_{kernel.name.upper()}_PYTHON set.  "
                  f"Fix: scprofile install {kernel.name} --prefix <dir>, or set the variable.")


def build_spec(group, log=None):
    """What the installer must build for a resolved GROUP, in the shape `lock_spec` returns.

    THE BUILDER BUILDS WHAT THE RESOLVER RESOLVED. Until now it did not: resolution decided WHERE
    the environment goes and the plugin's own `lock.yml` still decided WHAT went into it - so an
    environment shared by four plugins was built from one of them, and the other three found a
    directory that looked finished and did not contain their packages. Nothing said so, because
    the shared directory existed and carried a stamp.

    The group is built WHOLE, including the members that were not asked for. A shared environment
    is not divisible: building one member's slice into it would leave a directory whose name
    claims to satisfy four requirements and satisfies one.
    """
    from . import resolve as RS
    py = RS.concrete_python(group.python)
    spec = {"python": py,
            "channels": list(group.channels) or ["conda-forge"],
            # VERBATIM. conda's grammar is not pip's; see resolve.Group.conda.
            "conda": [f"{n}={v}" if str(v).strip() else n
                      for n, v in sorted(group.conda.items())],
            "pip": [f"{n}{c}" for n, c in sorted(group.packages.items())],
            "r": list(group.r)}
    if spec["r"] and not any(c.split("=", 1)[0].strip() == "r-base" for c in spec["conda"]):
        raise ValueError(
            f"{group.name}: its requirement names R packages and pins no `r-base`. R is the "
            f"interpreter those resolve against, exactly as the python minor version decides "
            f"which wheels are built, so a requirement that omits it is not a requirement.")
    if not py and not spec["conda"]:
        raise ValueError(
            f"{group.name}: this requirement pins no interpreter and names no conda package, so "
            f"there is nothing to build an environment from.")
    if log:
        log(f"  requirement: python {group.python or 'unconstrained'} -> "
            + (f"python {py}" if py else "no python (another language's environment)")
            + f", {len(spec['pip'])} pip, {len(spec['conda'])} conda, {len(spec['r'])} r")
    return spec


def lock_fingerprint(kernel):
    """A short digest of `lock.yml`, so an env built from an older lock can be called STALE.

    Neither present nor absent is the right word for an environment built from a specification that
    has since changed: it will import, it will run, and it will not be what the lock describes.
    """
    import hashlib
    f = kernel.path / "lock.yml"
    if not f.exists():
        return ""
    return hashlib.sha256(f.read_bytes()).hexdigest()[:12]


def env_fingerprint(kernel, group=None):
    """What the `.scprofile_lock` stamp must say for this environment to be the current one.

    For a RESOLVED group that is the group's own content-addressed name, which is already a
    digest of everything that decides what gets built - so a changed requirement is a different
    directory rather than a stale one, and the stamp's job narrows to the one thing a directory
    cannot say: that the build reached its last act.
    """
    return group.name if group is not None else lock_fingerprint(kernel)


def env_state(kernel, prefix=None):
    """`installed` / `missing` / `stale` / `override` / `host`, with a sentence and a fix.

    IT LOOKS WHERE THE ENVIRONMENT ACTUALLY IS. This read the per-plugin path alone, so a plugin
    whose environment had been RESOLVED into a shared directory - built, stamped and proved - was
    reported `missing` by `doctor`, refused by `plan` as having no environment, and rejected by
    `install` as a half-built directory belonging to somebody else. Every one of those is the
    same bug: two functions in this file disagreeing about where a plugin's interpreter lives.
    """
    over, src = config_override(kernel.name)
    if over:
        return ("override", f"{src} -> {over}", "")
    if not kernel.needs_env:
        return ("host", "runs in the host interpreter", "")
    if not prefix:
        return ("missing", "no --prefix given",
                f"scprofile install {kernel.name} --prefix <dir>")
    grp, gpath = env_for(kernel, prefix)
    #: The resolved location first, then the per-plugin one - resolution must not invalidate an
    #: environment somebody already has for a reason they did not cause.
    tried = ([(gpath, grp)] if gpath is not None else []) + [(env_prefix(kernel.name, prefix),
                                                             None)]
    for p, g in tried:
        st = state_at(p, kernel, g, prefix)
        if st[0] != "missing":
            shared = [m for m in (g.members if g is not None else []) if m != kernel.name]
            if st[0] == "installed" and shared:
                return ("installed", f"{p}, shared with {', '.join(shared)}", "")
            return st
    return state_at(tried[0][0], kernel, tried[0][1], prefix)


def state_at(p, kernel, group, prefix):
    """The state of ONE candidate directory, asked about directly.

    Separated from `env_state`'s search because `install` must ask about the path IT IS BUILDING
    and not about wherever an interpreter can be found. A half-built group directory has no
    `bin/python`, so the search walks past it to the plugin's older per-plugin environment and
    reports `installed` - correctly, by its own question - and `install` then read that as "the
    directory I am about to build already matches", skipped the build, and proved the OLD
    environment. Two different questions that had one function.
    """
    exe = p / "bin" / ("Rscript" if kernel.language == "r" else "python")
    if not exe.exists():
        return ("missing", f"nothing at {p}",
                f"scprofile install {kernel.name} --prefix {prefix}")
    want = env_fingerprint(kernel, group)
    stamp = p / ".scprofile_lock"
    got = stamp.read_text(encoding="utf-8").strip() if stamp.exists() else ""
    if want and got != want:
        word = "requirement" if group is not None else "lock"
        return ("stale", f"built from {word} {got or 'unknown'}, current {word} is {want}",
                f"scprofile install {kernel.name} --prefix {prefix} --force")
    return ("installed", str(p), "")


#: Sections `lock.yml` may carry at indent 0. Anything else RAISES rather than being skipped: a
#: lock is a claim about an environment, and a section the installer read and ignored is a pin the
#: environment does not have while its fingerprint says it does. `r:` was added for cellchat.
LOCK_SECTIONS = ("name", "channels", "dependencies", "r")

#: An `r:` entry is one of two things, and both are exact.
#:
#:   owner/repo@<40-hex>   a git commit. A tag or a branch is NOT a pin - a branch moves and a tag
#:                         can be re-pointed at a different commit with nothing else changing.
#:   Package==<version>    a CRAN release, current or archived. Spelled like the pip pins in the
#:                         same file on purpose: it means the same thing.
#:
#: The CRAN form exists because a conda channel's ceiling is not the package's. conda-forge's
#: r-nmf stops at 0.21.0 and CellChat requires NMF >= 0.23.0, so an environment built from conda
#: alone cannot install CellChat at all - `R CMD INSTALL` refuses on the version requirement.
R_GIT_PIN = re.compile(r"^[\w.-]+/[\w.-]+@[0-9a-f]{40}$")
R_CRAN_PIN = re.compile(r"^([A-Za-z][\w.]*)==([0-9][\w.-]*)$")


def r_pin_kind(item):
    """`git`, `cran`, or None if it is neither - which is the only case a lock may not contain."""
    if R_GIT_PIN.match(item):
        return "git"
    if R_CRAN_PIN.match(item):
        return "cran"
    return None


def lock_spec(kernel):
    """Read `lock.yml` into {python, channels, conda, pip, r}. Stdlib only, like everything here.

    The file is a conda environment YAML because that is the format people recognise, but it is
    NOT handed to `conda env create`. Two reasons, both measured:

    - `conda env create --yes` does not exist before conda 23.10, and clusters run what they run.
      One site here has conda 4.10.3. An installer that only works on a recent conda is an
      installer that fails on exactly the machines a pipeline tool is used on.
    - Handing conda a file makes the pip section conda's problem, and conda runs it as a second,
      separate resolve whose failures it reports as a warning. Pins that were silently not applied
      are the specific outcome this lock exists to prevent.

    So the two steps are taken explicitly: conda builds the interpreter, pip applies the pins in
    ONE resolve. Anything the parser does not understand raises, rather than being skipped.

    THE `r:` SECTION, AND WHY IT HAD TO EXIST

    A conda environment YAML expresses conda packages and pip packages, and nothing else. It has no
    way to say "install this R package from a git commit" - so an R plugin whose method is
    distributed only on GitHub could not be locked at all. CellChat is exactly that, measured
    rather than assumed: PBS 676350 asked the channels - `conda search r-cellchat` and
    `bioconductor-cellchat` over conda-forge and bioconda both returned "No match found" - so it
    is on neither conda-forge nor
    bioconda. The two personal channels carrying it are a two-year-old linux-64 build and a
    macOS-arm64 one, which is not something another site could reproduce.

    `r:` is therefore a list of exact pins - `owner/repo@<40-char commit>` for a git source, and
    `Package==<version>` for a CRAN release - applied by `remotes::install_github` and
    `remotes::install_version`, both with `upgrade = "never"` and `dependencies = FALSE`. The
    discipline is the pip path's and so is the reason: installed one at a time, a later package
    re-resolves an earlier one and the environment stops matching the lock its fingerprint claims.
    `dependencies = FALSE` is the load-bearing half - every dependency comes from the pinned conda
    section, so NOTHING in the environment is chosen at install time. A dependency that was
    forgotten then surfaces in the selftest as a package that will not load, by name, which is a
    line to add to the lock rather than an unpinned install nobody sees.
    """
    f = kernel.path / "lock.yml"
    if not f.exists():
        raise FileNotFoundError(f"{kernel.name} has no lock.yml; it cannot be installed")
    spec = {"python": None, "channels": [], "conda": [], "pip": [], "r": []}
    section, in_pip, pip_indent = None, False, None
    for raw in f.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        body = line.strip()
        if indent == 0:
            section, in_pip = body.split(":", 1)[0].strip(), False
            if section not in LOCK_SECTIONS:
                raise ValueError(
                    f"{f}: `{section}:` is not a section this installer applies. It knows "
                    f"{', '.join(LOCK_SECTIONS)}. A section that is read and skipped is a pin the "
                    f"environment does not have while its fingerprint says it does.")
            continue
        if not body.startswith("- "):
            raise ValueError(f"{f}: cannot read {raw!r}")
        item = body[2:].strip()
        if section == "channels":
            spec["channels"].append(item)
        elif section == "r":
            if r_pin_kind(item) is None:
                raise ValueError(
                    f"{f}: r entry {item!r} is neither `owner/repo@<40-char commit>` nor "
                    f"`Package==<version>`. A tag or a branch is not a pin - a branch moves and a "
                    f"tag can be re-pointed - and the whole point of this section is that the "
                    f"same lock builds the same package on a machine nobody has seen.")
            spec["r"].append(item)
        elif section == "dependencies":
            if in_pip and pip_indent is not None and indent > pip_indent:
                spec["pip"].append(item)
                continue
            in_pip = False
            if item in ("pip:", "pip :"):
                in_pip, pip_indent = True, indent
            elif item.startswith("python="):
                spec["python"] = item.split("=", 1)[1]
            elif item != "pip":
                spec["conda"].append(item)
    # A LOCK MUST PIN ITS OWN INTERPRETER, and for an R kernel that is not python. Demanding
    # `python=` from an R lock would be the format asserting an assumption rather than checking
    # one; `r-base=` is the line that decides which binaries every `r-*` package resolves against,
    # exactly as the python minor version decides which wheels are built.
    if kernel.language == "r":
        if not any(c.split("=", 1)[0].strip() == "r-base" for c in spec["conda"]):
            raise ValueError(
                f"{f}: no `r-base=<version>` in dependencies. This kernel declares `language: r`, "
                f"so R is the interpreter the lock has to pin - r-* packages are built against a "
                f"given R minor version and resolve differently without it.")
    elif not spec["python"]:
        raise ValueError(f"{f}: no `python=<version>` in dependencies. A lock that does not pin "
                         f"the interpreter is not a lock - wheels are built per minor version.")
    return spec


def _venv_python(want):
    """A `pythonX.Y` on PATH matching the lock, for the route that needs no conda at all."""
    exe = shutil.which(f"python{want}")
    return exe if exe else None


#: The R half of the installer. Written to the environment as a file rather than passed with
#: `-e`, so that what ran is on disk beside what it built - an install nobody can read afterwards
#: is an install nobody can check.
R_INSTALL_SCRIPT = r'''
# Written by scprofile from lock.yml. Do not edit: it is regenerated on every install, and the
# lock is the thing to change.

# INSTALL INTO THIS ENVIRONMENT, EXPLICITLY. `.Library` is the environment's own library whatever
# its layout, and it is named here rather than left to `.libPaths()[1]` because that is whatever
# R_LIBS_USER happens to say. Measured on PBS 676357: with R_LIBS_USER set, NMF and CellChat were
# installed into a scratch directory OUTSIDE the environment, `install_github` reported a warning
# rather than an error, and the environment `doctor` would then have called installed contained
# neither package. The caller also scrubs R_LIBS* from this process's environment; this is the
# second lock on the same door, because the failure is silent on both sides.
lib <- .Library
.libPaths(lib)

if (!requireNamespace("remotes", quietly = TRUE)) {
  stop("remotes is not installed. Add `r-remotes=` to the conda dependencies - this step needs ",
       "it, and installing it here would put an unpinned package in an environment whose whole ",
       "claim is that nothing in it was chosen at install time.")
}
repos <- getOption("repos")
if (is.null(repos) || !nzchar(repos[[1]]) || repos[[1]] == "@CRAN@") {
  repos <- c(CRAN = "https://cloud.r-project.org")
}

specs <- SPECS
cran  <- specs[grepl("==", specs, fixed = TRUE)]
git   <- specs[!grepl("==", specs, fixed = TRUE)]

# CRAN ENTRIES FIRST, and the order is not arbitrary. They are here because a conda channel's
# ceiling was below what a git package requires, and `R CMD INSTALL` checks those version
# requirements while installing the git package - so an entry applied afterwards would be applied
# after the thing it exists to satisfy had already refused.
for (s in cran) {
  pkg <- sub("==.*", "", s); ver <- sub(".*==", "", s)
  cat(sprintf("    CRAN  %s %s\n", pkg, ver))
  remotes::install_version(pkg, version = ver, repos = repos, upgrade = "never",
                           dependencies = FALSE, quiet = FALSE, lib = lib)
}
if (length(git)) {
  for (s in git) cat(sprintf("    git   %s\n", s))
  remotes::install_github(git, upgrade = "never", dependencies = FALSE, force = TRUE,
                          quiet = FALSE, lib = lib)
}

# THE RECEIPT. Both installers report success for a build that produced no loadable package often
# enough to be worth checking, and a package at the wrong version is the failure this whole
# section exists to prevent.
for (s in cran) {
  pkg <- sub("==.*", "", s); ver <- sub(".*==", "", s)
  if (!requireNamespace(pkg, lib.loc = lib, quietly = TRUE)) {
    stop(sprintf("%s installed without error and cannot be loaded from %s", pkg, lib))
  }
  got <- as.character(utils::packageVersion(pkg, lib.loc = lib))
  if (got != ver) stop(sprintf("%s is at %s; the lock asked for %s", pkg, got, ver))
  cat(sprintf("    ok    %s %s  (CRAN)\n", pkg, got))
}
for (s in git) {
  pkg <- sub("@.*", "", sub(".*/", "", s)); want <- sub(".*@", "", s)
  if (!requireNamespace(pkg, lib.loc = lib, quietly = TRUE)) {
    stop(sprintf(paste("%s installed without error and cannot be loaded from %s. If the",
                       "repository name and the package name differ, this is what that looks",
                       "like."), pkg, lib))
  }
  got <- utils::packageDescription(pkg, lib.loc = lib)$RemoteSha
  if (is.null(got) || substr(got, 1, 40) != want) {
    stop(sprintf("%s reports commit %s; the lock asked for %s", pkg,
                 if (is.null(got)) "none" else got, want))
  }
  cat(sprintf("    ok    %s %s @ %s  (git)\n", pkg, utils::packageVersion(pkg, lib.loc = lib),
              substr(want, 1, 7)))
}
'''


def _install_r(p, entries, log=print):
    """Apply the lock's `r:` section. Nothing in it is resolved; every version is in the lock.

    Four things are deliberate and each is the R spelling of something the pip path already does
    for a reason that was measured.

    `upgrade = "never"`  - remotes' default is to offer to update every dependency it finds out of
                           date, which against a conda-built library means replacing packages the
                           conda section pinned. The lock would then describe an environment that
                           no longer exists.
    `dependencies=FALSE` - every dependency comes from the pinned conda section. Letting remotes
                           fetch a missing one installs an UNPINNED package that nothing recorded,
                           and it works, which is what makes it dangerous. A dependency that was
                           forgotten instead fails to load in the selftest, by name.
    one process          - all pins applied together, so no entry can re-resolve an earlier one.
    CRAN before git      - see the script; the git package's install-time version checks are what
                           the CRAN entries exist to satisfy.

    TWO THINGS ABOUT THE SUBPROCESS ENVIRONMENT, both measured on PBS 676357 and both silent.

    `<prefix>/bin` MUST BE ON PATH. A conda R's `Makeconf` names its compilers by bare name -
    `CC = x86_64-conda-linux-gnu-cc` - and those binaries live in the environment's own `bin`.
    Running `<prefix>/bin/Rscript` by absolute path does not put that directory on PATH, so every
    package with compiled code failed with `x86_64-conda-linux-gnu-cc: command not found` while
    the compilers sat pinned and installed a few directories away. This is what `conda activate`
    would have done; the installer does it for the one subprocess that needs it.

    `R_LIBS_USER` and friends ARE SCRUBBED. R installs into `.libPaths()[1]`, which those
    variables control, so a site setting sends the packages somewhere outside the environment -
    where they install successfully, are reported as installed, and are not in the environment
    that `doctor` then calls ready. An earlier version of this docstring claimed `.libPaths()`
    inside a conda prefix's Rscript already points at that prefix's library; it does when nothing
    overrides it, and the whole risk is the case where something does.
    """
    rscript = p / "bin" / "Rscript"
    if not rscript.exists():
        raise RuntimeError(
            f"the lock has an `r:` section but there is no Rscript at {rscript}. Add `r-base=` to "
            f"its dependencies - the conda step builds the interpreter that this step then uses.")
    kinds = [f"{e} ({r_pin_kind(e)})" for e in entries]
    log(f"  applying {len(entries)} pinned R package(s), nothing resolved: {', '.join(kinds)}")
    specs = "c(" + ", ".join(f'"{e}"' for e in entries) + ")"
    f = p / ".scprofile_r_install.R"
    f.write_text(R_INSTALL_SCRIPT.replace("SPECS", specs), encoding="utf-8")
    env = dict(os.environ)
    env["PATH"] = f"{p / 'bin'}{os.pathsep}{env.get('PATH', '')}"
    for var in ("R_LIBS_USER", "R_LIBS_SITE", "R_LIBS"):
        env.pop(var, None)
    subprocess.run([str(rscript), str(f)], check=True, env=env)


def env_for(kernel, prefix, *, all_kernels=None):
    """The environment THIS plugin resolves to - which may be shared with others.

    A plugin no longer owns an environment; it owns a REQUIREMENT, and the builder decides how
    few environments satisfy them all. Named for its CONTENT, so two plugins wanting the same
    stack land in the same directory and the second one costs nothing.
    """
    from . import resolve as RS
    from .kernels import discover
    ks = all_kernels if all_kernels is not None else discover().values()
    for g in RS.group_by_compatibility(list(ks)):
        if kernel.name in g.members:
            return g, Path(prefix) / g.name if prefix else None
    return None, None


def machine(log=None):
    """What THIS machine can build with. Probed once, reported, never assumed.

    The builder runs again for every new user and every new machine, and the machines differ: a
    cluster with `module load anaconda3` and nothing on PATH until you do, a laptop with
    micromamba, a container with only the system python. A builder that assumes one of those
    fails on the other two with a message about the tool it wanted rather than the ones present.

    Returns {"managers": [...], "pythons": [...], "route": str, "why": str}.
    """
    import shutil
    import sys as _s
    mgrs = [m for m in ("micromamba", "mamba", "conda") if shutil.which(m)]
    pys = sorted({f"{v}" for v in ("3.10", "3.11", "3.12", "3.13")
                  if shutil.which(f"python{v}")})
    if mgrs:
        route = mgrs[0]
        why = (f"{mgrs[0]} is on PATH, so an environment can be built at any pinned python "
               f"version and with conda packages")
    elif pys:
        route = "venv"
        why = (f"no conda-family manager on PATH, but python {', '.join(pys)} are - a lock that "
               f"needs only pip packages can be built as a venv")
    else:
        route = "host"
        why = (f"neither a conda-family manager nor a versioned python is on PATH. Only plugins "
               f"declaring no environment can run; this interpreter is {_s.version.split()[0]}")
    out = {"managers": mgrs, "pythons": pys, "route": route, "why": why}
    if log:
        log(f"  machine: {route} - {why}")
    return out


def install(kernel, prefix, *, force=False, log=print, dry_run=False):
    """Build the environment this plugin RESOLVES TO, then prove it with every member's selftest.

    A selftest that runs at INSTALL time is the difference between finding out now and finding out
    after the models have trained. It is the kernel's own file, because only the kernel knows what
    importing successfully means for it.

    THE UNIT OF INSTALLATION IS THE RESOLVED ENVIRONMENT, NOT THE PLUGIN. The resolver decides how
    few environments satisfy every plugin's requirement; an environment shared by four of them is
    built once, from the merged requirement, and PROVED FOR ALL FOUR - because an environment that
    only one of its members has ever run is an environment the other three will discover inside
    somebody's run. That is also why installing one member costs what it costs: a shared
    environment is not divisible.

    Two kinds of plugin have nothing to install and are refused HERE rather than allowed to fall
    through to a message about a missing file. "no lock.yml" is true of both and explains neither,
    and a user reading it cannot tell "I should write one" from "there is nothing to write".
    """
    if not kernel.needs_env:
        raise RuntimeError(
            f"{kernel.name} declares `needs_env: false`: it runs in the HOST interpreter, so "
            f"there is nothing to install and no lock to build.\n"
            f"  Its selftest still matters and still runs - a host-interpreter plugin is a "
            f"wrapper too, and only a selftest proves its call is well-formed against the version "
            f"actually installed:  scprofile selftest {kernel.name}\n"
            f"  If it should have its own pinned environment, set `needs_env: true` in "
            f"{kernel.path / 'kernel.yml'} and write {kernel.path / 'lock.yml'}.")
    grp, _gp = env_for(kernel, prefix)
    if grp is None and not (kernel.path / "lock.yml").exists():
        raise FileNotFoundError(
            f"{kernel.name} needs an environment and has no {kernel.path / 'lock.yml'}, so there "
            f"is nothing to build from. It is `status: {kernel.status}`.\n"
            + ("  A planned plugin is a DECLARATION - its prerequisites are real and checkable "
               "and its implementation does not exist. `scprofile scaffold " + kernel.name
               + "` writes the skeleton, including the lock.\n"
               if kernel.status != "built" else "")
            + f"  A lock is captured from a resolve that WORKS, every line pinned; do not write "
              f"one from memory.")
    p = resolved_prefix(kernel, prefix, group=grp)
    members = list(grp.members) if grp is not None else [kernel.name]
    if grp is not None:
        log(f"  environment {grp.name}")
        log(f"      shared by: {', '.join(members)}"
            + ("" if len(members) > 1 else "   (alone: " + (grp.why_alone or "it is the only "
               "plugin declaring a requirement") + ")"))
        spec = build_spec(grp, log=log)
    else:
        # NO RESOLVED GROUP. A plugin the host cannot discover - handed in directly, or living
        # outside every kernel root - is not part of any resolution, so its own lock is the only
        # statement of what it needs and it is built alone at the per-plugin path.
        log(f"  no resolved group for {kernel.name}; building from its own lock at {p}")
        spec = lock_spec(kernel)
    if dry_run:
        # RESOLVE AND REPORT, BUILD NOTHING. The resolver proves that the DECLARED constraints do
        # not contradict each other; it cannot prove that their transitive closure installs. That
        # is a different claim and only a resolver with an index can make it, so this prints
        # exactly what would be handed to one and stops.
        log(f"  --dry-run: nothing was built. {p} " + ("exists" if p.exists() else "does not exist"))
        for field in ("channels", "conda", "pip", "r"):
            for item in spec[field]:
                log(f"      {field:<9} {item}")
        log(f"      selftests that would run: {', '.join(members)}")
        return p
    if p.exists() and not force:
        # AN ENVIRONMENT THAT EXISTS IS NOT AN ENVIRONMENT THAT WAS FINISHED. `.scprofile_lock` is
        # written as the LAST act of a successful build, so its absence means a build got part of
        # the way and stopped - conda succeeded, the pip or r: step did not - and the directory
        # left behind looks exactly like a complete one from the outside.
        #
        # Measured on PBS 676357: the conda step built 306 packages, the r: step failed, no stamp
        # was written, and `doctor` reported `stale - built from lock unknown`. `install` did not
        # ask. Re-running it without --force would have printed "exists" and gone straight to a
        # selftest against an environment with none of the plugin's own packages in it - and that
        # selftest failure reads as a broken package rather than as a build that never finished.
        # env_state knew and install did not; they now read the same stamp.
        state, detail, fix = state_at(p, kernel, grp, prefix)
        if state != "installed":
            raise RuntimeError(
                f"{p} exists but is {state}: {detail}." + "\n"
                "  It is not an environment this lock describes, so nothing here will treat it as "
                "one. A partial build leaves a directory that looks finished from the outside, "
                "which is why this refuses rather than carrying on to the selftest.\n"
                f"  Fix: {fix or f'scprofile install {kernel.name} --prefix {prefix} --force'}")
        log(f"  {p} exists and matches the current lock. Pass --force to rebuild.")
        build_failure = None
    else:
        if p.exists():
            # --force MEANS BUILD IT AGAIN, and building again into a populated prefix is not
            # that: it would leave every package the PREVIOUS lock pulled and the current one does
            # not. The environment would then hold more than the lock describes while carrying a
            # fingerprint saying it came from that lock, which is the exact failure this file
            # exists to prevent.
            #
            # The name is checked before anything is removed. `env_prefix` always produces it, so
            # the check never fires today; it is here so a future caller passing some other path
            # cannot turn --force into an rmtree of it.
            expected = {ENV_DIRNAME.format(kernel=kernel.name)}
            if grp is not None:
                expected.add(grp.name)
            if p.name not in expected or p.is_symlink() or not p.is_dir():
                raise RuntimeError(
                    f"refusing to remove {p} for a --force rebuild: it is not a directory named "
                    f"{' or '.join(sorted(expected))!r}. Remove it yourself if that is what you "
                    f"meant.")
            log(f"  --force: removing {p} first, so the rebuild cannot inherit packages the "
                f"current lock does not name")
            shutil.rmtree(p)
        m = machine(log=log)
        mgr = (shutil.which("micromamba") or shutil.which("mamba") or shutil.which("conda"))
        if not mgr and spec["conda"] and m["pythons"]:
            # ADAPT RATHER THAN REFUSE. A lock whose conda section is only the interpreter can be
            # built as a venv on a machine with no conda at all - and saying so beats telling a
            # new user to install a package manager they do not need.
            log(f"  no conda manager, but this lock's conda packages are {spec['conda']}; "
                f"attempting a venv at python {spec['python']}")
        venv_py = _venv_python(spec["python"]) if not spec["conda"] else None
        if mgr:
            # `create`, never `env create`: it takes -y on every conda anyone still runs.
            # --override-channels: the lock NAMES its channels, so whatever is in the user's
            # ~/.condarc must not join the solve. Without it the same lock can build differently
            # on two machines depending on which channels each had configured, which is the one
            # thing a lock exists to stop. It matters most for the R lock, where `defaults`
            # carries its own r-base and a mixed solve is how an r-* package ends up built
            # against a different R than the one pinned.
            cmd = [mgr, "create", "-y", "--override-channels", "-p", str(p)]
            for c in (spec["channels"] or ["conda-forge"]):
                cmd += ["-c", c]
            # An R lock need not pin python at all, and asking conda for `python=None pip` would
            # be this installer inventing a dependency the lock does not declare.
            if spec["python"]:
                cmd += [f"python={spec['python']}", "pip"]
            cmd += spec["conda"]
            log(f"  interpreter: {mgr} -> "
                + (f"python {spec['python']}" if spec["python"] else "no python pin (r lock)")
                + (f" + {len(spec['conda'])} conda package(s)" if spec["conda"] else ""))
            subprocess.run(cmd, check=True)
        elif venv_py:
            log(f"  interpreter: {venv_py} (venv; this lock needs no conda packages)")
            subprocess.run([venv_py, "-m", "venv", str(p)], check=True)
        else:
            want = f"python{spec['python']}"
            raise RuntimeError(
                f"cannot build {kernel.name}: no micromamba, mamba or conda on PATH"
                + (f", and no {want} either" if not spec["conda"] else
                   f" (and this lock needs conda packages {spec['conda']}, so a venv will not do)")
                + ".\n"
                f"  Either: put one on PATH - on a cluster that is usually `module load anaconda3`\n"
                f"  Or:     build the environment yourself from {kernel.path / 'lock.yml'} and set\n"
                f"          SCPROFILE_{kernel.name.upper()}_PYTHON=/path/to/that/env/bin/python\n"
                f"          `doctor` will report that route, so nothing is ambiguous.")

        pip = p / "bin" / "pip"
        # A FAILURE HERE STILL PROVES WHAT IT CAN. Any of these steps can fail, and the
        # environment is then NOT built - no stamp is written, so nothing treats it as one - but
        # the members whose half of it did install can still be run, and running them costs a
        # minute against a build that costs an hour.
        #
        # Measured on an eight-member group whose R step failed on a forgotten dependency: the
        # pip half, 130 packages and 25 minutes, was complete, and eight selftests would have
        # taken about a minute. Instead `install` raised, `doctor` reported all eight stale, and
        # the job ended knowing nothing about any of them. That is one defect learned per job for
        # however many defects there are, which on a first build of eight plugins is the cycle.
        build_failure = None
        try:
            if spec["pip"]:
                # ONE resolve, all pins together. Installing them in sequence lets a later
                # package quietly downgrade an earlier pin, and the environment then does not
                # match the lock that the fingerprint says it was built from.
                log(f"  applying {len(spec['pip'])} pinned package(s) in one resolve")
                subprocess.run([str(pip), "install", "--no-input"] + spec["pip"], check=True)
            if spec["r"]:
                _install_r(p, spec["r"], log=log)
        except Exception as e:                                            # noqa: BLE001
            build_failure = e
            log(f"\n  BUILD FAILED: {e}")
            log("  The environment is NOT built and no stamp is written, so nothing will treat "
                "it as one. Every member's selftest still runs below, because what the finished "
                "half of this environment can prove is worth more than a second job to find out.")
        else:
            (p / ".scprofile_lock").write_text(env_fingerprint(kernel, grp), encoding="utf-8")

    # PROVE IT FOR EVERY MEMBER. An environment shared by four plugins and proved by one is an
    # environment three of them meet for the first time inside a run - and the whole reason
    # `install` ends in a selftest is that an environment nothing proved fails there instead.
    #
    # A member whose selftest fails does not make this a partial success: the directory's name is
    # a claim to satisfy every member's requirement, so it is not built until it does.
    from .kernels import discover
    known = {kernel.name: kernel}
    for n, k in discover().items():
        known.setdefault(n, k)
    proved, unproved, failed = [], [], []
    for m in members:
        mk = known.get(m)
        if mk is None:
            unproved.append(f"{m} (not discoverable from here)")
            continue
        try:
            if selftest(mk, prefix=prefix, log=log):
                proved.append(m)
            else:
                unproved.append(f"{m} (ships none)")
        except RuntimeError as e:                                         # noqa: PERF203
            failed.append(m)
            log(f"  {m}: SELFTEST FAILED\n{e}")
    if len(members) > 1:
        log(f"  proved for {len(proved)} of {len(members)} member(s): "
            + (", ".join(proved) or "none")
            + (f";  unproven: {', '.join(unproved)}" if unproved else ""))
    if build_failure is not None:
        raise RuntimeError(
            f"{p} was NOT built: {build_failure}\n"
            f"  The selftests above ran against a HALF-BUILT environment and are diagnostic, not "
            f"a claim that it works: {len(proved)} of {len(members)} member(s) could run there "
            f"anyway"
            + (f", and {', '.join(failed)} could not" if failed else "")
            + ".\n  Fix what the build step named above, then install again with --force.")
    if failed:
        raise RuntimeError(
            f"{p} was built, and {', '.join(failed)} could not run in it. A shared environment "
            f"is not built until every plugin that resolves to it can run there - the directory's "
            f"name is a claim about all {len(members)}, not about the one that was asked for.")
    return p


#: How long a selftest may take before it is called a failure. A selftest proves a CALL is
#: well-formed; it is seconds to a few minutes by construction, and one that runs longer than
#: this is not slow, it is stuck. Measured: decoupler's fetches a published prior over the
#: network, and on a compute node with no route out it blocked with no output and no timeout -
#: `install` would have sat there until the job's walltime, sixteen hours, having proved nothing
#: and reported nothing.
SELFTEST_TIMEOUT = 1800


def selftest(kernel, *, prefix=None, log=print, timeout=None):
    """Run a plugin's selftest with THAT PLUGIN'S OWN INTERPRETER. Raises if it fails.

    Two reasons this is not just an install step. An environment DRIFTS - a shared conda prefix
    gets updated, a system library moves - and the selftest is the only thing that would notice;
    an install-time-only check answers "did it work in June". And a plugin with `needs_env: false`
    has no install step at all, so its selftest would otherwise never run automatically, which is
    exactly how a forbidden keyword reached a real cohort.

    Returns True if it ran, False if the plugin ships no selftest.
    """
    # THE KERNEL ANSWERS. This looked for `kernel.path / "selftest.py"`, which for a ONE-FILE
    # plugin is a path inside a file and can never exist - so every one-file plugin was reported
    # as shipping no selftest, and the one check that would have caught the launch bug above was
    # skipped for exactly the shape that had it.
    if not kernel.has_selftest:
        return False
    exe, why = interpreter(kernel, prefix)
    if not exe:
        raise RuntimeError(f"{kernel.name}: no interpreter to run its selftest with. {why}")
    cmd = kernel.selftest_argv(exe)
    limit = SELFTEST_TIMEOUT if timeout is None else timeout
    # TO A FILE, NOT TO A PIPE, and the file is named. `capture_output` holds everything until the
    # process exits, so a selftest that is waiting on a network call prints nothing and is
    # indistinguishable from one that has hung - which is the same lesson `run` learned when a
    # plugin that takes an hour and prints nothing looked like a plugin that had stopped. Here it
    # was not hypothetical: decoupler's selftest blocked on a published prior it fetches, with no
    # output and no timeout, and there was nothing to look at while it did.
    logf = Path(exe).resolve().parent.parent / f".scprofile_selftest_{kernel.name}.log"
    log(f"  selftest: {Path(cmd[-1]).name}  ({why})")
    log(f"      live: {logf}")
    try:
        with open(logf, "w", encoding="utf-8") as fh:
            r = subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT, timeout=limit,
                               env=with_env_bin(exe))
    except subprocess.TimeoutExpired:
        tail = "".join(logf.read_text(encoding="utf-8", errors="replace").splitlines(True)[-15:])
        raise RuntimeError(
            f"{kernel.name}'s selftest did not finish within {limit}s, so nothing has proved this "
            f"environment. A selftest proves a CALL is well-formed and is seconds to minutes by "
            f"construction; one that runs longer is stuck, not slow - a fetch with no route out "
            f"is the usual reason.\n  Last lines of {logf.name}:\n{tail}") from None
    out = logf.read_text(encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(
            f"{kernel.name}'s selftest FAILED, so the environment is not usable:\n" + out)
    # Print it on SUCCESS too. "selftest ok" tells you a check passed and not which versions it
    # passed against, and the versions are the thing anyone debugging this later needs - a lock is
    # a claim about an environment, and this is the receipt.
    for line in out.splitlines():
        log(f"    {line}")
    log("  selftest ok")
    return True


def run(kernel, *, inp, out_dir, prefix=None, log=print, timeout=None):
    """Run one kernel. Returns its validated output manifest, or raises with what went wrong.

    The kernel's stdout and stderr are streamed to a log file in its own output directory - not
    captured and discarded - because a kernel that takes an hour and prints nothing readable is
    indistinguishable from one that has hung.
    """
    exe, src = interpreter(kernel, prefix)
    if not exe:
        raise RuntimeError(f"{kernel.name}: {src}")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    # THE KERNEL SAYS HOW IT IS LAUNCHED. The runner used to build `[exe, path/entry, inp]`
    # itself, which is right for the directory shape and silently wrong for every other. A
    # one-file plugin has no `main()` - the whole point of the shape is that `_entry.py` does the
    # argument parsing, the contract and the manifest once for everybody - so handing the file to
    # an interpreter DEFINES TWO NAMES, EXITS 0 AND WRITES NOTHING. The host can only report that
    # as a missing out.json, which is what the first third-party plugin to reach a real run did.
    cmd = kernel.argv(exe, inp)
    for part in cmd[1:-1]:
        if not Path(part).exists():
            raise FileNotFoundError(f"{kernel.name} is launched via {part}, which is absent")
    log(f"  interpreter: {exe}  ({src})")
    log(f"  running: {' '.join(cmd[1:])}", )
    logf = out / f"{kernel.name}.log"
    # THE SHARE, AS AN ENVIRONMENT VARIABLE TOO. `in.json` tells the plugin its share and the
    # plugin honours it for what it schedules itself; numpy's BLAS sizes its pool from
    # OMP_NUM_THREADS at import, before the plugin exists. Read from the manifest that was just
    # written, so there is exactly one statement of the share and the two cannot disagree.
    import json as _json
    _cores = ((_json.loads(Path(inp).read_text(encoding="utf-8")).get("resources") or {})
              .get("cores"))
    with open(logf, "w", encoding="utf-8") as fh:
        r = subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT,
                           env=with_env_bin(exe, manifest.env_for_kernel(inp, cores=_cores)),
                           timeout=timeout)
    if r.returncode != 0:
        tail = "".join(logf.read_text(encoding="utf-8", errors="replace").splitlines(True)[-15:])
        raise RuntimeError(
            f"{kernel.name} exited {r.returncode}. Last lines of {logf.name}:\n{tail}")
    payload = manifest.read_output(out)
    extra = manifest.unknown_keys(payload)
    if extra:
        log(f"  note: {kernel.name} declared key(s) the host does not act on: {extra}")
    return payload
