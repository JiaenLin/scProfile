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

# THREADS BOUNDED BY THE ALLOCATION, which this did not do and the job script beside it always
# has. Every one of these is read at IMPORT time by the library it controls, so a BLAS that sees
# a 64-core node while the scheduler granted four will oversubscribe — and a native library
# fighting a cgroup dies without a Python traceback, which is exactly what a selftest failure
# with one log line and no exception looks like.
: "${NCPUS:=${SCPROFILE_SMOKE_CORES:-4}}"
export OMP_NUM_THREADS="$NCPUS" OPENBLAS_NUM_THREADS="$NCPUS" MKL_NUM_THREADS="$NCPUS" \
       NUMEXPR_NUM_THREADS="$NCPUS" VECLIB_MAXIMUM_THREADS="$NCPUS" BLIS_NUM_THREADS="$NCPUS"
echo "threads  $NCPUS per library"

echo "tool     $TOOL"
echo "python   $PY"
echo "work     $WORK"
echo "started  $(date -u +%FT%TZ)"

echo; echo "=== 1. the fixture plugins are discovered and valid ==="
# `_check.py`, with the underscore, so plugin discovery skips it. Without it the checker script
# in this directory is loaded as a plugin and reported as one with no summary — noise in every
# doctor and validate this suite runs, from a file that is not a plugin at all.
$PY -m scprofile.cli validate perunit || exit 1
$PY -m scprofile.cli validate contrastee || exit 1

echo; echo "=== 2. every built plugin's selftest ==="
# `scprofile selftest`, NOT a shell loop over selftest.py with the host interpreter. A plugin
# that brings its own environment must have its selftest run BY THAT ENVIRONMENT; the loop this
# replaces ran velocity's selftest under the host python and died on `No module named scvelo`,
# reporting a missing dependency that is not missing anywhere it matters.
# REPORTED, NOT FATAL — and the two are different claims. A selftest proves a plugin's
# ENVIRONMENT works; the steps below prove the plan, the decision channel, the merge and the
# report work together, and a code change breaks the second far more often than the first.
# Aborting here meant one unusable environment hid every host-path failure behind it, so a
# pre-flight submitted to find them reported one thing and stopped. The exit status still
# carries it: `selftest_rc` is folded into the result at the end.
selftest_rc=0
$PY -m scprofile.cli selftest ${PREFIX:+--prefix "$PREFIX"} || selftest_rc=$?
[ "$selftest_rc" -eq 0 ] || echo "  SELFTESTS FAILED (rc=$selftest_rc) — continuing, so this job
  reports every host-path failure too rather than only the first environment one."

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
# velocity ONLY IF AN ENVIRONMENT WAS NAMED. It needs its own, so a site without one would see a
# refusal rather than a test - but skipping it silently would leave the only plugin that brings an
# environment, writes a side-car object and needs a compatibility copy of the input outside the
# only test that opens what a run wrote. Which of the two happened is printed, not implied.
WANT=cellcycle,perunit,contrastee
if [ -n "$PREFIX" ] && [ -d "$PREFIX" ]; then
    WANT=velocity,$WANT
    echo "  including velocity: an environment prefix was given ($PREFIX)"
else
    echo "  NOT including velocity: no environment prefix given, so its own interpreter, its"
    echo "  side-car object and the compatibility-copy path are NOT exercised by this run."
fi
# --design, AND THAT IS THE POINT OF THIS STEP. Without one the planner decides no contrast,
# no plugin is handed one, and the channel that carried a delivery bug into a three-hour run
# is not walked by anything that runs before that run. The fixture is eight samples in a 2x2
# with replication, so the contrast decided here is the INTERACTION — the branch a real
# design-testing plugin takes.
$PY -m scprofile.cli run --h5ad "$WORK/fixture.h5ad" --out "$WORK/results" \
    --design "$HERE/design.csv" \
    --kernel "$WANT" ${PREFIX:+--prefix "$PREFIX"} \
    --cores 4 --timeout 1800
echo "  run exit $?"

echo; echo "=== 6. what landed ==="
( cd "$WORK/results" && find . -type f | sort | sed 's/^/  /' )

echo; echo "=== 7. the checks ==="
$PY "$HERE/_check.py" --out "$WORK/results" --units 8 --expect "$WANT" --log "$LOG"
rc=$?
if [ "$selftest_rc" -ne 0 ]; then
    echo "  and the selftests failed earlier (rc=$selftest_rc): an environment is not usable."
    rc=1
fi
echo; echo "finished $(date -u +%FT%TZ)"
exit $rc
