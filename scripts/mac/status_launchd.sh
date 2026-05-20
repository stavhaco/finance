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
