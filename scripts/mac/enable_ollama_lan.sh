#!/usr/bin/env bash
# Expose Ollama on your LAN so a Cursor cloud agent can call your Mac's models.
# Run on the Mac Mini (not in the cloud VM). Restart Ollama.app after this.
set -euo pipefail

HOST_BIND="${OLLAMA_HOST:-0.0.0.0:11434}"

echo "=== Ollama LAN bridge (macOS) ==="
echo "Binding Ollama to: ${HOST_BIND}"
echo ""

# Persists for GUI-launched Ollama.app after restart (user session).
launchctl setenv OLLAMA_HOST "${HOST_BIND}" 2>/dev/null || true

# Also print for manual shell / launchd overrides.
echo "To apply in the current terminal only:"
echo "  export OLLAMA_HOST=${HOST_BIND}"
echo ""
echo "Next steps:"
echo "  1. ./scripts/mac/restart_ollama_lan.sh   # quit + relaunch with OLLAMA_HOST (recommended)"
echo "     (Dock-only restart often keeps 127.0.0.1 — LAN stays ✗)"
echo "  2. ./scripts/mac/diagnose_ollama_listen.sh"
echo "  3. ./scripts/mac/show_ollama_bridge_url.sh  — need ✓ on LAN or Tailscale"
echo "  3. Copy the URL into scripts/ci/remote-ollama.env (see remote-ollama.env.example)"
echo "  4. Cloud agent: OLLAMA_BASE_URL=<that URL>  OR  ./scripts/ci/run_cycle_remote_ollama.sh"
echo ""
echo "Security: only use on home LAN or Tailscale. macOS Firewall may prompt — allow Ollama."

LAN_IP=""
if command -v ipconfig >/dev/null 2>&1; then
  for iface in en0 en1 bridge0; do
    LAN_IP="$(ipconfig getifaddr "$iface" 2>/dev/null || true)"
    [[ -n "$LAN_IP" ]] && break
  done
fi
if [[ -n "$LAN_IP" ]]; then
  echo ""
  echo "Likely LAN URL for cloud agent:"
  echo "  OLLAMA_BASE_URL=http://${LAN_IP}:11434"
fi
if command -v tailscale >/dev/null 2>&1; then
  TS_IP="$(tailscale ip -4 2>/dev/null | head -1 || true)"
  if [[ -n "$TS_IP" ]]; then
    echo "  OLLAMA_BASE_URL=http://${TS_IP}:11434   # Tailscale (works off-LAN)"
  fi
fi
