#!/usr/bin/env bash
# Same as ci/init — run on Mac Mini to write remote-ollama.env.
exec "$(cd "$(dirname "$0")/../ci" && pwd)/init_remote_ollama_env.sh" "$@"
