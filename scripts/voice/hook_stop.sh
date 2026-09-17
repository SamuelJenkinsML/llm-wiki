#!/usr/bin/env bash
# Claude Code Stop hook — pipes response to Jarvis TTS in background.
# Reads hook JSON from stdin, forks tts.py, exits within 2 seconds.
set -euo pipefail

# Opt-out for unattended overnight jobs (e.g. jarvis-job-radar at 01:07).
[ "${JARVIS_TTS_DISABLE:-}" = "1" ] && exit 0

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"

# Source credentials for ElevenLabs API key
[ -f ~/.config/jarvis/credentials.env ] && source ~/.config/jarvis/credentials.env

# Read hook JSON from stdin
INPUT=$(cat)

# Fork TTS into background and exit immediately
cd "$REPO_DIR"
echo "$INPUT" | nohup \
    env PYTHONPATH="$REPO_DIR/scripts" \
    "$SCRIPT_DIR/../.venv/bin/python" "$SCRIPT_DIR/tts.py" --from-stdin \
    >/dev/null 2>>/tmp/jarvis-tts.log &

exit 0
