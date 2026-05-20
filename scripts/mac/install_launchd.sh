#!/usr/bin/env bash
# Install macOS LaunchAgent for one-shot demo_trader cycles (every StartInterval seconds).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${DEMO_TRADER_ENV_FILE:-$SCRIPT_DIR/demo-trader.env}"

if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$ENV_FILE"
fi

REPO_ROOT="${REPO_ROOT:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
RUN_SCRIPT="$SCRIPT_DIR/run_cycle.sh"
PLIST_SRC="$SCRIPT_DIR/com.finance.demo-trader.plist.template"
PLIST_DST="$HOME/Library/LaunchAgents/com.finance.demo-trader.plist"

chmod +x "$RUN_SCRIPT"
mkdir -p "$REPO_ROOT/data/logs"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Create $ENV_FILE from demo-trader.env.example first." >&2
  exit 1
fi

sed \
  -e "s|__REPO_ROOT__|$REPO_ROOT|g" \
  -e "s|__RUN_SCRIPT__|$RUN_SCRIPT|g" \
  -e "s|__ENV_FILE__|$ENV_FILE|g" \
  "$PLIST_SRC" > "$PLIST_DST"

launchctl bootout "gui/$(id -u)/com.finance.demo-trader" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST_DST"
launchctl enable "gui/$(id -u)/com.finance.demo-trader"

echo "Installed $PLIST_DST"
echo "Logs: $REPO_ROOT/data/logs/demo-trader.{stdout,stderr}.log"
echo ""
echo "Run one cycle now:"
echo "  launchctl kickstart -k gui/$(id -u)/com.finance.demo-trader"
echo "Or manually:"
echo "  $RUN_SCRIPT"
echo ""
echo "Check status: $SCRIPT_DIR/status_launchd.sh"
