#!/bin/bash
# Install/restore Jarvis systemd units by symlinking from this repo
# Usage: bash systemd/install.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TARGET_DIR="$HOME/.config/systemd/user"

mkdir -p "$TARGET_DIR"

count=0
for unit in "$SCRIPT_DIR"/jarvis-*.service "$SCRIPT_DIR"/jarvis-*.timer; do
    [ -f "$unit" ] || continue
    name="$(basename "$unit")"
    ln -sf "$unit" "$TARGET_DIR/$name"
    echo "  Linked: $name"
    count=$((count + 1))
done

echo "Installed $count unit files into $TARGET_DIR"
echo ""
echo "Reload and enable timers:"
echo "  systemctl --user daemon-reload"
echo "  systemctl --user enable --now jarvis-health-receiver.service"

# List all jarvis timers for the user to enable
echo ""
echo "Enable timers with:"
for timer in "$SCRIPT_DIR"/jarvis-*.timer; do
    [ -f "$timer" ] || continue
    echo "  systemctl --user enable --now $(basename "$timer")"
done
