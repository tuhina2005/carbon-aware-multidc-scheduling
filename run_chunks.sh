#!/usr/bin/env bash
# Re-run every experiment with the current solver in short sessions instead of one long run.
#
#   ./run_chunks.sh 1      grid + headline + sensitivity                          (~1 h)
#   ./run_chunks.sh 2      multi-date, Jan + Apr                                  (~1.5 h)
#   ./run_chunks.sh 3      multi-date, Jul + Oct                                  (~1.5 h)
#   ./run_chunks.sh w1     W1 heterogeneous-DC study -> results/hetero/           (~1 h)
#   ./run_chunks.sh w2     W2 contention study (DC queues) -> results/contention/ (~2-3 h)
#   ./run_chunks.sh 5      rebuild results/ from the cache, noise control, plots, comparison (~1.5 h)
#   ./run_chunks.sh status which sessions have finished
#
# Sessions can run while you use the laptop (they just slow it down), in any order except 5 last.
# Closing the lid pauses a session; it continues when the Mac wakes.
#
# Sessions 1-4 only fill the shared solver cache (cwm_multidc/results/cache.jsonl); their tables go
# to cwm_multidc/results/_chunks/ and are thrown away.  So any session can be stopped (Ctrl-C, lid
# closed, battery) and simply started again: finished solver calls are never repeated.  Session 5
# writes the real results in one pass; if an earlier session did not finish, session 5 computes
# the missing part itself (it just takes longer).  The Mac is kept awake while a session runs
# (caffeinate), but closing the lid still sleeps it.
set -euo pipefail
cd "$(dirname "$0")"
PY=${PY:-.venv/bin/python}
CI=cwm_multidc/data/public_ci
SCRATCH=cwm_multidc/results/_chunks
LOGS=$SCRATCH/logs
mkdir -p "$LOGS"
EXP=("$PY" -m cwm_multidc.experiments)

dates() {  # third Wednesday of each month of 2024, months $1..$2
  "$PY" -c "from cwm_multidc.experiments import third_wednesdays as t; print(','.join(t()[$1-1:$2]))"
}

awake() {  # keep the machine from idle-sleeping while the command runs (macOS)
  if command -v caffeinate >/dev/null 2>&1; then caffeinate -i "$@"; else "$@"; fi
}

run() {  # run <session> <log name> <command...>
  local s=$1 name=$2; shift 2
  echo "[session $s] $name  (log: $LOGS/$name.log)"
  awake "$@" > "$LOGS/$name.log" 2>&1
}

finish() { date '+%Y-%m-%d %H:%M' > "$SCRATCH/session$1.done"; echo "session $1 finished"; }

case "${1:-}" in
  1)
    run 1 grid "${EXP[@]}" grid --ci-dir "$CI" --out "$SCRATCH"
    run 1 headline "${EXP[@]}" headline --ci-dir "$CI" --out "$SCRATCH"
    run 1 sensitivity "${EXP[@]}" sensitivity --ci-dir "$CI" --out "$SCRATCH"
    finish 1 ;;
  2|3)
    if [ "$1" = 2 ]; then m=(1 4); else m=(7 10); fi
    d="$(dates ${m[0]} ${m[0]}),$(dates ${m[1]} ${m[1]})"
    run "$1" "multidate_m${m[0]}+${m[1]}" "${EXP[@]}" multidate --ci-dir "$CI" --dates "$d" --out "$SCRATCH"
    finish "$1" ;;
  5)
    for s in 1 2 3; do
      [ -f "$SCRATCH/session$s.done" ] || echo "note: session $s not finished; session 5 will compute its part (slower)"
    done
    run 5 final_grid "${EXP[@]}" grid --ci-dir "$CI"
    run 5 final_headline "${EXP[@]}" headline --ci-dir "$CI"
    run 5 final_sensitivity "${EXP[@]}" sensitivity --ci-dir "$CI"
    run 5 final_multidate "${EXP[@]}" multidate --ci-dir "$CI"
    run 5 final_noise "${EXP[@]}" multidate-noise --ci-dir "$CI"
    run 5 final_plot "${EXP[@]}" plot
    if [ -d cwm_multidc/results/pre_fix_solver ]; then
      "$PY" -m cwm_multidc.scripts.compare_results cwm_multidc/results/pre_fix_solver cwm_multidc/results \
        --out cwm_multidc/results/pre_vs_post_fix.md > /dev/null
      echo "comparison: cwm_multidc/results/pre_vs_post_fix.md"
    fi
    run 5 tests "$PY" -m unittest discover -s cwm_multidc/tests -t .
    finish 5 ;;
  w1)
    run w1 hetero "${EXP[@]}" hetero --ci-dir "$CI"
    "$PY" -c "from pathlib import Path; from cwm_multidc.plots import _style, make_hetero; _style(); make_hetero(Path('cwm_multidc/results/hetero'))"
    finish w1 ;;
  w2)
    run w2 contention "${EXP[@]}" contention --ci-dir "$CI"
    "$PY" -c "from pathlib import Path; from cwm_multidc.plots import _style, make_contention; _style(); make_contention(Path('cwm_multidc/results/contention'))"
    finish w2 ;;
  status)
    for s in 1 2 3 w1 w2 5; do
      if [ -f "$SCRATCH/session$s.done" ]; then echo "session $s: done $(cat "$SCRATCH/session$s.done")"
      else echo "session $s: not done"; fi
    done
    wc -l < cwm_multidc/results/cache.jsonl 2>/dev/null | sed 's/^/cached solver results: /' || true ;;
  *)
    sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'; exit 2 ;;
esac
