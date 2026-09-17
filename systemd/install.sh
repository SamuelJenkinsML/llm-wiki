#!/bin/bash
# Install Jarvis systemd units by generating from templates and symlinking
# Usage: bash systemd/install.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
TARGET_DIR="$HOME/.config/systemd/user"

# Source config if it exists; fall back to defaults
[ -f "$REPO_DIR/jarvis.conf" ] && source "$REPO_DIR/jarvis.conf"
JARVIS_CREDENTIALS_FILE="${JARVIS_CREDENTIALS_FILE:-$HOME/.config/jarvis/credentials.env}"

mkdir -p "$TARGET_DIR"

# Step 1: Generate .service files from .service.template files
echo "Generating service files from templates..."
generated=0
for template in "$SCRIPT_DIR"/jarvis-*.service.template; do
    [ -f "$template" ] || continue
    name="$(basename "$template" .template)"
    sed -e "s|@@REPO_DIR@@|$REPO_DIR|g" \
        -e "s|@@HOME@@|$HOME|g" \
        -e "s|@@CREDENTIALS@@|$JARVIS_CREDENTIALS_FILE|g" \
        "$template" > "$SCRIPT_DIR/$name"
    echo "  Generated: $name"
    generated=$((generated + 1))
done
echo "Generated $generated service files."
echo ""

# Step 2: Symlink all service and timer files
echo "Installing unit files..."
count=0
for unit in "$SCRIPT_DIR"/jarvis-*.service "$SCRIPT_DIR"/jarvis-*.timer; do
    [ -f "$unit" ] || continue
    # Skip templates
    [[ "$unit" == *.template ]] && continue
    name="$(basename "$unit")"
    ln -sf "$unit" "$TARGET_DIR/$name"
    echo "  Linked: $name"
    count=$((count + 1))
done

echo ""
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
