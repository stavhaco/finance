# shellcheck shell=bash
# Shared helpers for scripts/mac/*.sh

_mac_script_dir() {
  cd "$(dirname "${BASH_SOURCE[1]}")" && pwd
}

# Detect git repo root (contains demo_trader/).
_mac_detect_repo_root() {
  local script_dir="$1"
  local root
  root="$(cd "$script_dir/../.." && pwd)"
  if [[ -f "$root/demo_trader/__main__.py" ]]; then
    echo "$root"
    return 0
  fi
  echo "$root"
}

_mac_repo_root_invalid() {
  local r="${1:-}"
  [[ -z "$r" ]] && return 0
  [[ "$r" == *"/YOU/"* ]] && return 0
  [[ "$r" == *"YOU/path"* ]] && return 0
  [[ ! -f "$r/demo_trader/__main__.py" ]] && return 0
  return 1
}

# Sets REPO_ROOT in caller's scope: env file, then auto-detect if missing/placeholder.
mac_resolve_repo_root() {
  local script_dir="$1"
  local env_file="${2:-}"
  local detected
  detected="$(_mac_detect_repo_root "$script_dir")"

  if [[ -n "${REPO_ROOT:-}" ]] && ! _mac_repo_root_invalid "$REPO_ROOT"; then
    return 0
  fi

  if [[ -f "$env_file" ]]; then
    # shellcheck disable=SC1090
    set -a
    # shellcheck source=/dev/null
    source "$env_file"
    set +a
  fi

  if _mac_repo_root_invalid "${REPO_ROOT:-}"; then
    REPO_ROOT="$detected"
    echo "NOTE: REPO_ROOT not set or still placeholder — using: $REPO_ROOT" >&2
    echo "      Fix scripts/mac/demo-trader.env → REPO_ROOT=$REPO_ROOT" >&2
  fi
  export REPO_ROOT
}
