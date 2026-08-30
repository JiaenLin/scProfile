"""A plugin must have somewhere to keep an expensive intermediate that OUTLIVES the run.

WHAT THIS COST, measured: the plugin saved its fitted object into the instance directory and
guarded it with a digest of the inference inputs — exactly right, and useless across runs,
because a new run's instance directory is empty. Every change to a PLOT therefore paid for the
whole inference again: 2m41s and 7.5 GB per unit, eighteen units, to redraw a figure.

The host says only WHERE. What to keep, under what key, and when the key is still valid are the
plugin's decisions, because only the plugin knows what determines its result. And the cache is
disposable by definition: deleting it must cost time and nothing else.
"""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scprofile import manifest as M                                       # noqa: E402
from scprofile.plugin import Context                                      # noqa: E402

FAILURES = []


def check(c, m):
    if not c:
        FAILURES.append(m)


with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    obj = root / "x.h5ad"
    obj.write_bytes(b"0")
    inst = root / "run1" / "kernels" / "kk" / "u1"
    inst.mkdir(parents=True)
    cache = root / "_cache" / "kk" / "u1"

    M.write_input(inst / "in.json", h5ad=obj, out_dir=inst, keys={}, cache_dir=cache)
    d = json.loads((inst / "in.json").read_text())
    check("cache_dir" in d, "in.json does not carry a cache_dir at all")
    check(d.get("cache_dir") == str(cache.resolve()),
          f"cache_dir was not made absolute: {d.get('cache_dir')}")

    ctx = Context(None, keys={}, out=inst, cache_dir=d["cache_dir"])
    c = ctx.cache("objects")
    check(c is not None, "ctx.cache returned nothing when the host supplied a directory")
    if c:
        check(c.is_dir(), "ctx.cache did not create the directory")
        check(str(cache.resolve()) in str(c), f"cache landed somewhere unexpected: {c}")
        # IT MUST BE OUTSIDE THE RUN. A run directory is sealed and a cache is disposable;
        # one inside the other makes the run un-sealable or the cache un-disposable.
        check((root / "run1") not in c.parents and c != (root / "run1"),
              f"the cache is INSIDE the run directory: {c}")
        (c / "big.rds").write_bytes(b"x" * 10)

    # A SECOND RUN sees the same cache and the same contents.
    inst2 = root / "run2" / "kernels" / "kk" / "u1"
    inst2.mkdir(parents=True)
    M.write_input(inst2 / "in.json", h5ad=obj, out_dir=inst2, keys={}, cache_dir=cache)
    d2 = json.loads((inst2 / "in.json").read_text())
    ctx2 = Context(None, keys={}, out=inst2, cache_dir=d2["cache_dir"])
    c2 = ctx2.cache("objects")
    check(c2 is not None and (c2 / "big.rds").is_file(),
          "a second run did not see what the first run cached — the whole point")

    # NO CACHE OFFERED must be survivable, not an exception.
    ctx3 = Context(None, keys={}, out=inst2)
    check(ctx3.cache("objects") is None,
          "a plugin given no cache got something other than None")

if FAILURES:
    print("FAIL")
    for f in FAILURES:
        print("  -", f)
    raise SystemExit(1)
print("ok: the cache is outside the run, survives it, is visible to the next run, and is "
      "absent-safe")
