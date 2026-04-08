#!/usr/bin/env bash
# Run a Jarvis operation via Claude Code headless mode
# Usage: run-jarvis.sh <prompt-file>

set -euo pipefail

PROMPT_DIR="/home/samuel-jenkins/Projects/llm-wiki/prompts"
PROMPT_FILE="${1:?Usage: run-jarvis.sh <prompt-name> (e.g., daily-briefing)}"
PROMPT_PATH="${PROMPT_DIR}/${PROMPT_FILE}.md"

if [ ! -f "$PROMPT_PATH" ]; then
    echo "Error: Prompt file not found: $PROMPT_PATH" >&2
    exit 1
fi

PROMPT=$(cat "$PROMPT_PATH")

cd /home/samuel-jenkins/Projects/llm-wiki

exec /home/samuel-jenkins/.local/bin/claude \
    -p "$PROMPT" \
    --allowedTools "Bash,Read,Write,Edit,Glob,Grep"
