#!/usr/bin/env python3
"""A file the maker generates must BE what the maker generates, byte for byte.

DEMANDED, CHECKED AND GENERATED ARE THREE DIFFERENT CLAIMS. A plugin that draws through R is given
a drawing protocol - the figure context, the colour map, the declared ceilings, the caption file
and both draw wrappers - and `sch dev convert placement` requires that the wrapper it runs refuses
past its ceilings. A requirement can be satisfied by a hand-written file that looks like the
generator's output, and then the whole point of generating it is gone: one definition serving every
plugin becomes one definition again the moment somebody edits the copy.

WHY THIS SUITE EXISTS AT ALL, and the answer is not flattering. The command that generates this
file CRASHED for every kernel in this repository - it wrote the six-file layout `scprofile/plugin.py`
replaced, and a one-file kernel's path is the FILE, so it tried `kernels/<name>.py/run.py`. The
generated wrapper had therefore never been generated once, on any plugin, while being reported as
the reason the mechanism was no longer hand-written. Nothing here checked, because the check was
done once by hand at a shell prompt and left there.

THE REPOSITORY IS THE ONLY HOME. That hand check is this file.
"""
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scprofile import scaffold as SC                                      # noqa: E402
from scprofile.kernels import discover                                    # noqa: E402

FAILURES = []


def check(ok, msg):
    if not ok:
        FAILURES.append(msg)


ks = discover()
if not ks:
    print("skipped - no kernels are installed here, so there is no companion to check")
    sys.exit(0)

drawing = [k for k in ks.values() if SC.draws_through_r(k.spec)]
if not drawing:
    print("skipped - no kernel here draws through R, so this repository generates no R companion. "
          "That is a fact about this checkout and not about the mechanism")
    sys.exit(0)

tmp = Path(tempfile.mkdtemp(prefix="companion-"))
try:
    for k in drawing:
        beside = SC.companion(k.path, "draw.R")
        check(beside.is_file(),
              f"{k.name} draws through R and {beside.name} is not beside it. It is GENERATED: "
              f"`scprofile scaffold {k.name}` writes it")
        if not beside.is_file():
            continue

        # THE PLUGIN MUST ACTUALLY READ IT. A generated file nothing loads is a file, not a
        # mechanism, and this repository has shipped exactly that.
        src = Path(k.path).read_text(encoding="utf-8")
        check(beside.name in src or "draw.R" in src,
              f"{k.name} never names {beside.name}, so the generated protocol is not reaching "
              f"any script it runs")

        out = tmp / k.name
        SC.scaffold(k, force=True, out_dir=out, log=lambda *_a, **_kw: None)
        fresh = out / beside.name
        check(fresh.is_file(), f"`scaffold {k.name}` wrote no {beside.name} into a fresh directory")
        if fresh.is_file():
            check(fresh.read_bytes() == beside.read_bytes(),
                  f"{beside.name} beside {k.name} is NOT what `scprofile scaffold {k.name}` "
                  f"writes: it has been edited in place, so the next regeneration silently "
                  f"reverts whoever made the change. Edit scprofile/scaffold.py instead")

    # AND THE COMPANION BELONGS TO ONE PLUGIN. Nine one-file kernels share one directory, so a
    # bare `draw.R` in it would answer the ceiling requirement for all nine - including the ones
    # that never load it. Green while the family is together; red the day one is deployed alone.
    shared = sorted((ROOT / "kernels").glob("*.R"))
    unnamed = [f for f in shared if f.stem.split(".")[0] not in ks]
    check(not unnamed,
          "R beside the kernels that is named for no kernel: "
          + ", ".join(f.name for f in unnamed)
          + " - it would answer for every plugin in this directory")
finally:
    shutil.rmtree(tmp, ignore_errors=True)

if FAILURES:
    print("FAIL")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print(f"ok: {len(drawing)} generated companion(s) are byte-identical to what generates them, "
      f"and each is named for the plugin that loads it")
