#!/usr/bin/env bash
# Install and start Ollama for cloud-agent / CI (no systemd).
set -euo pipefail

MODEL="${OLLAMA_MODEL:-llama3.2:1b}"
API="http://127.0.0.1:11434"

if ! command -v ollama >/dev/null 2>&1; then
  if ! command -v zstd >/dev/null 2>&1; then
    sudo apt-get update -qq
    sudo apt-get install -y -qq zstd
  fi
  curl -fsSL https://ollama.com/install.sh | sh
fi

if ! curl -sf --connect-timeout 2 "${API}/api/tags" >/dev/null 2>&1; then
  echo "Starting ollama serve (background)..."
  nohup ollama serve >>/tmp/ollama-serve.log 2>&1 &
  for _ in $(seq 1 30); do
    if curl -sf --connect-timeout 2 "${API}/api/tags" >/dev/null 2>&1; then
      break
    fi
    sleep 1
  done
fi

if ! curl -sf "${API}/api/tags" | grep -q "\"name\":\"${MODEL}\""; then
  echo "Pulling model ${MODEL}..."
  ollama pull "${MODEL}"
fi

curl -sf "${API}/api/tags" | python3 -m json.tool 2>/dev/null | head -30 || true
echo "Ollama ready at ${API} (model=${MODEL})"
