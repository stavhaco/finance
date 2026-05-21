#!/usr/bin/env bash
# Full paper-trader cycle without Ollama (for CI / cloud agents).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}"
export DEMO_TRADER_DRY_RUN=1
export DEMO_TRADER_MAYA_ENABLED=0
export DEMO_TRADER_KNOWLEDGE_ENRICH_ON_INGEST=0
export DEMO_TRADER_ENFORCE_TASE_HOURS=0
export DEMO_TRADER_CYCLE_LOG_ENABLED=1
exec python3 -m demo_trader --once --dry-run "$@"
