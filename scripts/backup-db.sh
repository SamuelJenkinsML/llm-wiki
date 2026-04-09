#!/bin/bash
# Daily SQLite backup using Python's sqlite3.backup() — safe, consistent even under load
set -euo pipefail

DB="$HOME/Documents/Day to day/_llm/data/jarvis.db"
BACKUP_DIR="$HOME/Documents/Day to day/_llm/data/backups"
MAX_BACKUPS=7

if [ ! -f "$DB" ]; then
    echo "ERROR: Database not found at $DB" >&2
    exit 1
fi

mkdir -p "$BACKUP_DIR"

BACKUP_FILE="$BACKUP_DIR/jarvis-$(date +%Y-%m-%d).db"

python3 -c "
import sqlite3, sys
src = sqlite3.connect(sys.argv[1])
dst = sqlite3.connect(sys.argv[2])
src.backup(dst)
dst.close()
src.close()
" "$DB" "$BACKUP_FILE"

echo "Backup created: $BACKUP_FILE ($(du -h "$BACKUP_FILE" | cut -f1))"

# Rotate: keep only last N backups
ls -1t "$BACKUP_DIR"/jarvis-*.db 2>/dev/null | tail -n +$((MAX_BACKUPS + 1)) | xargs -r rm -f

echo "Backups retained: $(ls -1 "$BACKUP_DIR"/jarvis-*.db 2>/dev/null | wc -l)/$MAX_BACKUPS"
