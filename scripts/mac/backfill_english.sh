#!/usr/bin/env bash
# Backfill English rationales (cycle logs -> SQLite) and knowledge article text.
#
# Usage:
#   ./scripts/mac/backfill_english.sh
#   ./scripts/mac/backfill_english.sh --dry-run
#   KNOWLEDGE_LIMIT=50 ./scripts/mac/backfill_english.sh
#
# Extra args are passed to backfill_cycle_rationales (e.g. --cycle-id 96).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_lib.sh
source "$SCRIPT_DIR/_lib.sh"
ENV_FILE="${DEMO_TRADER_ENV_FILE:-$SCRIPT_DIR/demo-trader.env}"
mac_resolve_repo_root "$SCRIPT_DIR" "$ENV_FILE"
cd "$REPO_ROOT"

PY="${REPO_ROOT}/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  echo "Missing $PY — create venv first." >&2
  exit 1
fi

KNOWLEDGE_LIMIT="${KNOWLEDGE_LIMIT:-0}"
KNOWLEDGE_ARGS=()
if [[ -n "$KNOWLEDGE_LIMIT" && "$KNOWLEDGE_LIMIT" != "0" ]]; then
  KNOWLEDGE_ARGS=(--limit "$KNOWLEDGE_LIMIT")
fi

echo "Repo: $REPO_ROOT"
echo "Step 1/2: cycle rationales from data/logs/cycles/*.json"
"$PY" -m demo_trader.backfill_cycle_rationales "$@"
echo ""
echo "Step 2/2: knowledge_events English enrichment (Ollama; set KNOWLEDGE_LIMIT=0 to skip volume cap)"
if ((${#KNOWLEDGE_ARGS[@]})); then
  "$PY" -m demo_trader.backfill_knowledge "${KNOWLEDGE_ARGS[@]}"
else
  "$PY" -m demo_trader.backfill_knowledge
fi
echo ""
echo "Backfill complete. Hard-refresh the dashboard to see updated English text."
