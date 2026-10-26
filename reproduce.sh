#!/bin/bash
# Drive the artifact-evaluation pipeline end-to-end:
#   1. Activate the venv created by ./setup.sh
#   2. Launch the simexpal experiments for the chosen size:
#      code_cwm/experiments/reproduce/{small,medium,full}/simex/
#   3. Execute the evaluation notebook headlessly to (re)generate plots
# Idempotent: simexpal skips already-completed runs; the notebook is overwritten in place.
#
# Usage: ./reproduce.sh [--size small|medium|full]
#   --size  which experiment set to run (default: small)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

log() { printf '\n=== %s ===\n' "$*"; }

# --- Parse args --------------------------------------------------------------
SIZE="small"
while [ "$#" -gt 0 ]; do
  case "$1" in
    --size)   SIZE="${2:-}"; shift 2 ;;
    --size=*) SIZE="${1#--size=}"; shift ;;
    -h|--help)
      sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//'
      exit 0 ;;
    *) echo "ERROR: unknown argument: $1" >&2; exit 2 ;;
  esac
done

case "$SIZE" in
  small|medium|full) ;;
  *) echo "ERROR: --size must be one of small|medium|full (got: '$SIZE')" >&2; exit 2 ;;
esac

REPRO_DIR="code_cwm/experiments/reproduce"
SIMEX_DIR="$REPRO_DIR/$SIZE/simex"
EVAL_DIR="$REPRO_DIR/eval"
if [ ! -d "$SIMEX_DIR" ]; then
  echo "ERROR: experiment directory $SIMEX_DIR does not exist." >&2
  exit 1
fi

# --- Pre-flight: venv + built binaries ---------------------------------------
log "Pre-flight checks"
if [ ! -d .venv ]; then
  echo "ERROR: .venv/ not found. Run ./setup.sh first." >&2
  exit 1
fi

for bin in \
  code_cwm/code/deploy/main \
  code_cwm/code/deploy/heft_mapping \
  code_cwm/code/deploy/setup_for_CaWoSched \
  code_cawosched/deploy/multi_machine_scheduler
do
  if [ ! -x "$bin" ]; then
    echo "ERROR: $bin missing or not executable. Re-run ./setup.sh." >&2
    exit 1
  fi
done

# shellcheck disable=SC1091
source .venv/bin/activate

for tool in simex jupyter bc python3; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "ERROR: '$tool' not on PATH after venv activation. Re-run ./setup.sh to refresh requirements." >&2
    exit 1
  fi
done
echo "OK"

# --- 1. Run the simexpal experiments -----------------------------------------
log "Launching simexpal experiments ($SIMEX_DIR)"
(
  cd "$SIMEX_DIR"
  simex e
  simex e launch --launch-through=fork
  simex e
)

# --- 2. Point the eval notebook at the active size ---------------------------
# The notebook hardcodes simexpal.config_for_dir("./../simex") (run from eval/),
# i.e. it always reads code_cwm/experiments/reproduce/simex. Refresh that as a
# symlink to the size we just ran.
ln -sfn "$SIZE/simex" "$REPRO_DIR/simex"

# --- 3. Execute the evaluation notebook --------------------------------------
# The notebook hardcodes plt.savefig("plots/shifted/<name>", ...). To keep one
# notebook usable for all sizes, write each run into plots/shifted_$SIZE/ and
# expose plots/shifted as a symlink to the current size.
log "Executing evaluation notebook ($EVAL_DIR)"
(
  cd "$EVAL_DIR"
  mkdir -p "plots/shifted_$SIZE"
  # ln -sfn cannot replace a real directory. If a previous run left
  # plots/shifted/ as a real dir (e.g. from before the symlink change), remove
  # it so the symlink can be recreated.
  if [ -d plots/shifted ] && [ ! -L plots/shifted ]; then
    rm -rf plots/shifted
  fi
  ln -sfn "shifted_$SIZE" plots/shifted
  jupyter nbconvert \
    --to notebook \
    --execute \
    --inplace \
    --ExecutePreprocessor.timeout=-1 \
    eval_final_EUROPAR.ipynb
)

# --- 4. Summary --------------------------------------------------------------
log "Done"
done_runs=$(find "$SIMEX_DIR/output" -name '*.status' 2>/dev/null | wc -l | tr -d ' ')
plot_count=$(find "$EVAL_DIR/plots/shifted_$SIZE" -name '*.png' 2>/dev/null | wc -l | tr -d ' ')
cat <<EOF

Experiment set:                       $SIZE  ($SIMEX_DIR)
Completed simex runs (.status files): $done_runs
Plots written to:                     $EVAL_DIR/plots/shifted_$SIZE/  ($plot_count PNGs)
Executed notebook:                    $EVAL_DIR/eval_final_EUROPAR.ipynb
EOF
