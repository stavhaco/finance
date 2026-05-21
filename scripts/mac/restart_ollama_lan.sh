#!/usr/bin/env bash
# Quit Ollama and relaunch with OLLAMA_HOST so LAN/Tailscale can connect.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_ollama_mac.sh
source "$SCRIPT_DIR/_ollama_mac.sh"

HOST_BIND="${OLLAMA_HOST:-0.0.0.0:11434}"

# Optional override when app is not under /Applications
if [[ -n "${OLLAMA_APP_PATH:-}" && -d "${OLLAMA_APP_PATH}" ]]; then
  ollama_mac_find_app() { echo "${OLLAMA_APP_PATH}"; }
fi

echo "=== Restart Ollama (LAN bridge) ==="
echo "OLLAMA_HOST=${HOST_BIND}"
echo ""

echo "Stopping Ollama..."
ollama_mac_stop

if ! ollama_mac_start_lan "$HOST_BIND"; then
  exit 1
fi

echo "Waiting for API..."
for _ in $(seq 1 20); do
  if curl -sf --connect-timeout 2 "http://127.0.0.1:11434/api/tags" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

echo ""
"$SCRIPT_DIR/diagnose_ollama_listen.sh"
