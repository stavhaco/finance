#!/usr/bin/env bash
# Verify cloud agent (or CI) can reach your Mac's Ollama.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ENV_FILE="${REMOTE_OLLAMA_ENV:-$ROOT/scripts/ci/remote-ollama.env}"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "$ENV_FILE"
  set +a
  echo "Loaded: $ENV_FILE"
else
  echo "No $ENV_FILE — using OLLAMA_BASE_URL from environment"
fi

BASE="${OLLAMA_BASE_URL:-http://127.0.0.1:11434}"
MODEL="${OLLAMA_MODEL:-llama3.2}"

echo "Checking Ollama at: $BASE"
if ! curl -sf --connect-timeout 5 "${BASE}/api/tags"; then
  echo ""
  echo "FAILED. On your Mac:"
  echo "  ./scripts/mac/enable_ollama_lan.sh   # then restart Ollama.app"
  echo "  ./scripts/mac/show_ollama_bridge_url.sh"
  echo "  # fix scripts/ci/remote-ollama.env with a ✓ URL"
  exit 1
fi

echo ""
echo "OK — bridge works."
python3 - <<'PY' 2>/dev/null || true
import json, os, urllib.request
base = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
with urllib.request.urlopen(base + "/api/tags", timeout=10) as r:
    d = json.load(r)
print("Models:", ", ".join(m.get("name", "") for m in d.get("models", [])) or "(none)")
PY

if [[ -n "${MODEL:-}" ]]; then
  if curl -sf "${BASE}/api/tags" | grep -q "\"name\":\"${MODEL}\""; then
    echo "Model ${MODEL} is available."
  else
    echo "WARN: model ${MODEL} not in list — on Mac run: ollama pull ${MODEL}"
  fi
fi
