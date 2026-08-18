"""Finding kernels, reading what they declare, and checking prerequisites BEFORE spending.

A kernel is a directory, not a python class. That is what lets one be written in R, and what stops
the host from importing anything a kernel pins.

    kernels/<name>/
        kernel.yml       what it needs, what it produces, what it cannot show
        lock.yml         the environment, captured from a working install
        references.yml   URL + sha256 + size, organism-keyed  (optional)
        run.py | run.R   the entry point
        selftest.py      proves the env works before a run is spent on it

STDLIB ONLY, including the YAML reading. `kernel.yml` is deliberately a flat, simple subset -
scalars, lists and one level of mapping - so the host needs no yaml dependency to discover what a
kernel wants. A host that could not enumerate its kernels without pyyaml installed would fail at
exactly the moment a user is trying to work out why nothing runs.
"""
from __future__ import annotations

from pathlib import Path

#: Where kernels live, relative to the package. Overridable so a site can add its own.
KERNEL_DIRNAME = "kernels"


def _mini_yaml(text):
    """A deliberately small YAML subset: `key: value`, `key:` + `  - item`, and `#` comments.

    Not a YAML parser and does not pretend to be. It reads the files THIS project ships, and
    refuses anything it does not understand rather than guessing - a config silently
    mis-parsed is worse than one that will not load.
    """
    out, key = {}, None
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if line.startswith(("  - ", "- ")):
            item = line.split("- ", 1)[1].strip()
            if key is None:
                raise ValueError(f"list item with no key: {raw!r}")
            # `key:` with nothing after it stores None, which is not the same as absent - so
            # setdefault would keep the None and the isinstance check below would reject a
            # perfectly ordinary list. Promote it here.
            if out.get(key) is None:
                out[key] = []
            if not isinstance(out[key], list):
                raise ValueError(f"{key!r} has both a value and list items")
            out[key].append(_scalar(item))
            continue
        if line.startswith(" "):
            raise ValueError(f"unsupported indentation: {raw!r}")
        if ":" not in line:
            raise ValueError(f"not a key: {raw!r}")
        key, _, val = line.partition(":")
        key, val = key.strip(), val.strip()
        out[key] = _scalar(val) if val else None
    return out


def _scalar(v):
    v = v.strip().strip('"').strip("'")
    if v.lower() in ("true", "false"):
        return v.lower() == "true"
    if v.lower() in ("null", "none", ""):
        return None
    try:
        return int(v)
    except ValueError:
        pass
    try:
        return float(v)
    except ValueError:
        return v


class Kernel:
    """One kernel directory, and what it declares about itself."""

    def __init__(self, path):
        self.path = Path(path)
        self.name = self.path.name
        f = self.path / "kernel.yml"
        if not f.exists():
            raise FileNotFoundError(f"{self.path} has no kernel.yml; it is not a kernel")
        self.spec = _mini_yaml(f.read_text(encoding="utf-8"))

    def _list(self, key):
        v = self.spec.get(key)
        if v is None:
            return []
        return list(v) if isinstance(v, list) else [v]

    # ---- what it declares ------------------------------------------------------------------
    @property
    def summary(self):
        return self.spec.get("summary") or ""

    @property
    def language(self):
        return (self.spec.get("language") or "python").lower()

    @property
    def entry(self):
        return self.spec.get("entry") or ("run.R" if self.language == "r" else "run.py")

    @property
    def needs_obs(self):
        return self._list("needs_obs")

    @property
    def needs_obsm(self):
        return self._list("needs_obsm")

    @property
    def needs_layers(self):
        return self._list("needs_layers")

    @property
    def needs_kernels(self):
        return self._list("needs_kernels")

    @property
    def needs_design(self):
        return bool(self.spec.get("needs_design"))

    @property
    def produces(self):
        return self._list("produces")

    @property
    def cannot_show(self):
        """What this kernel's own result does NOT establish. Printed under its section."""
        return self._list("cannot_show")

    @property
    def needs_env(self):
        """False for a kernel that runs in the host's own interpreter (e.g. cheap ones)."""
        return self.spec.get("needs_env", True)

    def references(self, organism=None):
        """{name: {url, sha256, size, organism}} for this kernel, filtered by organism."""
        f = self.path / "references.yml"
        if not f.exists():
            return {}
        flat = _mini_yaml(f.read_text(encoding="utf-8"))
        out, cur = {}, None
        for k, v in flat.items():
            if v is None:
                cur = k
                out[cur] = {}
            elif cur:
                out[cur][k] = v
        if organism:
            out = {k: v for k, v in out.items()
                   if not v.get("organism") or str(v["organism"]).lower() == organism.lower()}
        return out

    def __repr__(self):
        return f"<Kernel {self.name}>"


def discover(root=None):
    """Every kernel that ships with the host, plus any under $SCPROFILE_KERNELS."""
    import os
    roots = []
    r = Path(root) if root else Path(__file__).resolve().parent.parent / KERNEL_DIRNAME
    roots.append(r)
    extra = os.environ.get("SCPROFILE_KERNELS")
    if extra:
        roots += [Path(p) for p in extra.split(os.pathsep) if p]
    found = {}
    for base in roots:
        if not base.is_dir():
            continue
        for d in sorted(base.iterdir()):
            if (d / "kernel.yml").exists():
                found[d.name] = Kernel(d)          # later roots win, so a site can override
    return found


def order(names, available):
    """Kernels sorted so a prerequisite runs before what needs it. Refuses a cycle by name."""
    todo, done, out = list(names), set(), []
    guard = 0
    while todo:
        guard += 1
        if guard > len(names) * len(names) + 10:
            raise ValueError(f"cannot order {names}: a needs_kernels cycle among {todo}")
        n = todo.pop(0)
        k = available.get(n)
        pend = [d for d in (k.needs_kernels if k else []) if d in names and d not in done]
        if pend:
            todo.append(n)
            continue
        out.append(n)
        done.add(n)
    return out


def unmet(kernel, *, obs=(), obsm=(), layers=(), ran=(), has_design=False):
    """Everything `kernel` needs and does not have. One line per problem, each with its FIX.

    Checked before the kernel is launched. A prerequisite discovered inside a kernel is a
    prerequisite discovered after the environment was resolved and the object was read.
    """
    problems = []
    for c in kernel.needs_obs:
        if c not in obs:
            who = _who_produces(f"obs[{c}]")
            problems.append(f"obs[{c!r}] is absent." + (f"  Fix: run --kernel {who} first." if who
                                                        else "  It must be on the input object."))
    for c in kernel.needs_obsm:
        if c not in obsm:
            problems.append(f"obsm[{c!r}] is absent.  Fix: pass --embedding to name the one to "
                            f"use, or run the integration step that writes it.")
    for c in kernel.needs_layers:
        if c not in layers:
            problems.append(
                f"layers[{c!r}] is absent.  Fix: this kernel cannot run on this dataset. "
                f"{'Spliced/unspliced counts come from the aligner and cannot be derived later.' if c in ('spliced', 'unspliced') else ''}")
    for d in kernel.needs_kernels:
        if d not in ran:
            problems.append(f"kernel {d!r} has not been run.  Fix: --kernel {d} first, or "
                            f"--kernel {d},{kernel.name}.")
    if kernel.needs_design and not has_design:
        problems.append("no --design was given.  Fix: pass a CSV keyed on the sample column. "
                        "Without it there is no contrast to test.")
    return problems


#: Which kernel writes which cell-level column, so an unmet prerequisite can name its own fix
#: instead of leaving the user to work out where `phase` was supposed to come from.
_PRODUCERS = {
    "obs[phase]": "cellcycle",
    "obs[S_score]": "cellcycle",
    "obs[G2M_score]": "cellcycle",
    "obs[pseudotime]": "pseudotime",
}


def _who_produces(slot):
    return _PRODUCERS.get(slot)
