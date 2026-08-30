"""The reuse mechanism must be wrong-answer-safe, not merely fast.

A cache that is only fast is a liability. Each check below pins one way this one could have
served a stale or torn file, all found by scanning the mechanism rather than by it failing:

  1. THE KEY MUST COVER THE VALUES. The first key hashed the barcodes, the gene names and the
     label COLUMN NAME - none of which says what is IN them. An object re-normalised, switched
     to another layer, or re-annotated under the same column name has the same barcodes and the
     same genes, so the key matched and a stale matrix and stale labels would have been served.
  2. PUBLISH BY RENAME, NEVER BY OVERWRITE. An instance holds a HARD LINK to the cached file, so
     writing that path in place changes the bytes inside an already-sealed run directory - and a
     concurrent reader can see a half-written file.
  3. THE VALIDITY MARKER IS WRITTEN LAST. Writing it first leaves a job killed in between
     advertising a payload it never finished.
  4. A FORMAT VERSION IS PART OF THE KEY, or a cache written by older code is served to newer
     code that expects something else.
  5. THERE IS A WAY TO SWITCH IT OFF. The first thing anyone needs when a result looks wrong is
     to rule the cache out in one run.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FAILURES = []
CHECKED = 0

for f in sorted((ROOT / "kernels").glob("*.py")):
    src = f.read_text()
    if "ctx.cache(" not in src:
        continue
    CHECKED += 1
    n = f.name

    # 1. the key must hash DATA, not only names
    keyblk = re.search(r"_key\s*=\s*.*?\n\n", src, re.S)
    kb = keyblk.group(0) if keyblk else ""
    if kb and not re.search(r"\.data\b|\.indices\b|\.indptr\b|astype\(str\)\)\.encode", kb):
        FAILURES.append(f"{n}: the cache key hashes names but never the VALUES, so a "
                        f"re-normalised or re-annotated object reuses a stale file")
    if kb and "FORMAT" not in kb.upper():
        FAILURES.append(f"{n}: no producer/format version in the cache key, so a cache written "
                        f"by older code is served to newer code")

    # 6. THE CACHE PATH MUST BE SCOPED BY THE INFERENCE PARAMETERS. The stamp inside already
    #    refuses an object built under different settings, so this is not correctness - but two
    #    runs comparing two settings would share one path and overwrite each other on every
    #    unit, so the cache thrashes to nothing in exactly the comparison it is wanted for.
    import re as _re
    m = _re.search(r"ctx\.cache\(\s*[\"']objects[\"']([^)]*)\)", src)
    if m and not m.group(1).strip().strip(","):
        FAILURES.append(f"{n}: the object cache is keyed on the unit alone, so two runs at "
                        f"different inference settings overwrite each other")

    # 2/3. publication must be by rename, and the marker last
    if "ctx.cache(" in src:
        if "os.replace" not in src and "_os.replace" not in src:
            FAILURES.append(f"{n}: the cache is published by overwrite, which mutates the "
                            f"hard-linked copy inside an already-sealed run")
        ik, ir = src.find("key.txt"), src.rfind("_os.replace")
        if ik >= 0 and ir >= 0 and src.find("_os.replace") > src.rfind("key.txt"):
            FAILURES.append(f"{n}: the validity marker is written before the payload")

    # R side: same two rules
    for m in re.finditer(r"_R_[A-Z_]+\s*=\s*r?(\"\"\"|''')(.*?)\1", src, re.S):
        body = m.group(2)
        if "saveRDS" not in body:
            continue
        if "file.rename" not in body:
            FAILURES.append(f"{n}: saveRDS writes the cache path directly; an earlier run's "
                            f"hard link to it would be rewritten in place")
        i_save, i_stamp = body.find("saveRDS("), body.find("writeLines(unname(stamp)")
        if i_save >= 0 and i_stamp >= 0 and i_stamp < i_save:
            FAILURES.append(f"{n}: the inference stamp is written BEFORE the object it "
                            f"validates")

# 5. the lever
cli = (ROOT / "scprofile" / "cli.py").read_text()
if '"--no-cache"' not in cli:
    FAILURES.append("cli.py: no way to switch the cache off for one run")
elif not re.search(r"no_cache[^\n]*\n?[^\n]*cache_dir|cache_dir=\(None if getattr\(a, \"no_cache\"",
                   cli):
    FAILURES.append("cli.py: --no-cache exists but does not actually withhold the directory")

if CHECKED == 0:
    print("FAIL")
    print("  - no plugin uses ctx.cache; this check proved nothing")
    raise SystemExit(1)
if FAILURES:
    print("FAIL")
    for x in FAILURES:
        print("  -", x)
    raise SystemExit(1)
print(f"ok: {CHECKED} caching plugin(s) — key covers values and format, published by rename, "
      f"marker written last, and the cache can be switched off")
