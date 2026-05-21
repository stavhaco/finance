#!/usr/bin/env bash
# Quick check: is Homebrew/GUI Ollama ready for cloud agent bridge?
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_ollama_mac.sh
source "$SCRIPT_DIR/_ollama_mac.sh"

PORT="${OLLAMA_PORT:-11434}"
LAN_IP=""
if command -v ipconfig >/dev/null 2>&1; then
  for iface in en0 en1; do
    LAN_IP="$(ipconfig getifaddr "$iface" 2>/dev/null || true)"
    [[ -n "$LAN_IP" ]] && break
  done
fi

echo "=== Ollama bridge status ==="
if command -v lsof >/dev/null 2>&1; then
  lsof -nP -iTCP:"${PORT}" -sTCP:LISTEN 2>/dev/null || echo "(not listening on ${PORT})"
fi
echo ""

if ollama_mac_listens_lan "$PORT"; then
  echo "Listen: *:${PORT} — LAN bridge bind OK"
else
  echo "Listen: localhost-only or down — run: export OLLAMA_HOST=0.0.0.0:11434 && ollama serve"
fi

if ollama_mac_api_ok "http://127.0.0.1:${PORT}"; then
  echo "API:    127.0.0.1 OK"
else
  echo "API:    127.0.0.1 DOWN"
fi

if [[ -n "$LAN_IP" ]]; then
  if ollama_mac_api_ok "http://${LAN_IP}:${PORT}"; then
    echo "API:    http://${LAN_IP}:${PORT} OK — use in remote-ollama.env"
  else
    echo "API:    http://${LAN_IP}:${PORT} FAILED (firewall?)"
  fi
fi

CLI="$(ollama_mac_find_cli)"
[[ -n "$CLI" ]] && echo "CLI:    $CLI"
