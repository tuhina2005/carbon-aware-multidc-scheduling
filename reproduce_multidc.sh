#!/usr/bin/env bash
# Rebuild the solver and regenerate every result in cwm_multidc/results/ from the real 2024 CI data.
#
#   ./reproduce_multidc.sh            # everything (~8-10 h on an 8-core laptop from an empty cache)
#   ./reproduce_multidc.sh quick      # build + tests + grid/headline/sensitivity + plots (~1.5 h)
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
  "$PY" -m cwm_multidc.experiments multidate --ci-dir "$CI"         # 4 seasons x 4 start hours
  "$PY" -m cwm_multidc.experiments multidate-noise --ci-dir "$CI"   # 3 seeds + C1 on the winners
  "$PY" -m cwm_multidc.experiments substitution --ci-dir "$CI"      # H6: no flat clean grid
  "$PY" -m cwm_multidc.experiments hetero --ci-dir "$CI"            # W1: hardware tiers + PUE
  "$PY" -m cwm_multidc.experiments contention --ci-dir "$CI"        # W2: diurnal DC queues
  "$PY" -m cwm_multidc.experiments sources --ci-dir "$CI"           # W3: data origin
fi

echo "== figures and tables"
"$PY" -m cwm_multidc.experiments plot
if [ "$MODE" != quick ]; then
  "$PY" -m cwm_multidc.waiting_cost   # cost of waiting/queuing (re-scores saved results, no solver calls)
  "$PY" -m cwm_multidc.tradeoffs      # carbon vs deadline, results by workflow (from saved summaries)
fi
echo "done: cwm_multidc/results/ (provenance in ci_source.json)"
