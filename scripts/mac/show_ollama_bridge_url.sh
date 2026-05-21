#!/usr/bin/env bash
# Print OLLAMA_BASE_URL values to paste into cloud agent env (run on Mac).
set -euo pipefail

PORT="${OLLAMA_PORT:-11434}"
MODEL="${OLLAMA_MODEL:-llama3.2}"

echo "=== Ollama bridge URLs (set OLLAMA_BASE_URL in cloud agent) ==="
echo ""

check_local() {
  if curl -sf --connect-timeout 2 "http://127.0.0.1:${PORT}/api/tags" >/dev/null 2>&1; then
    echo "OK: Ollama responding on 127.0.0.1:${PORT}"
    curl -sf "http://127.0.0.1:${PORT}/api/tags" | python3 -c "
import json,sys
d=json.load(sys.stdin)
names=[m.get('name','') for m in d.get('models',[])]
print('Models:', ', '.join(names) if names else '(none — run: ollama pull ${MODEL})')
" 2>/dev/null || true
  else
    echo "WARN: Ollama not reachable on 127.0.0.1:${PORT} — start Ollama.app first"
  fi
  echo ""
}

check_url() {
  local label="$1"
  local url="$2"
  printf "%-12s %s\n" "${label}:" "${url}"
  if curl -sf --connect-timeout 3 "${url}/api/tags" >/dev/null 2>&1; then
    echo "             ✓ reachable from this Mac"
  else
    echo "             ✗ not reachable (firewall / OLLAMA_HOST / wrong IP)"
  fi
}

check_local

if command -v ipconfig >/dev/null 2>&1; then
  for iface in en0 en1; do
    ip="$(ipconfig getifaddr "$iface" 2>/dev/null || true)"
    if [[ -n "$ip" ]]; then
      check_url "Wi‑Fi/LAN (${iface})" "http://${ip}:${PORT}"
    fi
  done
fi

if command -v tailscale >/dev/null 2>&1; then
  ts="$(tailscale ip -4 2>/dev/null | head -1 || true)"
  if [[ -n "$ts" ]]; then
    check_url "Tailscale" "http://${ts}:${PORT}"
  fi
fi

echo ""
echo "Paste into scripts/ci/remote-ollama.env (gitignored), e.g.:"
echo "  OLLAMA_BASE_URL=http://<pick-working-host>:${PORT}"
echo "  OLLAMA_MODEL=${MODEL}"
