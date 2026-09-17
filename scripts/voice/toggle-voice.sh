#!/usr/bin/env bash
# Toggle Jarvis voice on/off via sentinel file.
# Called by tmux keybinding (Prefix S).
set -euo pipefail

SENTINEL="/tmp/jarvis-voice-off"

if [ -f "$SENTINEL" ]; then
    rm "$SENTINEL"
    tmux display-message "🔊 Voice enabled"
else
    touch "$SENTINEL"
    # Kill any current speech
    kill "$(cat /tmp/jarvis-tts.pid 2>/dev/null)" 2>/dev/null || true
    tmux display-message "🔇 Voice disabled"
fi
