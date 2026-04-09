#!/usr/bin/env bash
# Run a Jarvis data collection script via Python venv
# Usage: run-collector.sh <script-name> (e.g., collect-lastfm)

set -euo pipefail

SCRIPT_DIR="/home/samuel-jenkins/Projects/llm-wiki/scripts"
SCRIPT_NAME="${1:?Usage: run-collector.sh <script-name> (e.g., collect-lastfm)}"

source "$SCRIPT_DIR/.venv/bin/activate"
exec python3 "$SCRIPT_DIR/${SCRIPT_NAME}.py"
