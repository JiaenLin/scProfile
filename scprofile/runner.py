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


def lock_spec(kernel):
    """Read `lock.yml` into {python, channels, conda, pip}. Stdlib only, like everything here.

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
    """
    f = kernel.path / "lock.yml"
    if not f.exists():
        raise FileNotFoundError(f"{kernel.name} has no lock.yml; it cannot be installed")
    spec = {"python": None, "channels": [], "conda": [], "pip": []}
    section, in_pip, pip_indent = None, False, None
    for raw in f.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        body = line.strip()
        if indent == 0:
            section, in_pip = body.split(":", 1)[0].strip(), False
            continue
        if not body.startswith("- "):
            raise ValueError(f"{f}: cannot read {raw!r}")
        item = body[2:].strip()
        if section == "channels":
            spec["channels"].append(item)
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
    if not spec["python"]:
        raise ValueError(f"{f}: no `python=<version>` in dependencies. A lock that does not pin "
                         f"the interpreter is not a lock - wheels are built per minor version.")
    return spec


def _venv_python(want):
    """A `pythonX.Y` on PATH matching the lock, for the route that needs no conda at all."""
    exe = shutil.which(f"python{want}")
    return exe if exe else None


def install(kernel, prefix, *, force=False, log=print):
    """Build a kernel's environment from its lock, then prove it with its own selftest.

    A selftest that runs at INSTALL time is the difference between finding out now and finding out
    after the models have trained. It is the kernel's own file, because only the kernel knows what
    importing successfully means for it.
    """
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
            cmd += [f"python={spec['python']}", "pip"] + spec["conda"]
            log(f"  interpreter: {mgr} -> python {spec['python']}"
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
        (p / ".scprofile_lock").write_text(lock_fingerprint(kernel), encoding="utf-8")

    st = kernel.path / "selftest.py"
    if st.exists():
        exe, _ = interpreter(kernel, prefix)
        log(f"  selftest: {st.name}")
        r = subprocess.run([exe, str(st)], capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(
                f"{kernel.name}'s selftest FAILED, so the environment is not usable:\n"
                + (r.stdout or "") + (r.stderr or ""))
        # Print it on SUCCESS too. "selftest ok" tells you a check passed and not which versions
        # it passed against, and the versions are the thing anyone debugging this later needs -
        # a lock is a claim about an environment, and this is the receipt.
        for line in (r.stdout or "").splitlines():
            log(f"    {line}")
        log("  selftest ok")
    return p


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
