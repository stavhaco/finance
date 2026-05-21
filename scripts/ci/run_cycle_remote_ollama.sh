#!/usr/bin/env bash
# Run one trading cycle using Ollama on your Mac (via LAN/Tailscale bridge).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${ROOT}"

ENV_FILE="${REMOTE_OLLAMA_ENV:-$ROOT/scripts/ci/remote-ollama.env}"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "$ENV_FILE"
  set +a
else
  echo "Missing $ENV_FILE"
  echo "  cp scripts/ci/remote-ollama.env.example scripts/ci/remote-ollama.env"
  echo "  # On Mac: ./scripts/mac/show_ollama_bridge_url.sh → paste OLLAMA_BASE_URL"
  exit 1
fi

"$(dirname "$0")/check_ollama_bridge.sh"
exec python3 -m demo_trader --once "$@"
