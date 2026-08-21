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

#: An `r:` entry is `owner/repo@<commit>`. A tag or a branch is not a pin - a branch moves and a
#: tag can be re-pointed - so the commit is required and checked here rather than hoped for.
R_PIN = re.compile(r"^[\w.-]+/[\w.-]+@[0-9a-f]{40}$")


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
    rather than assumed: PBS 676308 asked the channels, and it is on neither conda-forge nor
    bioconda. The two personal channels carrying it are a two-year-old linux-64 build and a
    macOS-arm64 one, which is not something another site could reproduce.

    `r:` is therefore a list of `owner/repo@<40-char commit>`, applied by ONE
    `remotes::install_github` call with `upgrade = "never"` and `dependencies = FALSE`. The
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
            if not R_PIN.match(item):
                raise ValueError(
                    f"{f}: r entry {item!r} is not `owner/repo@<40-char commit>`. A tag or a "
                    f"branch is not a pin - a branch moves and a tag can be re-pointed - and the "
                    f"whole point of this section is that the same lock builds the same package.")
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


def _install_r(p, entries, log=print):
    """Apply the lock's `r:` section: ONE install_github call, every pin together.

    Three things here are deliberate and each is the R spelling of something the pip path already
    does.

    `upgrade = "never"`  - remotes' default is to offer to update every dependency it finds out of
                           date, which on a conda-built library means silently replacing packages
                           the conda section pinned. The lock would then describe an environment
                           that no longer exists.
    `dependencies=FALSE` - every dependency comes from the pinned conda section. Letting remotes
                           fetch a missing one installs an UNPINNED package that nothing recorded,
                           and it would work, which is what makes it dangerous. A dependency that
                           was forgotten instead fails to load in the selftest, by name.
    one call             - installed one at a time, a later package re-resolves an earlier one.

    `withr`-free on purpose: `.libPaths()` inside a conda prefix's own Rscript already points at
    that prefix's library, so nothing here needs to redirect it. The install is verified by asking
    R for the installed commit back, because `install_github` reports success for a build that
    produced no loadable package often enough to be worth checking.
    """
    rscript = p / "bin" / "Rscript"
    if not rscript.exists():
        raise RuntimeError(
            f"the lock has an `r:` section but there is no Rscript at {rscript}. Add `r-base=` to "
            f"its dependencies - the conda step builds the interpreter that this step then uses.")
    repos = ", ".join(f'"{e}"' for e in entries)
    log(f"  applying {len(entries)} pinned R package(s) from git, in one resolve")
    for e in entries:
        log(f"    {e}")
    script = (
        'if (!requireNamespace("remotes", quietly = TRUE)) '
        'stop("remotes is not installed. Add r-remotes= to the conda dependencies: this step '
        'needs it, and installing it here would be an unpinned package the lock never declared.")\n'
        f'remotes::install_github(c({repos}), upgrade = "never", dependencies = FALSE, '
        'force = TRUE, quiet = FALSE)\n'
        # The receipt. A package directory with no DESCRIPTION, or one whose RemoteSha is not the
        # commit that was asked for, is an install that reported success and did not happen.
        f'for (spec in c({repos})) {{\n'
        '  pkg <- sub("@.*", "", sub(".*/", "", spec)); want <- sub(".*@", "", spec)\n'
        '  if (!requireNamespace(pkg, quietly = TRUE)) stop(sprintf('
        '"%s installed without error and cannot be loaded", pkg))\n'
        '  got <- utils::packageDescription(pkg)$RemoteSha\n'
        '  if (is.null(got) || substr(got, 1, 40) != want) stop(sprintf('
        '"%s is at %s, the lock asked for %s", pkg, got, want))\n'
        '  cat(sprintf("    %s %s @ %s\\n", pkg, utils::packageVersion(pkg), substr(want, 1, 7)))\n'
        '}\n')
    subprocess.run([str(rscript), "-e", script], check=True)


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
        log(f"  {p} exists. Pass --force to rebuild.")
    else:
        mgr = (shutil.which("micromamba") or shutil.which("mamba") or shutil.which("conda"))
        venv_py = _venv_python(spec["python"]) if not spec["conda"] else None
        if mgr:
            # `create`, never `env create`: it takes -y on every conda anyone still runs.
            cmd = [mgr, "create", "-y", "-p", str(p)]
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
