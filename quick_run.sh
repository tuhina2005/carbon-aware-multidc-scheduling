#!/bin/bash
# Convenience wrapper: build + run the whole artifact pipeline in one go.
# Equivalent to: ./setup.sh && ./reproduce.sh

set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

log() { printf '\n=== %s ===\n' "$*"; }

START=$(date +%s)

log "running the setup script"
./setup.sh
SETUP_END=$(date +%s)
log "setup done ($((SETUP_END - START))s)"

log "running the experiments + evaluation"
./reproduce.sh "$@"
END=$(date +%s)
log "reproduce done ($((END - SETUP_END))s)"

TOTAL=$((END - START))
printf '\nTotal elapsed: %ds (%dm %ds)\n' "$TOTAL" $((TOTAL / 60)) $((TOTAL % 60))
