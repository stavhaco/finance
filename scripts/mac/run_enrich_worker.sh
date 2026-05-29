#!/usr/bin/env bash
# Drain async knowledge enrichment jobs (run beside launchd trading cycles).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_lib.sh
source "$SCRIPT_DIR/_lib.sh"

ENV_FILE="${DEMO_TRADER_ENV_FILE:-$SCRIPT_DIR/demo-trader.env}"
mac_resolve_repo_root "$SCRIPT_DIR" "$ENV_FILE"
cd "$REPO_ROOT"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "$ENV_FILE"
  set +a
fi

if [[ -x "$REPO_ROOT/.venv/bin/python" ]]; then
  PY="$REPO_ROOT/.venv/bin/python"
elif [[ -n "${PYTHON_BIN:-}" ]]; then
  PY="$PYTHON_BIN"
else
  echo "ERROR: $REPO_ROOT/.venv/bin/python not found." >&2
  exit 1
fi

export PYTHONPATH="$REPO_ROOT${PYTHONPATH:+:$PYTHONPATH}"
exec "$PY" -m demo_trader.enrich_worker "$@"
