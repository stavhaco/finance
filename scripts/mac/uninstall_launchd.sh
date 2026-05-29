#!/usr/bin/env bash
set -euo pipefail
DOMAIN="gui/$(id -u)"
for LABEL in com.finance.demo-trader com.finance.demo-trader-enrich; do
  launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
  rm -f "$HOME/Library/LaunchAgents/${LABEL}.plist"
  echo "Removed $LABEL (if installed)."
done
