#!/usr/bin/env bash
# Install trading + enrichment LaunchAgents.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
"$SCRIPT_DIR/install_launchd.sh"
"$SCRIPT_DIR/install_enrich_launchd.sh"
echo ""
echo "Both agents installed. Kickstart:"
echo "  launchctl kickstart -k gui/\$(id -u)/com.finance.demo-trader"
echo "  launchctl kickstart -k gui/\$(id -u)/com.finance.demo-trader-enrich"
