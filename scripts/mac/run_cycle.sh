#!/usr/bin/env bash
# Single trading cycle — intended for launchd/cron, not a long-running Python loop.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_lib.sh
source "$SCRIPT_DIR/_lib.sh"

ENV_FILE="${DEMO_TRADER_ENV_FILE:-$SCRIPT_DIR/demo-trader.env}"

mac_resolve_repo_root "$SCRIPT_DIR" "$ENV_FILE"
cd "$REPO_ROOT"

mkdir -p data/logs

if [[ -x "$REPO_ROOT/.venv/bin/python" ]]; then
  PY="$REPO_ROOT/.venv/bin/python"
elif [[ -n "${PYTHON_BIN:-}" ]]; then
  PY="$PYTHON_BIN"
else
  echo "ERROR: $REPO_ROOT/.venv/bin/python not found." >&2
  echo "  cd $REPO_ROOT && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2
  exit 1
fi

export PYTHONPATH="$REPO_ROOT${PYTHONPATH:+:$PYTHONPATH}"

echo "run_cycle: python=$PY ($("$PY" --version 2>&1))" >&2

exec "$PY" -m demo_trader --once "$@"
