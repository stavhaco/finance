#!/usr/bin/env bash
# After git pull: verify the trader can complete one cycle (dry-run).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_lib.sh
source "$SCRIPT_DIR/_lib.sh"
ENV_FILE="${DEMO_TRADER_ENV_FILE:-$SCRIPT_DIR/demo-trader.env}"
mac_resolve_repo_root "$SCRIPT_DIR" "$ENV_FILE"
cd "$REPO_ROOT"
echo "Repo: $REPO_ROOT"
if [[ -d "$REPO_ROOT/.git" ]]; then
  git pull --ff-only origin main
fi
chmod +x "$REPO_ROOT/scripts/smoke_cycle.sh"
"$REPO_ROOT/scripts/smoke_cycle.sh"
echo "smoke_cycle OK — safe to kick launchd: launchctl kickstart -k gui/\$(id -u)/com.finance.demo-trader"
