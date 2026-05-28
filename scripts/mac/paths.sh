#!/usr/bin/env bash
# Print absolute paths for logs, DB, and launchd status (run from anywhere).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_lib.sh
source "$SCRIPT_DIR/_lib.sh"
ENV_FILE="${DEMO_TRADER_ENV_FILE:-$SCRIPT_DIR/demo-trader.env}"
mac_resolve_repo_root "$SCRIPT_DIR" "$ENV_FILE"
cd "$REPO_ROOT"

DB="${DEMO_TRADER_DB_PATH:-data/trader.db}"
STATE="${DEMO_TRADER_STATE_PATH:-data/paper_state.json}"
[[ "$DB" != /* ]] && DB="$REPO_ROOT/$DB"
[[ "$STATE" != /* ]] && STATE="$REPO_ROOT/$STATE"
STDOUT="$REPO_ROOT/data/logs/demo-trader.stdout.log"
STDERR="$REPO_ROOT/data/logs/demo-trader.stderr.log"

echo "REPO_ROOT=$REPO_ROOT"
echo "DB=$DB"
echo "STATE=$STATE"
echo "launchd stdout log=$STDOUT"
echo "launchd stderr log=$STDERR"
for f in "$DB" "$STDOUT" "$STDERR"; do
  if [[ -f "$f" ]]; then
    echo "  exists: $f ($(wc -c <"$f" | tr -d ' ') bytes, modified $(stat -f '%Sm' "$f" 2>/dev/null || stat -c '%y' "$f" 2>/dev/null))"
  else
    echo "  missing: $f"
  fi
done

if command -v sqlite3 >/dev/null && [[ -f "$DB" ]]; then
  echo "Latest cycles:"
  sqlite3 "$DB" "SELECT id, ts FROM cycles ORDER BY id DESC LIMIT 3;" 2>/dev/null || true
fi

echo ""
"$SCRIPT_DIR/status_launchd.sh" 2>/dev/null || true
