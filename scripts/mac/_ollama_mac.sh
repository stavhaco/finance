# shellcheck shell=bash
# Find and start Ollama on macOS (GUI app or CLI serve).

ollama_mac_find_app() {
  local c found
  local candidates=(
    "/Applications/Ollama.app"
    "${HOME}/Applications/Ollama.app"
  )
  for c in "${candidates[@]}"; do
    if [[ -d "$c" ]]; then
      echo "$c"
      return 0
    fi
  done
  if command -v mdfind >/dev/null 2>&1; then
    found="$(mdfind 'kMDItemCFBundleIdentifier == "com.electron.ollama"' 2>/dev/null | head -1)"
    if [[ -z "$found" ]]; then
      found="$(mdfind "kMDItemDisplayName == 'Ollama' && kMDItemContentType == 'com.apple.application-bundle'" 2>/dev/null | head -1)"
    fi
    if [[ -n "$found" && -d "$found" ]]; then
      echo "$found"
      return 0
    fi
  fi
  return 1
}

ollama_mac_find_cli() {
  command -v ollama 2>/dev/null || true
}

ollama_mac_stop() {
  osascript -e 'quit app "Ollama"' 2>/dev/null || true
  killall ollama 2>/dev/null || true
  killall "Ollama" 2>/dev/null || true
  sleep 2
}

# True if something is listening on all interfaces (LAN bridge OK).
ollama_mac_listens_lan() {
  local port="${1:-11434}"
  command -v lsof >/dev/null 2>&1 || return 1
  lsof -nP -iTCP:"${port}" -sTCP:LISTEN 2>/dev/null | grep -qE '\*:'"${port}"'|0\.0\.0\.0:'"${port}"'
}

ollama_mac_api_ok() {
  local base="${1:-http://127.0.0.1:11434}"
  curl -sf --connect-timeout 2 "${base%/}/api/tags" >/dev/null 2>&1
}

# Start with OLLAMA_HOST set. Returns 0 on success.
ollama_mac_start_lan() {
  local host_bind="${1:-0.0.0.0:11434}"
  export OLLAMA_HOST="$host_bind"
  launchctl setenv OLLAMA_HOST "$host_bind" 2>/dev/null || true

  local app cli bin log
  if app="$(ollama_mac_find_app)"; then
    echo "Found Ollama.app: $app"
    if [[ -x "$app/Contents/MacOS/Ollama" ]]; then
      echo "Starting via app binary with OLLAMA_HOST=${OLLAMA_HOST}"
      nohup env OLLAMA_HOST="$OLLAMA_HOST" "$app/Contents/MacOS/Ollama" >>/tmp/ollama-gui.log 2>&1 &
      return 0
    fi
    echo "Starting via open(1) with OLLAMA_HOST=${OLLAMA_HOST}"
    open "$app" --env "OLLAMA_HOST=${OLLAMA_HOST}" 2>/dev/null \
      || open -a "$app" --env "OLLAMA_HOST=${OLLAMA_HOST}" 2>/dev/null \
      || open -a "$app"
    return 0
  fi

  cli="$(ollama_mac_find_cli)"
  if [[ -n "$cli" ]]; then
    echo "No Ollama.app bundle found; starting CLI: $cli serve"
    echo "OLLAMA_HOST=${OLLAMA_HOST}"
    log="${OLLAMA_SERVE_LOG:-/tmp/ollama-serve.log}"
    nohup env OLLAMA_HOST="$OLLAMA_HOST" "$cli" serve >>"$log" 2>&1 &
    echo "Log: $log"
    return 0
  fi

  echo "ERROR: Could not find Ollama.app or ollama CLI."
  echo "  Install from https://ollama.com or: brew install --cask ollama"
  echo "  If the app exists elsewhere, set: OLLAMA_APP_PATH=/path/to/Ollama.app"
  return 1
}
