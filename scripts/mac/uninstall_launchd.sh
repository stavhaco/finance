#!/usr/bin/env bash
set -euo pipefail
PLIST_DST="$HOME/Library/LaunchAgents/com.finance.demo-trader.plist"
launchctl bootout "gui/$(id -u)/com.finance.demo-trader" 2>/dev/null || true
rm -f "$PLIST_DST"
echo "Removed com.finance.demo-trader LaunchAgent (if it was installed)."
