#!/usr/bin/env bash
# Run a Jarvis operation via Claude Code headless mode
# Usage: run-jarvis.sh <prompt-file>

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"

# Source config if it exists; fall back to defaults
[ -f "$REPO_DIR/jarvis.conf" ] && source "$REPO_DIR/jarvis.conf"

PROMPT_DIR="$REPO_DIR/prompts"
PROMPT_FILE="${1:?Usage: run-jarvis.sh <prompt-name> (e.g., daily-briefing)}"
PROMPT_PATH="${PROMPT_DIR}/${PROMPT_FILE}.md"

if [ ! -f "$PROMPT_PATH" ]; then
    echo "Error: Prompt file not found: $PROMPT_PATH" >&2
    exit 1
fi

PROMPT=$(cat "$PROMPT_PATH")

# Inject current date/time so the model doesn't have to guess the day of week
TODAY_DATE=$(date +%Y-%m-%d)
TODAY_DAY=$(date +%A)
TODAY_FULL=$(date "+%A, %B %d, %Y")
PROMPT="Today is ${TODAY_FULL} (${TODAY_DATE}). The day of the week is ${TODAY_DAY}.

${PROMPT}"

# Per-prompt tool override: prompts/<name>.tools, one comma-separated line.
# Falls back to the default set when no override file exists.
TOOLS_PATH="${PROMPT_DIR}/${PROMPT_FILE}.tools"
DEFAULT_TOOLS="Bash,Read,Write,Edit,Glob,Grep,mcp__claude_ai_Google_Calendar__gcal_list_events,mcp__claude_ai_Google_Calendar__gcal_get_event,mcp__claude_ai_Gmail__gmail_get_profile,mcp__claude_ai_Gmail__gmail_search_messages,mcp__claude_ai_Gmail__gmail_read_message"

if [ -f "$TOOLS_PATH" ]; then
    ALLOWED_TOOLS="$(tr -d '\n' < "$TOOLS_PATH")"
else
    ALLOWED_TOOLS="$DEFAULT_TOOLS"
fi

cd "$REPO_DIR"

exec claude \
    -p "$PROMPT" \
    --allowedTools "$ALLOWED_TOOLS"
