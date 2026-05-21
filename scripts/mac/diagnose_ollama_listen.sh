#!/usr/bin/env bash
# Show whether Ollama is listening on LAN (0.0.0.0) or localhost only.
set -euo pipefail

PORT="${OLLAMA_PORT:-11434}"

echo "=== Ollama listen diagnose (port ${PORT}) ==="
echo ""

if command -v lsof >/dev/null 2>&1; then
  echo "Listening sockets:"
  lsof -nP -iTCP:"${PORT}" -sTCP:LISTEN 2>/dev/null || echo "  (nothing listening on ${PORT})"
  echo ""
  if lsof -nP -iTCP:"${PORT}" -sTCP:LISTEN 2>/dev/null | grep -q "127.0.0.1:${PORT}"; then
    if ! lsof -nP -iTCP:"${PORT}" -sTCP:LISTEN 2>/dev/null | grep -qE '\*:'"${PORT}"'|0\.0\.0\.0:'"${PORT}"; then
      echo "PROBLEM: Ollama is bound to 127.0.0.1 only — cloud/LAN cannot connect."
      echo "  Fix: ./scripts/mac/restart_ollama_lan.sh"
      echo "  Or:  export OLLAMA_HOST=0.0.0.0:11434 && killall ollama && open -a Ollama"
    fi
  fi
  if lsof -nP -iTCP:"${PORT}" -sTCP:LISTEN 2>/dev/null | grep -qE '\*:'"${PORT}"'|0\.0\.0\.0:'"${PORT}"; then
    echo "OK: Ollama appears to listen on all interfaces (LAN bridge possible)."
  fi
else
  echo "(install lsof for socket details)"
fi

echo ""
echo "launchctl OLLAMA_HOST=$(launchctl getenv OLLAMA_HOST 2>/dev/null || echo '(not set)')"
echo ""
"$(cd "$(dirname "$0")" && pwd)/show_ollama_bridge_url.sh"
