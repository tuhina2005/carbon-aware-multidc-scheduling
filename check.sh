#!/bin/bash
# Standalone smoke test: does the artifact look correctly configured?
# Runs *no* experiments and *no* builds — only verifies presence of tools,
# binaries, the venv, the Python packages, and the data needed to reproduce.
#
# Exit code 0 ==> ready for ./reproduce.sh.
# Exit code 1 ==> at least one check failed; see "FAIL" lines above.
#
# Re-runnable. Safe to run before or after ./setup.sh.

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

PASS=0
FAIL=0

log() { printf '\n=== %s ===\n' "$*"; }
ok()   { printf '  [ OK ]  %s\n' "$*"; PASS=$((PASS+1)); }
bad()  { printf '  [FAIL]  %s\n' "$*"; FAIL=$((FAIL+1)); }
note() { printf '  [info]  %s\n' "$*"; }

# --- 1. Host tools ----------------------------------------------------------
log "Host tools"
for tool in cmake ninja python3 bc sed bash; do
  if command -v "$tool" >/dev/null 2>&1; then
    ok "$tool found ($($tool --version 2>&1 | head -n1))"
  else
    bad "$tool not on PATH"
  fi
done

# C++ compiler — CMake picks `c++` by default, but g++/clang++ also work.
cxx=""
for c in c++ g++ clang++; do
  if command -v "$c" >/dev/null 2>&1; then cxx="$c"; break; fi
done
if [ -n "$cxx" ]; then
  cxx_version=$("$cxx" --version 2>&1 | head -n1)
  ok "C++ compiler: $cxx_version"
  note "C++20 required by both CMakeLists.txt; minimums: GCC>=10, Clang>=13, Apple Clang>=14, MSVC>=19.29"
else
  bad "no C++ compiler (c++ / g++ / clang++) on PATH"
fi

# --- 2. Built binaries -------------------------------------------------------
log "Built binaries (produced by ./setup.sh)"
for bin in \
  code_cwm/code/deploy/main \
  code_cwm/code/deploy/heft_mapping \
  code_cwm/code/deploy/setup_for_CaWoSched \
  code_cawosched/deploy/multi_machine_scheduler
do
  if [ -x "$bin" ]; then
    ok "$bin"
  else
    bad "$bin missing or not executable (run ./setup.sh)"
  fi
done

# --- 3. Python venv ----------------------------------------------------------
log "Python virtual environment"
if [ -d .venv ] && [ -x .venv/bin/python3 ]; then
  ok ".venv/ exists ($(.venv/bin/python3 --version 2>&1))"
  # Probe the load-bearing packages; do not full-import jupyter (slow).
  missing_py=()
  for pkg in simexpal numpy pandas matplotlib tabulate; do
    if ! .venv/bin/python3 -c "import $pkg" >/dev/null 2>&1; then
      missing_py+=("$pkg")
    fi
  done
  if [ ${#missing_py[@]} -eq 0 ]; then
    ok "Python deps importable: simexpal numpy pandas matplotlib tabulate"
  else
    bad "Python deps missing in .venv: ${missing_py[*]} (re-run ./setup.sh)"
  fi
  # simex CLI + jupyter binary
  for vbin in .venv/bin/simex .venv/bin/jupyter; do
    if [ -x "$vbin" ]; then
      ok "$vbin"
    else
      bad "$vbin missing (re-run ./setup.sh)"
    fi
  done
else
  bad ".venv/ not found or broken (run ./setup.sh)"
fi

# --- 4. Experiment inputs ----------------------------------------------------
log "Experiment inputs (reproduce/)"
REPRO_DIR=code_cwm/experiments/reproduce
INST_DIR=$REPRO_DIR/instances
EVAL_DIR=$REPRO_DIR/eval
if [ -e "$EVAL_DIR/eval_final_EUROPAR.ipynb" ]; then
  ok "$EVAL_DIR/eval_final_EUROPAR.ipynb"
else
  bad "$EVAL_DIR/eval_final_EUROPAR.ipynb missing"
fi

# All three size sets must be present so reproduce.sh --size {small,medium,full} works.
for size in small medium full; do
  d=$REPRO_DIR/$size/simex
  if [ -d "$d" ] && [ -e "$d/experiments.yml" ] && [ -e "$d/CaWoSched_app.sh" ] && [ -e "$d/adjust_rts_for_CaWoSched.py" ]; then
    n_inst=$(grep -c '^      - name:' "$d/experiments.yml" 2>/dev/null || echo 0)
    ok "$REPRO_DIR/$size/simex/  ($n_inst instances)"
  else
    bad "$REPRO_DIR/$size/simex/ missing or incomplete"
  fi
done

# Shared instances tree.
if [ -e "$INST_DIR/cluster_processors.json" ]; then
  ok "$INST_DIR/cluster_processors.json"
else
  bad "$INST_DIR/cluster_processors.json missing"
fi
n_dags=$(find "$INST_DIR/DAGs" -maxdepth 1 -name '*.dot' 2>/dev/null | wc -l | tr -d ' ')
if [ "${n_dags:-0}" -gt 0 ]; then
  ok "$n_dags DAG file(s) under $INST_DIR/DAGs/"
else
  bad "no .dot DAGs under $INST_DIR/DAGs/"
fi
n_profiles=$(find "$INST_DIR/Profiles" -name '*.json' 2>/dev/null | wc -l | tr -d ' ')
if [ "${n_profiles:-0}" -gt 0 ]; then
  ok "$n_profiles profile file(s) under $INST_DIR/Profiles/"
else
  bad "no profile JSONs under $INST_DIR/Profiles/"
fi

# --- 5. Smoke-test one binary -----------------------------------------------
log "Binary smoke test"
if [ -x code_cwm/code/deploy/main ]; then
  # `main` prints usage + non-zero exit when invoked with no args; that's enough
  # to confirm it dynamically links and starts up on this host.
  if code_cwm/code/deploy/main >/dev/null 2>&1; then
    ok "code_cwm/code/deploy/main runs (exit 0 with no args)"
  else
    rc=$?
    if [ "$rc" -lt 130 ]; then
      ok "code_cwm/code/deploy/main runs (exit $rc — expected for no-args)"
    else
      bad "code_cwm/code/deploy/main aborted with exit $rc — likely a runtime/linker issue"
    fi
  fi
else
  note "skipping smoke test; main binary not built"
fi

# --- 6. Summary --------------------------------------------------------------
log "Summary"
printf 'Passed: %d   Failed: %d\n' "$PASS" "$FAIL"
if [ "$FAIL" -gt 0 ]; then
  echo "Not ready. Fix the FAIL items above and re-run ./check.sh." >&2
  exit 1
fi
echo "Ready. Run ./reproduce.sh."
