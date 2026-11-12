#!/usr/bin/env bash
# Rebuild the solver and regenerate every result in cwm_multidc/results/ from the real 2024 CI data.
#
#   ./reproduce_multidc.sh            # everything (~12-14 h on an 8-core laptop)
#   ./reproduce_multidc.sh quick      # build + tests + grid/headline/sensitivity + plots (~1.5 h), no multi-date
#
# Solver results are cached in cwm_multidc/results/cache.jsonl, keyed on the inputs AND the SHA-256
# of the solver binary, so an interrupted run resumes where it stopped and a rebuilt solver never
# reuses old results.  Requires: cmake, ninja, a C++17 compiler, Python 3.13 with requirements.lock.txt.
set -euo pipefail
cd "$(dirname "$0")"
PY=${PY:-.venv/bin/python}
CI=cwm_multidc/data/public_ci
MODE=${1:-full}

echo "== build solve_cwm / heft_mapping"
(cd code_cwm/code && ./build.sh)
shasum -a 256 code_cwm/code/deploy/solve_cwm

echo "== tests"
"$PY" -m unittest discover -s cwm_multidc/tests -t .

echo "== experiments (CI: $CI)"
"$PY" -m cwm_multidc.experiments grid --ci-dir "$CI"
"$PY" -m cwm_multidc.experiments headline --ci-dir "$CI"
"$PY" -m cwm_multidc.experiments sensitivity --ci-dir "$CI"
if [ "$MODE" != quick ]; then
  "$PY" -m cwm_multidc.experiments multidate --ci-dir "$CI"
fi

echo "== figures and tables"
"$PY" -m cwm_multidc.experiments plot
echo "done: cwm_multidc/results/ (provenance in ci_source.json)"
