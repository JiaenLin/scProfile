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


def env_prefix(kernel_name, prefix):
    return Path(prefix).expanduser() / ENV_DIRNAME.format(kernel=kernel_name)


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
        p = env_prefix(kernel.name, prefix)
        exe = p / "bin" / ("Rscript" if kernel.language == "r" else "python")
        if exe.exists():
            return str(exe), f"installed at {p}"
        return None, (f"no environment at {p}.  Fix: scprofile install {kernel.name} "
                      f"--prefix {prefix}")
    return None, (f"no --prefix given and no $SCPROFILE_{kernel.name.upper()}_PYTHON set.  "
                  f"Fix: scprofile install {kernel.name} --prefix <dir>, or set the variable.")


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


def env_state(kernel, prefix=None):
    """`installed` / `missing` / `stale` / `override` / `host`, with a sentence and a fix."""
    over, src = config_override(kernel.name)
    if over:
        return ("override", f"{src} -> {over}", "")
    if not kernel.needs_env:
        return ("host", "runs in the host interpreter", "")
    if not prefix:
        return ("missing", "no --prefix given",
                f"scprofile install {kernel.name} --prefix <dir>")
    p = env_prefix(kernel.name, prefix)
    exe = p / "bin" / ("Rscript" if kernel.language == "r" else "python")
    if not exe.exists():
        return ("missing", f"nothing at {p}", f"scprofile install {kernel.name} --prefix {prefix}")
    stamp = p / ".scprofile_lock"
    want = lock_fingerprint(kernel)
    got = stamp.read_text(encoding="utf-8").strip() if stamp.exists() else ""
    if want and got != want:
        return ("stale", f"built from lock {got or 'unknown'}, current lock is {want}",
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


def install(kernel, prefix, *, force=False, log=print):
    """Build a kernel's environment from its lock, then prove it with its own selftest.

    A selftest that runs at INSTALL time is the difference between finding out now and finding out
    after the models have trained. It is the kernel's own file, because only the kernel knows what
    importing successfully means for it.

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
    if not (kernel.path / "lock.yml").exists():
        raise FileNotFoundError(
            f"{kernel.name} needs an environment and has no {kernel.path / 'lock.yml'}, so there "
            f"is nothing to build from. It is `status: {kernel.status}`.\n"
            + ("  A planned plugin is a DECLARATION - its prerequisites are real and checkable "
               "and its implementation does not exist. `scprofile scaffold " + kernel.name
               + "` writes the skeleton, including the lock.\n"
               if kernel.status != "built" else "")
            + f"  A lock is captured from a resolve that WORKS, every line pinned; do not write "
              f"one from memory.")
    p = env_prefix(kernel.name, prefix)
    spec = lock_spec(kernel)
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
        state, detail, fix = env_state(kernel, prefix)
        if state != "installed":
            raise RuntimeError(
                f"{p} exists but is {state}: {detail}." + "\n"
                "  It is not an environment this lock describes, so nothing here will treat it as "
                "one. A partial build leaves a directory that looks finished from the outside, "
                "which is why this refuses rather than carrying on to the selftest.\n"
                f"  Fix: {fix or f'scprofile install {kernel.name} --prefix {prefix} --force'}")
        log(f"  {p} exists and matches the current lock. Pass --force to rebuild.")
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
            expected = ENV_DIRNAME.format(kernel=kernel.name)
            if p.name != expected or p.is_symlink() or not p.is_dir():
                raise RuntimeError(
                    f"refusing to remove {p} for a --force rebuild: it is not a directory named "
                    f"{expected!r}. Remove it yourself if that is what you meant.")
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
        if spec["pip"]:
            # ONE resolve, all pins together. Installing them in sequence lets a later package
            # quietly downgrade an earlier pin, and the environment then does not match the lock
            # that the fingerprint says it was built from.
            log(f"  applying {len(spec['pip'])} pinned package(s) in one resolve")
            subprocess.run([str(pip), "install", "--no-input"] + spec["pip"], check=True)
        if spec["r"]:
            _install_r(p, spec["r"], log=log)
        (p / ".scprofile_lock").write_text(lock_fingerprint(kernel), encoding="utf-8")

    selftest(kernel, prefix=prefix, log=log)
    return p


def selftest(kernel, *, prefix=None, log=print, timeout=None):
    """Run a plugin's selftest with THAT PLUGIN'S OWN INTERPRETER. Raises if it fails.

    Two reasons this is not just an install step. An environment DRIFTS - a shared conda prefix
    gets updated, a system library moves - and the selftest is the only thing that would notice;
    an install-time-only check answers "did it work in June". And a plugin with `needs_env: false`
    has no install step at all, so its selftest would otherwise never run automatically, which is
    exactly how a forbidden keyword reached a real cohort.

    Returns True if it ran, False if the plugin ships no selftest.
    """
    st = kernel.path / "selftest.py"
    if not st.exists():
        st = kernel.path / "selftest.R"
    if not st.exists():
        return False
    exe, why = interpreter(kernel, prefix)
    if not exe:
        raise RuntimeError(f"{kernel.name}: no interpreter to run its selftest with. {why}")
    log(f"  selftest: {st.name}  ({why})")
    r = subprocess.run([exe, str(st)], capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(
            f"{kernel.name}'s selftest FAILED, so the environment is not usable:\n"
            + (r.stdout or "") + (r.stderr or ""))
    # Print it on SUCCESS too. "selftest ok" tells you a check passed and not which versions it
    # passed against, and the versions are the thing anyone debugging this later needs - a lock is
    # a claim about an environment, and this is the receipt.
    for line in (r.stdout or "").splitlines():
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
    entry = kernel.path / kernel.entry
    if not entry.exists():
        raise FileNotFoundError(f"{kernel.name} declares entry {kernel.entry!r}, which is absent")

    cmd = [exe, str(entry), str(inp)]
    log(f"  interpreter: {exe}  ({src})")
    log(f"  running: {' '.join(cmd[-2:])}", )
    logf = out / f"{kernel.name}.log"
    with open(logf, "w", encoding="utf-8") as fh:
        r = subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT,
                           env=manifest.env_for_kernel(inp), timeout=timeout)
    if r.returncode != 0:
        tail = "".join(logf.read_text(encoding="utf-8", errors="replace").splitlines(True)[-15:])
        raise RuntimeError(
            f"{kernel.name} exited {r.returncode}. Last lines of {logf.name}:\n{tail}")
    payload = manifest.read_output(out)
    extra = manifest.unknown_keys(payload)
    if extra:
        log(f"  note: {kernel.name} declared key(s) the host does not act on: {extra}")
    return payload
