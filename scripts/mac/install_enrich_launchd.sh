#!/usr/bin/env bash
# Install macOS LaunchAgent for async knowledge enrichment (batch every 60s).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_lib.sh
source "$SCRIPT_DIR/_lib.sh"

ENV_FILE="${DEMO_TRADER_ENV_FILE:-$SCRIPT_DIR/demo-trader.env}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Create $ENV_FILE from demo-trader.env.example first." >&2
  exit 1
fi

mac_resolve_repo_root "$SCRIPT_DIR" "$ENV_FILE"

ENRICH_SCRIPT="$SCRIPT_DIR/run_enrich_worker.sh"
PLIST_SRC="$SCRIPT_DIR/com.finance.demo-trader-enrich.plist.template"
PLIST_DST="$HOME/Library/LaunchAgents/com.finance.demo-trader-enrich.plist"

chmod +x "$ENRICH_SCRIPT"
mkdir -p "$REPO_ROOT/data/logs"

_mac_persist_repo_root() {
  if grep -qE '^REPO_ROOT=' "$ENV_FILE" 2>/dev/null; then
    if [[ "$(uname)" == "Darwin" ]]; then
      sed -i '' "s|^REPO_ROOT=.*|REPO_ROOT=$REPO_ROOT|" "$ENV_FILE"
    else
      sed -i "s|^REPO_ROOT=.*|REPO_ROOT=$REPO_ROOT|" "$ENV_FILE"
    fi
  else
    echo "REPO_ROOT=$REPO_ROOT" >>"$ENV_FILE"
  fi
  echo "Set REPO_ROOT in $ENV_FILE"
}

if grep -q 'REPO_ROOT=.*YOU' "$ENV_FILE" 2>/dev/null || ! grep -qE '^REPO_ROOT=/.+' "$ENV_FILE" 2>/dev/null; then
  _mac_persist_repo_root
fi

sed \
  -e "s|__REPO_ROOT__|$REPO_ROOT|g" \
  -e "s|__ENRICH_SCRIPT__|$ENRICH_SCRIPT|g" \
  -e "s|__ENV_FILE__|$ENV_FILE|g" \
  "$PLIST_SRC" > "$PLIST_DST"

launchctl bootout "gui/$(id -u)/com.finance.demo-trader-enrich" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST_DST"
launchctl enable "gui/$(id -u)/com.finance.demo-trader-enrich"

echo "Installed $PLIST_DST"
echo "Logs: $REPO_ROOT/data/logs/demo-trader-enrich.{stdout,stderr}.log"
echo ""
echo "Run one batch now:"
echo "  launchctl kickstart -k gui/$(id -u)/com.finance.demo-trader-enrich"
