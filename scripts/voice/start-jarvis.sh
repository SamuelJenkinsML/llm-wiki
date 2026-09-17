#!/usr/bin/env bash
# Launch the full Jarvis experience — tmux session with Claude Code + STT + voice controls.
# Usage: start-jarvis.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
SESSION="jarvis"

# Source credentials for TTS
[ -f ~/.config/jarvis/credentials.env ] && source ~/.config/jarvis/credentials.env

# If session already exists, just attach
if tmux has-session -t "$SESSION" 2>/dev/null; then
    exec tmux attach -t "$SESSION"
fi

# Create new session
tmux new-session -d -s "$SESSION"

# Pane 0: Claude Code
tmux send-keys -t "$SESSION:0.0" "cd $REPO_DIR && claude" Enter

# Pane 1: STT listener (small bottom pane)
tmux split-window -t "$SESSION:0" -v -l 8
tmux send-keys -t "$SESSION:0.1" \
    "cd $REPO_DIR && source ~/.config/jarvis/credentials.env 2>/dev/null; PYTHONPATH=./scripts scripts/.venv/bin/python scripts/voice/stt.py" Enter

# Register keybindings
# Prefix S — toggle voice on/off
tmux bind-key -T prefix S run-shell "$SCRIPT_DIR/toggle-voice.sh"
# Prefix Q — stop current speech
tmux bind-key -T prefix Q run-shell "kill \$(cat /tmp/jarvis-tts.pid 2>/dev/null) 2>/dev/null; true"
# Prefix D — read daily briefing
tmux bind-key -T prefix D run-shell \
    "cd $REPO_DIR && source ~/.config/jarvis/credentials.env 2>/dev/null && PYTHONPATH=./scripts nohup scripts/.venv/bin/python scripts/voice/tts.py --daily >/dev/null 2>>/tmp/jarvis-tts.log &"
# Prefix M — toggle mic (pause/resume STT)
tmux bind-key -T prefix M run-shell "kill -SIGUSR1 \$(cat /tmp/jarvis-stt.pid 2>/dev/null) 2>/dev/null; true"

# Focus on Claude Code pane
tmux select-pane -t "$SESSION:0.0"

# Speak greeting (background, don't block attach)
cd "$REPO_DIR"
PYTHONPATH=./scripts nohup scripts/.venv/bin/python scripts/voice/tts.py --greet \
    >/dev/null 2>>/tmp/jarvis-tts.log &

# Attach to session
exec tmux attach -t "$SESSION"
