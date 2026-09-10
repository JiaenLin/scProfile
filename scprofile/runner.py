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
import time
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
            # BUILT IS NOT PROVED, AND THIS PLUGIN IS THE ONE BEING ASKED ABOUT. The directory
            # can be complete, current and shared by seven plugins and still be an environment
            # nothing has ever run THIS one in - which is the case `install` used to prevent by
            # refusing to finish until every member passed, and now prevents here instead. The
            # word is `missing` rather than a sixth state because the vocabulary is read by
            # `doctor`, by `plan` and by `planner.build_state`, and a state they have not been
            # taught is a KeyError in one of them and silence in another; what is missing is the
            # proof that this environment is this plugin's, and the repair `missing` names is the
            # cheap one - an install that re-proves a member, not a --force that rebuilds a
            # shared environment for everybody.
            if st[0] == "installed":
                ps, pwhy, pfix = proof_state(kernel, prefix)
                if ps in UNPROVED:
                    # AND WHAT THE SELFTEST SAID, HERE ONLY. `doctor` and `plan` print this
                    # sentence and nothing classifies it; `run` raises its own, which
                    # `feedback.diagnose` reads - see the note in `proof_state` for why a
                    # recorded `ImportError` must not travel into that path.
                    said = read_proof(proof_home(kernel, prefix) or p, kernel.name).get("why", "")
                    return ("missing", pwhy + (f"  It said: {said}" if said else ""), pfix)
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


# ------------------------------------------------------------------ the proof, one per member
#
# WHY A PER-MEMBER RECORD AND NOT A GROUP CLAIM
#
# The safety property has not changed and is not negotiable: an environment shared by four
# plugins and proved by one is an environment three of them meet for the first time inside a run.
# What changed is WHERE it is enforced, and the reason is a measurement.
#
# Reproduced on the cluster: `install liana` into scprofile-env-0242f5f3d1 ran all seven members'
# selftests. liana PASSED. The job still failed, because abundance hit a pertpy/statsmodels
# ImportError that is not liana's to fix and de and decoupler were SIGKILLed by the node. Three
# plugins nobody had asked about sank the one that was asked for, and the environment liana can
# demonstrably run in was reported as not built. A group claim can only ever be all-or-nothing,
# so the one member with a real answer is worth exactly as much as the worst member's.
#
# So the verdict is recorded PER MEMBER, beside the environment it is about, and the refusal
# moves to the point of use: `run` and `plan` refuse the plugin whose own record is absent,
# stale or failed, by name, with the command that would prove it. Nobody meets an unproved
# environment inside a run, and nobody is sunk by somebody else's plugin.
#
# `.scprofile_selftest_<name>.log` already says what a selftest PRINTED. This says what it
# CONCLUDED and what it concluded it about, which is the half a log cannot carry.
PROOF_NAME = ".scprofile_proof_{kernel}"

#: The recorded states that must stop a plugin being run or planned. `unrecorded` - an
#: environment carrying no record for ANYONE - is deliberately not among them, and it is the one
#: judgement call here. Absence of the whole record is absence of evidence: every environment
#: built before this file existed carries none, and refusing them all would invalidate every
#: installation on disk for a reason its owner did not cause - the same rule `resolved_prefix`
#: and `env_state` already follow one function up. Absence of ONE record among several IS
#: evidence of absence: this host writes a record for every member it proves, so a member with
#: none in an environment that has them is a member that install did not prove. The first
#: install after this change records every member, which closes the gap where it matters.
UNPROVED = ("failed", "stale", "absent")


def env_home(exe):
    """The environment an interpreter BELONGS TO: the directory its `bin/` sits in.

    THE PREFIX THE INTERPRETER WAS FOUND AT, NOT THE ONE IT POINTS AT. This was
    `Path(exe).resolve().parent.parent` in both callers below, and on a CONDA-built environment
    those are the same directory: `bin/python` is a symlink to `bin/python3.11` lying beside it,
    so resolving the executable stays inside the prefix and the old expression was right by
    accident. On a VENV-built environment they are not the same directory at all. `python -m
    venv` makes `bin/python` a symlink to the interpreter it was built FROM, so resolving walks
    straight out of the environment into the base python's prefix. Measured on this host, on the
    venv route `install` takes whenever no conda-family manager is on PATH (see `machine`):

        <prefix>/scprofile-env-0242f5f3d1/bin/python
            -> /Library/Developer/.../Python3.framework/Versions/3.9/bin/python3.9
        .resolve().parent.parent = /Library/Developer/.../Versions/3.9   <- NOT the environment

    That INVERTED the property this whole section exists to defend, and it did so in two
    different ways depending on one thing the host does not control - whether the base python's
    prefix happens to be writable:

      - WRITABLE base (a pyenv, a homebrew python, a `module load`ed one on the cluster - all of
        them user-owned): the record is written outside the environment, so it survives
        `rm -rf <env>` and every rebuild after it. The environment the proof is a claim about is
        gone, the record is still there, its fingerprint still matches because the group name is
        content-addressed, and `proof_state` reads it as `proved`. That is precisely the
        stale-proof-accepted-as-fresh failure the fingerprint was added to prevent, arriving
        through the one path the fingerprint cannot see. Worse, that one directory is shared by
        EVERY venv on the machine built from that base python, so a proof earned under one
        --prefix answers for a different --prefix where nothing has ever run.
      - READ-ONLY base (a system python, which is the common case and the one measured above):
        `record_proof` cannot write at all. It never raises - deliberately - so every install
        succeeds, every member stays `unrecorded`, `unrecorded` is deliberately NOT in `UNPROVED`,
        and `run` and `plan` stop refusing anybody. The safety property is simply off.

    Taking the parent of the `bin/` the interpreter was FOUND in gives the same answer as before
    on the conda route and the right one on the venv route, so the proof lives with the
    environment it is a claim about on every build path this host supports. The DIRECTORY is
    resolved and the executable is not: a prefix reached through a symlinked path (`/tmp` ->
    `/private/tmp` on macOS, a symlinked scratch on the cluster) still writes and reads one record
    in one place, which is the only thing `.resolve()` was ever needed for here.
    """
    p = Path(exe)
    try:
        return p.parent.parent.resolve()
    except OSError:                        # a resolve can still fail on a broken mount
        return p.parent.parent


def proof_home(kernel, prefix=None):
    """The directory this member's proof record lives in, or None if there is nowhere for one.

    DERIVED FROM THE INTERPRETER, exactly as the selftest log is - and through the SAME function,
    so a record cannot be written beside one environment and read beside another. That is the bug
    `env_state` and `interpreter` already had once, in this file, about this question, and it came
    back here as two copies of one expression that were only ever correct on one build route.

    A site override is a real environment and gets a record where it lives. A plugin running in
    the HOST interpreter has no environment of its own, and writing a stamp into whatever prefix
    `sys.executable` happens to sit in is not this tool's to do.
    """
    if not kernel.needs_env:
        return None
    exe, _why = interpreter(kernel, prefix)
    if not exe:
        return None
    return env_home(exe)


def read_proof(home, name):
    """One member's recorded verdict as a dict, or {} when there is no record."""
    f = Path(home) / PROOF_NAME.format(kernel=name)
    try:
        text = f.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    out = {}
    for line in text.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def any_proof(home):
    """Whether this environment carries a record for ANYONE. See `UNPROVED`."""
    try:
        return any(Path(home).glob(PROOF_NAME.format(kernel="*")))
    except OSError:
        return False


def record_proof(kernel, prefix=None, *, verdict, why="", log=None):
    """Write what this member's selftest concluded, and what it concluded it about.

    NEVER RAISES. A record that could not be written is not an install that failed - a site
    override can live in a read-only tree, and a disk can be full - so this reports and returns
    None rather than turning the absence of a receipt into the absence of the thing.

    The fingerprint is the environment's own, the same value `.scprofile_lock` carries: a
    content-addressed group name, or the lock digest for a plugin building alone. NOT the
    plugin's source, deliberately - a proof is a claim about an ENVIRONMENT, and re-proving every
    member on every prose edit to a plugin would make the record noise, which is the failure
    `jobs/inventory_all.pbs` Q1 is written to catch one layer up.
    """
    home = proof_home(kernel, prefix)
    if home is None:
        return None
    grp, _gp = env_for(kernel, prefix) if prefix else (None, None)
    f = Path(home) / PROOF_NAME.format(kernel=kernel.name)
    body = [f"verdict={verdict}",
            f"fingerprint={env_fingerprint(kernel, grp)}",
            f"when={time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}"]
    if why:
        # ONE LINE, and the log holds the rest. A record nobody can read at a glance is a record
        # that gets skipped, and the whole file already sits beside the full log.
        body.append("why=" + " ".join(str(why).split())[:300])
    try:
        f.write_text("\n".join(body) + "\n", encoding="utf-8")
    except OSError as e:                                                  # noqa: BLE001
        if log:
            log(f"  note: could not record {kernel.name}'s verdict at {f}: {e}")
        return None
    return f


def proof_state(kernel, prefix=None):
    """Has this environment been proved FOR THIS PLUGIN? A state, a sentence and a fix.

        proved      a record, matching this environment's fingerprint, saying its selftest passed
        none        the plugin ships no selftest, so this is as proved as it can be
        failed      a record saying its selftest did not pass here. Refused.
        stale       a record made against a different environment than the one now here. Refused.
        absent      no record for this member, in an environment that carries records for others.
                    Refused - see `UNPROVED` for why this is not the same as `unrecorded`.
        unrecorded  this environment carries no record for anyone: it predates them, or was built
                    by hand. Not refused, and said out loud rather than assumed away.
        na          there is nothing to ask - no prefix, no interpreter, or a plugin that runs in
                    the host interpreter and has no environment to prove.
    """
    home = proof_home(kernel, prefix)
    if home is None:
        return ("na", f"{kernel.name}: no environment of its own to prove", "")
    fix = (f"scprofile install {kernel.name} --prefix {prefix}"
           if prefix else f"scprofile selftest {kernel.name}")
    rec = read_proof(home, kernel.name)
    if not rec:
        if not any_proof(home):
            return ("unrecorded", f"{home} carries no proof record for any of its members; it "
                                  f"was built before they existed or by hand", fix)
        others = sorted(p.name.split(PROOF_NAME.format(kernel=""), 1)[-1]
                        for p in Path(home).glob(PROOF_NAME.format(kernel="*")))
        return ("absent",
                f"{home} is built and has never been proved for {kernel.name}. It records "
                f"{len(others)} other member(s) ({', '.join(others[:6])}), so this one was not "
                f"skipped by an older host - nothing has run {kernel.name} there at all",
                fix)
    grp, _gp = env_for(kernel, prefix) if prefix else (None, None)
    want = env_fingerprint(kernel, grp)
    got = rec.get("fingerprint", "")
    if want and got != want:
        return ("stale",
                f"{home} was proved for {kernel.name} against {got or 'something unrecorded'}, "
                f"and the environment it would run in now is {want}. A proof of one environment "
                f"is not a proof of another",
                fix)
    verdict = rec.get("verdict", "")
    if verdict == "ok":
        when = rec.get("when") or "an unrecorded date"
        return ("proved", f"{home}, proved for {kernel.name} on {when}", "")
    if verdict == "none":
        return ("none", f"{kernel.name} ships no selftest, so nothing can prove {home} for it",
                "")
    # WHAT IT SAID IS NOT IN THIS SENTENCE, and that is deliberate. `run` raises this text and
    # `feedback.diagnose` classifies whatever `run` raises: a recorded `ImportError: cannot
    # import name ...` quoted here matches the ENVIRONMENT signature, which is marked REPAIRABLE,
    # and the run loop's repair edge is a `--force` rebuild - hours of solving for a seven-member
    # environment, triggered by a refusal whose whole point is that a selftest costs a minute.
    # The record and the log are named instead, and `env_state` - which nothing diagnoses -
    # appends the reason for `doctor` and `plan`.
    return ("failed",
            f"{home} is built, and {kernel.name}'s own selftest FAILED there"
            + (f" on {rec['when']}" if rec.get("when") else "")
            + f".  Recorded in {PROOF_NAME.format(kernel=kernel.name)}; what it printed is in "
              f".scprofile_selftest_{kernel.name}.log, both beside the environment",
            fix)


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


def _accepts_solver_flag(mgr: str) -> bool:
    """Whether this manager's `create` accepts `--solver`. ASKED, not inferred from a version.

    conda grew `--solver` in 22.11 and made libmamba its default in 23.10, but the mapping has
    exceptions - a distribution can ship the flag without the plugin, or the plugin without
    having it as the default - and a version string is not the question anyway. The question is
    whether this binary takes the flag, so put it to the binary.
    """
    try:
        h = subprocess.run([mgr, "create", "--help"], capture_output=True, text=True, timeout=60)
    except Exception:
        return False
    return "--solver" in (h.stdout or "") + (h.stderr or "")


def _conda_solve(cmd: list, mgr: str, n_conda: int, *, log=print) -> None:
    """Run the create, on the fast solver where one is available, and SAY when it is not.

    THE CLASSIC CONDA SOLVER IS THE SLOWEST THING IN THIS INSTALLER, by a margin nothing else
    comes close to. A lock naming the bioconductor stack can sit in `Solving environment:` for
    hours, and conda prints a spinner rather than progress - so from outside, and from a job log
    afterwards, IT IS INDISTINGUISHABLE FROM A HANG. Someone watching it kills the job, and the
    thing that was working gets recorded as the thing that broke. That is worth a sentence.

    micromamba and mamba do not have the problem, which is why they are preferred over conda
    where they exist. Where they do not, a modern conda can be pointed at the same solver.

    THE FAST PATH IS ATTEMPTED, NEVER ASSUMED. `--solver=libmamba` fails in seconds when the
    plugin is absent - an argument or plugin error, not a wasted solve - so falling back to the
    plain command costs nothing and cannot lose a build. A retry that could cost hours would not
    be worth it; this one is free, which is what makes it the right shape.
    """
    fast = None
    if Path(mgr).name.startswith("conda") and n_conda and _accepts_solver_flag(mgr):
        fast = cmd + ["--solver=libmamba"]
    def _timed(c, what):
        """Run it, and report how long it took. A DURATION IS A MEASUREMENT; an estimate is not.

        This is the number the warning above refuses to guess at, and the one a reader deciding
        whether a future run has hung actually needs - from this machine, this manager, this lock.
        """
        t0 = time.monotonic()
        try:
            subprocess.run(c, check=True)
        finally:
            log(f"  {what} took {time.monotonic() - t0:.0f}s")

    if fast is not None:
        log(f"  solver: libmamba (this conda accepts --solver; {n_conda} conda packages)")
        try:
            _timed(fast, "the libmamba solve and create")
            return
        except subprocess.CalledProcessError as exc:
            log(f"  --solver=libmamba was accepted as a flag but the solve failed "
                f"(exit {exc.returncode}); retrying on this conda's default solver")
    elif Path(mgr).name.startswith("conda") and n_conda >= 20:
        log(f"  solver: this conda has no --solver flag, so its classic solver will resolve all "
            f"{n_conda} conda packages. It prints a spinner rather than progress, so SILENCE "
            f"HERE IS THE SOLVER WORKING, not a hang. How long it takes is not predictable from "
            f"here and this does not guess - the elapsed time is reported below when it finishes, "
            f"so the next reader has a measurement instead of somebody's estimate.")
        log(f"  micromamba or mamba on PATH avoids the classic solver entirely; both are already "
            f"preferred over conda where they exist.")
    _timed(cmd, f"the solve and create ({n_conda} conda packages)")


def install(kernel, prefix, *, force=False, log=print, dry_run=False):
    """Build the environment this plugin RESOLVES TO, then prove it with every member's selftest.

    A selftest that runs at INSTALL time is the difference between finding out now and finding out
    after the models have trained. It is the kernel's own file, because only the kernel knows what
    importing successfully means for it.

    THE UNIT OF INSTALLATION IS THE RESOLVED ENVIRONMENT, NOT THE PLUGIN. The resolver decides how
    few environments satisfy every plugin's requirement; an environment shared by four of them is
    BUILT once, from the merged requirement - a shared environment is not divisible, and building
    one member's slice into it would leave a directory whose name claims four requirements and
    satisfies one.

    THE UNIT OF PROOF IS THE PLUGIN. An environment that only one of its members has ever run is
    still an environment the other three will discover inside somebody's run - but that is a fact
    about each of those three, and enforcing it as a group claim made abundance's unfixable
    ImportError into liana's failed install (see PROOF_NAME). So the build is shared, the proof is
    per member and recorded, and the refusal happens where the plugin is actually used.

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
        # THE ONES THAT WOULD ACTUALLY RUN, not every member. An install proves the plugin it was
        # asked about plus anyone with no standing record; a member already recorded - passed or
        # failed - is not re-proved by somebody else's install, and a dry run that said otherwise
        # would be describing the version of this function that this one replaced.
        from .kernels import discover as _discover
        _known = dict(_discover())
        _known[kernel.name] = kernel
        would = [n for n in members
                 if n == kernel.name or n not in _known
                 or proof_state(_known[n], prefix)[0] not in ("proved", "none", "failed")]
        log(f"      selftests that would run: {', '.join(would)}"
            + (f"   (already recorded, not re-proved: "
               f"{', '.join(n for n in members if n not in would)})"
               if len(would) < len(members) else ""))
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
            # AND THE MEANS TO REBUILD ARE CHECKED BEFORE ANYTHING IS REMOVED. This used to
            # rmtree first and look for a package manager afterwards, so a job that had not
            # loaded its conda module turned a WORKING environment into no environment at all
            # and then printed a helpful message about what it would have needed. Measured: one
            # from-source R environment, destroyed by a repair job that could not repair.
            #
            # The check is the same one the build makes below, asked early and asked only when
            # the lock actually needs it: a lock with no conda packages builds as a venv and must
            # not be refused for the absence of a manager it will not use.
            _m = machine(log=None)
            _mgr = (shutil.which("micromamba") or shutil.which("mamba")
                    or shutil.which("conda"))
            if spec["conda"] and not _mgr and not _m["pythons"]:
                raise RuntimeError(
                    f"refusing to remove {p} for a --force rebuild: this lock needs conda "
                    f"packages and no micromamba, mamba or conda is on PATH, so the rebuild "
                    f"would fail and leave nothing behind. On a cluster this is usually a "
                    f"missing `module load anaconda3` in the job. The environment is untouched.")
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
            _conda_solve(cmd, mgr, len(spec["conda"]), log=log)
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

    # PROVE THE MEMBER THAT WAS ASKED FOR, AND ANY MEMBER NOTHING HAS PROVED YET.
    #
    # The property being defended has not changed: an environment shared by four plugins and
    # proved by one is an environment three of them meet for the first time inside a run. What
    # changed is that this enforced it as a GROUP CLAIM - every member proved or nobody
    # installed - and a group claim is worth what its worst member is worth.
    #
    # Measured on the cluster: `install liana` here ran seven selftests, liana PASSED, and this
    # function raised because abundance could not import statsmodels through pertpy and de and
    # decoupler were SIGKILLed by the node. The environment liana had just demonstrably run in
    # was reported as not built, to a job that had asked about liana and nothing else.
    #
    # So each member's verdict is RECORDED (see PROOF_NAME) and the refusal moved to `run` and
    # `plan`, which know which plugin is actually being asked for. A member that fails here fails
    # in its own record; it does not sink the member that was asked for, and it cannot be run or
    # planned until something proves it.
    from .kernels import discover
    known = {kernel.name: kernel}
    for n, k in discover().items():
        known.setdefault(n, k)
    # WHAT IS PROVED NOW. The one asked for, always - re-proving it is the whole reason somebody
    # ran this command, and drift is real. Plus every member that has no standing record: an
    # environment nothing has recorded is one where absence means nothing was asked, so the first
    # install after this change still proves the whole group and costs exactly what it did
    # before. A member whose record already says it FAILED is not re-proved for somebody else's
    # install - that is the seven-selftest bill this change exists to stop - and `install <that
    # member>` is what asks the question again.
    to_prove = {kernel.name}
    for m in members:
        if m == kernel.name or known.get(m) is None:
            continue
        if proof_state(known[m], prefix)[0] not in ("proved", "none", "failed"):
            to_prove.add(m)
    proved, unproved, failed, standing = [], [], [], []
    for m in members:
        mk = known.get(m)
        if mk is None:
            unproved.append(f"{m} (not discoverable from here)")
            log(f"  recorded: {m} not discoverable from here, so nothing can prove it")
            continue
        if m not in to_prove:
            # ONE VOCABULARY FOR A VERDICT, whether it was reached a second ago or last week. A
            # reader scanning `recorded:` lines - and `jobs/inventory_all.pbs` puts them in its
            # seal - must not have to know which install produced which word.
            st, _why, _fx = proof_state(mk, prefix)
            standing.append(m)
            log(f"  recorded: {m} "
                + {"proved": "ok", "none": "ships no selftest",
                   "failed": "FAILED"}.get(st, st)
                + f" already - not re-proved by an install asked about {kernel.name}")
            continue
        try:
            if selftest(mk, prefix=prefix, log=log):
                proved.append(m)
                log(f"  recorded: {m} ok")
            else:
                unproved.append(f"{m} (ships none)")
                log(f"  recorded: {m} ships no selftest")
        except RuntimeError as e:                                         # noqa: PERF203
            failed.append(m)
            log(f"  {m}: SELFTEST FAILED\n{e}")
            log(f"  recorded: {m} FAILED - refused at run and plan time by name, not here")
    if len(members) > 1:
        log(f"  proved for {len(proved)} of {len(members)} member(s): "
            + (", ".join(proved) or "none")
            + (f";  unproven: {', '.join(unproved)}" if unproved else "")
            + (f";  already recorded: {', '.join(standing)}" if standing else ""))

    # THE ONE QUESTION A SELFTEST CANNOT ASK. A selftest proves the plugin's own imports resolve
    # in this environment. It says nothing about whether the HOST can hand it an object - and that
    # is a different pair of anndatas, deliberately far apart wherever a plugin is pinned to an
    # older island. `readable_input` handles a mismatch correctly at RUN time, but it asks on the
    # user's object, after the environment is built and the expensive part has started; one
    # recorded instance reported NOT RUN for all ten units of a run. The same question costs under
    # a second on a four-cell object, so it is asked here instead.
    #
    # A WARNING, NOT A REFUSAL. The run-time path can still convert and re-probe, and an
    # environment that cannot take the probe copy may still take the real one - so this reports
    # what it found and lets `install` succeed. What it must not do is stay silent.
    from . import compat
    if kernel.needs_env:
        _exe, _src = interpreter(kernel, prefix)
        ok, why = ((True, f"no interpreter to probe ({_src})") if not _exe
                   else compat.handoff_works(_exe, p / "_probe", log=log))
        if ok:
            log(f"  handoff: {why}")
        else:
            log(f"  handoff: THIS ENVIRONMENT CANNOT READ AN OBJECT THE HOST WRITES")
            log(f"    {why}")
            log(f"    Every plugin is handed an AnnData written by the host's anndata and read "
                f"by this environment's. The run will try a compatibility copy and may still "
                f"succeed, but if it does not, every unit of this plugin reports NOT RUN.")
            log(f"    The environment's requirement is declared in the plugin's `requires`; "
                f"widen its anndata range, or the host's, until they overlap.")
    if build_failure is not None:
        raise RuntimeError(
            f"{p} was NOT built: {build_failure}\n"
            f"  The selftests above ran against a HALF-BUILT environment and are diagnostic, not "
            f"a claim that it works: {len(proved)} of {len(members)} member(s) could run there "
            f"anyway"
            + (f", and {', '.join(failed)} could not" if failed else "")
            + ".\n  Fix what the build step named above, then install again with --force.")
    # THE MEMBER THAT WAS ASKED FOR IS THE ONE THAT CAN FAIL THIS COMMAND. Anyone else's failure
    # is recorded and reported, and is refused where it belongs: at that plugin's own run or
    # plan. This used to raise for any member, so `install liana` failed on abundance's
    # unfixable pertpy/statsmodels ImportError and on two members the node had SIGKILLed.
    if kernel.name in failed:
        raise RuntimeError(
            f"{p} was built, and {kernel.name} - the plugin this install was asked about - could "
            f"not run in it. Its selftest failure is above and recorded at "
            f"{PROOF_NAME.format(kernel=kernel.name)} beside the environment, so nothing will "
            f"plan or run it until something proves it.")
    others = [m for m in failed if m != kernel.name]
    if others:
        log(f"  {len(others)} other member(s) of this environment recorded a FAILED selftest: "
            f"{', '.join(others)}.")
        log(f"      They do not make {kernel.name}'s environment unbuilt - it was proved for "
            f"{kernel.name} above - and none of them will run or plan until it is proved:")
        for m in others:
            log(f"      scprofile install {m} --prefix {prefix}")
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

    IT RECORDS ITS VERDICT, and this is the only function that does. Whatever route asked for the
    proof - `install`, `scprofile selftest`, a repair inside a run - the environment ends up
    carrying one statement of what happened, so `run` and `plan` cannot disagree with each other
    or with the log sitting beside it. See PROOF_NAME above for why the record is per member.
    """
    # THE KERNEL ANSWERS. This looked for `kernel.path / "selftest.py"`, which for a ONE-FILE
    # plugin is a path inside a file and can never exist - so every one-file plugin was reported
    # as shipping no selftest, and the one check that would have caught the launch bug above was
    # skipped for exactly the shape that had it.
    if not kernel.has_selftest:
        # RECORDED AS A VERDICT OF ITS OWN. "ships no selftest" is not "was not proved": there is
        # nothing that could prove it, and refusing to run it would ban a whole legal shape. The
        # record says so rather than leaving a hole a reader has to interpret.
        record_proof(kernel, prefix, verdict="none", log=log)
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
    # BESIDE THE ENVIRONMENT, through the same derivation the record uses. `proof_state` tells a
    # reader both files are "beside the environment"; with `.resolve().parent.parent` here that
    # sentence was false on a venv-built one, and the log went to the base python's prefix - where
    # a system python makes this `open` raise PermissionError and take down a selftest that had
    # nothing wrong with it. See `env_home`.
    logf = env_home(exe) / f".scprofile_selftest_{kernel.name}.log"
    log(f"  selftest: {Path(cmd[-1]).name}  ({why})")
    log(f"      live: {logf}")
    try:
        with open(logf, "w", encoding="utf-8") as fh:
            r = subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT, timeout=limit,
                               env=with_env_bin(exe))
    except subprocess.TimeoutExpired:
        tail = "".join(logf.read_text(encoding="utf-8", errors="replace").splitlines(True)[-15:])
        record_proof(kernel, prefix, verdict="failed",
                     why=f"its selftest did not finish within {limit}s", log=log)
        raise RuntimeError(
            f"{kernel.name}'s selftest did not finish within {limit}s, so nothing has proved this "
            f"environment. A selftest proves a CALL is well-formed and is seconds to minutes by "
            f"construction; one that runs longer is stuck, not slow - a fetch with no route out "
            f"is the usual reason.\n  Last lines of {logf.name}:\n{tail}") from None
    out = logf.read_text(encoding="utf-8", errors="replace")
    if r.returncode != 0:
        # THE STATUS, AND WHETHER THE LOG SAYS ANYTHING. This printed the log and nothing else,
        # and the case it kept meeting was a process KILLED BY A SIGNAL: the log then holds three
        # FutureWarnings from an import and no error at all, so "SELFTEST FAILED" arrived with no
        # diagnosis and read as a broken plugin. Measured across three submissions of the same
        # environment on two nodes, the same members passed, then failed, then passed - which is
        # a machine, not a package, and nothing in the message could distinguish them.
        #
        # A NEGATIVE RETURN CODE IS A SIGNAL, and -9 is a kill. Named, because a reader who sees
        # it should look at the node and its limits rather than at the plugin.
        note = ""
        if r.returncode < 0:
            note = (f"\n  Killed by signal {-r.returncode}"
                    + (" (SIGKILL - on a batch node that is usually the memory cgroup, and the "
                       "job's own limit is the first thing to check)" if r.returncode == -9 else "")
                    + ". The plugin never got to report anything, so nothing below is its "
                      "diagnosis.")
        elif not [ln for ln in out.splitlines()
                  if ln.strip() and "Warning" not in ln and not ln.startswith("  ")]:
            note = (f"\n  Exit {r.returncode}, and the log holds nothing but warnings - the "
                    f"process stopped without saying why.")
        # THE VERDICT IS RECORDED BEFORE IT IS RAISED. The caller may well swallow this - a
        # shared environment's other members are none of this member's business - and the whole
        # point of the record is that a failure nobody re-reads still refuses at the point of use.
        record_proof(kernel, prefix, verdict="failed",
                     why=(f"exit {r.returncode}"
                          + (f", killed by signal {-r.returncode}" if r.returncode < 0 else "")
                          + (": " + " ".join(out.split())[-160:] if out.strip() else "")),
                     log=log)
        raise RuntimeError(
            f"{kernel.name}'s selftest FAILED (exit {r.returncode}), so the environment is not "
            f"usable:{note}\n" + out)
    record_proof(kernel, prefix, verdict="ok", log=log)
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
    # THE POINT OF USE IS WHERE THE PROOF IS DEMANDED. `install` used to enforce it for the whole
    # group at once - every member proved or nobody installed - and that made three plugins
    # nobody asked about able to sink the one that was asked for (see PROOF_NAME). The property it
    # was protecting is real and survives here, one plugin at a time: a plugin whose own record is
    # absent, stale or failed does not start, because a run is exactly where an unproved
    # environment must not be met for the first time. Ten minutes of queue is cheaper than an
    # hour of compute reporting NOT RUN.
    pstate, pwhy, pfix = proof_state(kernel, prefix)
    if pstate in UNPROVED:
        raise RuntimeError(
            f"{kernel.name} will not be run: {pwhy}\n"
            f"  An environment is proved for one plugin at a time, and nothing has proved this "
            f"one for {kernel.name}. That proof is what stops a run from being the first thing "
            f"to find out.\n"
            f"  Fix: {pfix}")
    if pstate == "unrecorded":
        # SAID, NOT ASSUMED AWAY. This environment predates the per-member record or was built by
        # hand, so there is nothing here that can be called a proof either way - and a silence
        # that reads as a pass is the shape of failure this whole file is about.
        log(f"  note: {pwhy}. `{pfix}` writes one, and costs a selftest rather than a build.")
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
    # A WORKING DIRECTORY THE INSTANCE OWNS. Nothing set one, so every plugin inherited the
    # directory the job was launched from - and a wrapped tool that writes to the current
    # directory then writes into the PROJECT. Measured: CellChat's netVisual and its cluster-
    # number estimator dropped eight plates and a PDF at the project root, beside the stage
    # directories, on a run whose output was supposed to be sealed inside its own run key. The
    # instance directory is where anything a tool drops belongs.
    _cwd = Path(out).resolve()
    _cwd.mkdir(parents=True, exist_ok=True)
    with open(logf, "w", encoding="utf-8") as fh:
        r = subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT,
                           env=with_env_bin(exe, manifest.env_for_kernel(inp, cores=_cores)),
                           cwd=str(_cwd), timeout=timeout)
    if r.returncode != 0:
        tail = "".join(logf.read_text(encoding="utf-8", errors="replace").splitlines(True)[-15:])
        raise RuntimeError(
            f"{kernel.name} exited {r.returncode}. Last lines of {logf.name}:\n{tail}")
    payload = manifest.read_output(out)
    extra = manifest.unknown_keys(payload)
    if extra:
        log(f"  note: {kernel.name} declared key(s) the host does not act on: {extra}")
    return payload
