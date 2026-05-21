#!/usr/bin/env bash
# One paper-trader cycle with real Ollama (after setup_ollama.sh).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}"
export OLLAMA_BASE_URL="${OLLAMA_BASE_URL:-http://127.0.0.1:11434}"
export OLLAMA_MODEL="${OLLAMA_MODEL:-llama3.2:1b}"
export DEMO_TRADER_MAYA_ENABLED="${DEMO_TRADER_MAYA_ENABLED:-0}"
export DEMO_TRADER_KNOWLEDGE_ENRICH_ON_INGEST="${DEMO_TRADER_KNOWLEDGE_ENRICH_ON_INGEST:-0}"

"$(dirname "$0")/setup_ollama.sh"
exec python3 -m demo_trader --once "$@"
