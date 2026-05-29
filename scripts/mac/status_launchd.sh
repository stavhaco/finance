#!/usr/bin/env bash
# Check demo-trader LaunchAgents (cycle + enrich).
set -euo pipefail

DOMAIN="gui/$(id -u)"
FAIL=0

_status_one() {
  local label="$1"
  local log_stem="$2"
  local PLIST="$HOME/Library/LaunchAgents/${label}.plist"

  echo "=== $label ==="
  echo "Plist: $PLIST"
  if [[ ! -f "$PLIST" ]]; then
    echo "  exists: no"
    FAIL=1
    return
  fi
  echo "  exists: yes"

  if launchctl print "${DOMAIN}/${label}" &>/dev/null; then
    echo "  loaded: yes"
    launchctl print "${DOMAIN}/${label}" 2>/dev/null | grep -E 'state =|last exit|runs =|path =' | head -6 || true
  else
    echo "  loaded: no"
    FAIL=1
  fi

  local REPO=""
  REPO="$(/usr/bin/plutil -extract WorkingDirectory raw -o - "$PLIST" 2>/dev/null || true)"
  if [[ -n "$REPO" ]]; then
    for f in "$REPO/data/logs/${log_stem}.stdout.log" "$REPO/data/logs/${log_stem}.stderr.log"; do
      if [[ -f "$f" ]]; then
        echo "  log: $f ($(wc -c <"$f" | tr -d ' ') bytes)"
      fi
    done
  fi
  echo ""
}

_status_one "com.finance.demo-trader" "demo-trader"
_status_one "com.finance.demo-trader-enrich" "demo-trader-enrich"

if [[ "$FAIL" -ne 0 ]]; then
  echo "Install missing agents:"
  echo "  ./scripts/mac/install_launchd_all.sh"
  exit 1
fi
