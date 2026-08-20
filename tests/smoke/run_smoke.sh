#!/bin/bash
# End-to-end smoke test. Builds a synthetic object, runs the host over it, checks what landed.
#
# ON A CLUSTER THIS BELONGS IN A BATCH JOB, not at a login prompt. It starts subprocesses and
# fits a model; a scheduler exists so that work like this is accounted for. Wrap the invocation
# below in whatever your site's job script looks like and submit it.
#
#   tests/smoke/run_smoke.sh <PYTHON> <WORKDIR> [<ENV_PREFIX>]
#
# PYTHON     an interpreter that can import anndata and scanpy
# WORKDIR    a scratch directory. Everything is written under it and nothing is read from
#            anywhere else.
# ENV_PREFIX where kernel environments live, if any are installed. Optional; without it only
#            host-interpreter plugins run, which is enough to exercise every path this checks.
set -uo pipefail

PY=${1:?usage: run_smoke.sh <PYTHON> <WORKDIR> [<ENV_PREFIX>]}
WORK=${2:?usage: run_smoke.sh <PYTHON> <WORKDIR> [<ENV_PREFIX>]}
PREFIX=${3:-}
HERE=$(cd "$(dirname "$0")" && pwd)
TOOL=$(cd "$HERE/../.." && pwd)

mkdir -p "$WORK"
LOG=$WORK/smoke.log
exec > >(tee -a "$LOG") 2>&1

export PYTHONPATH=$TOOL
export SCPROFILE_KERNELS=$HERE
export MPLCONFIGDIR=$WORK/.mpl

echo "tool     $TOOL"
echo "python   $PY"
echo "work     $WORK"
echo "started  $(date -u +%FT%TZ)"

echo; echo "=== 1. the per-unit fixture plugin is discovered and valid ==="
$PY -m scprofile.cli validate perunit || exit 1

echo; echo "=== 2. every built plugin's selftest ==="
# `scprofile selftest`, NOT a shell loop over selftest.py with the host interpreter. A plugin
# that brings its own environment must have its selftest run BY THAT ENVIRONMENT; the loop this
# replaces ran velocity's selftest under the host python and died on `No module named scvelo`,
# reporting a missing dependency that is not missing anywhere it matters.
$PY -m scprofile.cli selftest ${PREFIX:+--prefix "$PREFIX"} || exit 1

echo; echo "=== 3. the fixture ==="
# tests/make_fixture.py, the one that was already here. It is the better fixture and it predates
# this directory: X is LOGNORMALISED rather than counts, which is what an integrated object
# actually delivers, and its unspliced counts LEAD spliced along a latent axis, so a velocity fit
# has real signal to find instead of noise. A second fixture builder was written here before
# looking for one, and deleted on finding this.
$PY "$HERE/../make_fixture.py" "$WORK/fixture.h5ad" || exit 1

echo; echo "=== 4. a duplicated --kernel must not race ==="
# NOT filtered through grep. Filtering this hid a fatal write_h5ad error behind a pattern that
# did not match it, and the pipeline's exit status was the grep's.
$PY -m scprofile.cli run --h5ad "$WORK/fixture.h5ad" --out "$WORK/dup" \
    --kernel cellcycle,cellcycle --cores 4 --timeout 900
echo "  dup exit $?"
[ -f "$WORK/dup/report.json" ] && echo "  dup wrote report.json" \
    || { echo "  dup DID NOT write report.json"; exit 1; }

echo; echo "=== 5. the run ==="
$PY -m scprofile.cli run --h5ad "$WORK/fixture.h5ad" --out "$WORK/results" \
    --kernel cellcycle,perunit ${PREFIX:+--prefix "$PREFIX"} \
    --cores 4 --timeout 1800
echo "  run exit $?"

echo; echo "=== 6. what landed ==="
( cd "$WORK/results" && find . -type f | sort | sed 's/^/  /' )

echo; echo "=== 7. the checks ==="
$PY "$HERE/check.py" --out "$WORK/results" --units 4 --expect cellcycle,perunit --log "$LOG"
rc=$?
echo; echo "finished $(date -u +%FT%TZ)"
exit $rc
