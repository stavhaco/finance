#!/usr/bin/env bash
# Check whether the demo-trader LaunchAgent is installed and loaded.
set -euo pipefail

LABEL="com.finance.demo-trader"
DOMAIN="gui/$(id -u)"
PLIST="$HOME/Library/LaunchAgents/${LABEL}.plist"

echo "Plist file: $PLIST"
if [[ -f "$PLIST" ]]; then
  echo "  exists: yes"
else
  echo "  exists: no  → run: ./scripts/mac/install_launchd.sh"
  exit 1
fi

if launchctl print "${DOMAIN}/${LABEL}" &>/dev/null; then
  echo "Service: loaded in ${DOMAIN}"
  launchctl print "${DOMAIN}/${LABEL}" 2>/dev/null | head -20
else
  echo "Service: NOT loaded in ${DOMAIN}"
  echo "  → run: ./scripts/mac/install_launchd.sh"
  exit 1
fi

# Resolve repo from plist WorkingDirectory when possible
REPO=""
if [[ -f "$PLIST" ]]; then
  REPO="$(/usr/bin/plutil -extract WorkingDirectory raw -o - "$PLIST" 2>/dev/null || true)"
fi
if [[ -n "$REPO" ]]; then
  echo ""
  echo "WorkingDirectory (from plist): $REPO"
  for f in "$REPO/data/logs/demo-trader.stdout.log" "$REPO/data/logs/demo-trader.stderr.log"; do
    if [[ -f "$f" ]]; then
      echo "  log: $f ($(wc -c <"$f" | tr -d ' ') bytes)"
    else
      echo "  log missing (agent may not have run yet): $f"
    fi
  done
fi
