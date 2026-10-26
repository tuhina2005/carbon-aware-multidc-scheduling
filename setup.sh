#!/bin/bash
# Full setup for the artifact evaluation:
#   1. Build CWM / HEFT-SL (code_cwm/code)
#   2. Build CaWoSched competitor (code_cawosched)
#   3. Create a Python virtual environment at .venv/ and install requirements.txt
#
# Idempotent: safe to re-run. Each build.sh wipes its own build/ and deploy/ dirs.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

log() { printf '\n=== %s ===\n' "$*"; }

# --- Sanity check: required tools -------------------------------------------
log "Checking required tools"
missing=()
for tool in cmake ninja python3 bc sed; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    missing+=("$tool")
  fi
done
# CMake auto-detects the compiler via `cc`/`c++`; verify at least one is present.
if ! command -v c++ >/dev/null 2>&1 && ! command -v g++ >/dev/null 2>&1 && ! command -v clang++ >/dev/null 2>&1; then
  missing+=("c++ (no g++/clang++ on PATH)")
fi
if [ "${#missing[@]}" -gt 0 ]; then
  echo "ERROR: missing required tools: ${missing[*]}" >&2
  echo "Install them and re-run. On Debian/Ubuntu: apt-get install build-essential cmake ninja-build python3-venv bc" >&2
  echo "On macOS (Homebrew + Xcode CLT): xcode-select --install && brew install cmake ninja" >&2
  exit 1
fi

# Report the compiler that CMake will pick up so build failures are easier to triage.
# Both CMakeLists.txt require C++20 (CMAKE_CXX_STANDARD 20 with _REQUIRED). Practical floors:
#   GCC >= 10, Clang >= 13, Apple Clang >= 14 (Xcode 14+), MSVC >= 19.29 (VS 2019 16.11).
if command -v c++ >/dev/null 2>&1; then
  echo "C++ compiler: $(c++ --version 2>&1 | head -n1)"
elif command -v g++ >/dev/null 2>&1; then
  echo "C++ compiler: $(g++ --version 2>&1 | head -n1)"
elif command -v clang++ >/dev/null 2>&1; then
  echo "C++ compiler: $(clang++ --version 2>&1 | head -n1)"
fi
echo "OK"

# --- 1. Build CWM / HEFT-SL --------------------------------------------------
log "Building CWM / HEFT-SL (code_cwm/code)"
( cd code_cwm/code && ./build.sh )

# --- 2. Build CaWoSched competitor ------------------------------------------
log "Building CaWoSched (code_cawosched)"
( cd code_cawosched && ./build.sh )

# --- 3. Python venv + requirements ------------------------------------------
log "Setting up Python virtual environment at .venv/"
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
deactivate

# --- 4. Summary --------------------------------------------------------------
log "Setup complete"
