#!/usr/bin/env bash
# Quit Ollama and relaunch with OLLAMA_HOST so LAN/Tailscale can connect.
set -euo pipefail

export OLLAMA_HOST="${OLLAMA_HOST:-0.0.0.0:11434}"
launchctl setenv OLLAMA_HOST "${OLLAMA_HOST}" 2>/dev/null || true

echo "Stopping Ollama..."
osascript -e 'quit app "Ollama"' 2>/dev/null || true
killall ollama 2>/dev/null || true
sleep 2

echo "Starting Ollama with OLLAMA_HOST=${OLLAMA_HOST}"
# Launch from this shell so the child inherits OLLAMA_HOST (Dock-only open often does not).
if [[ -d "/Applications/Ollama.app" ]]; then
  open -a Ollama --env OLLAMA_HOST="${OLLAMA_HOST}"
else
  echo "Ollama.app not found in /Applications — start Ollama manually after: export OLLAMA_HOST=${OLLAMA_HOST}"
  exit 1
fi

sleep 3
echo ""
"$(cd "$(dirname "$0")" && pwd)/diagnose_ollama_listen.sh"
