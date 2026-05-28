#!/usr/bin/env bash
# End-to-end smoke: one dry-run cycle with fast env (no Ollama, no Maya enrich spam).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec "$ROOT/scripts/ci/run_cycle_dry.sh" "$@"
