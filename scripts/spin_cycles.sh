#!/usr/bin/env bash
# Repeat `demo_trader --once` forever (recommended for systemd/docker — one process restarts each cycle).
# Prefer this over `python -m demo_trader` loop when you want the OS to supervise each invocation.
#
# Usage:
#   ./scripts/spin_cycles.sh                     # respects DEMO_TRADER_INTERVAL_MINUTES (default 15 min)
#   DEMO_TRADER_INTERVAL_MINUTES=2 ./scripts/spin_cycles.sh --dry-run
#   ./scripts/spin_cycles.sh --dry-run           # CI / without Ollama

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"

INTERVAL_MIN="${DEMO_TRADER_INTERVAL_MINUTES:-15}"
SLEEP_SEC=$((INTERVAL_MIN * 60))
if (( SLEEP_SEC < 60 )); then
  SLEEP_SEC=60
fi

PY="${PYTHON_BIN:-python3}"

echo "spin_cycles: repo=$ROOT interval=${INTERVAL_MIN}m extra_args=$*" >&2

while true; do
  echo "--- $(date -u +%Y-%m-%dT%H:%M:%SZ) starting cycle ---" >&2
  if ! "$PY" -m demo_trader --once "$@"; then
    echo "WARN: cycle failed; sleeping ${SLEEP_SEC}s before retry" >&2
  fi
  echo "sleeping ${SLEEP_SEC}s..." >&2
  sleep "$SLEEP_SEC"
done
