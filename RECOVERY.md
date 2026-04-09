# Jarvis Recovery Runbook

How to restore the Jarvis personal assistant system from scratch.

## Prerequisites

- Ubuntu/Debian Linux with systemd
- Python 3.13+
- Git, gh CLI
- Obsidian vault restored to `~/Documents/Day to day/`

## 1. Clone the repo

```bash
gh repo clone samuel-jenkins/llm-wiki ~/Projects/llm-wiki
cd ~/Projects/llm-wiki
```

## 2. Set up Python environment

```bash
cd scripts
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 3. Restore credentials

Create `~/.config/jarvis/credentials.env` with:

```
APPLE_MUSIC_DEVELOPER_TOKEN=...
APPLE_MUSIC_USER_TOKEN=...
POCKETCASTS_EMAIL=...
POCKETCASTS_PASSWORD=...
HEALTH_WEBHOOK_TOKEN=...
```

These are stored in your password manager (not in this repo).

## 4. Install systemd units

```bash
bash systemd/install.sh
systemctl --user daemon-reload
```

Enable the always-on health receiver:
```bash
systemctl --user enable --now jarvis-health-receiver.service
```

Enable all timers:
```bash
systemctl --user enable --now jarvis-daily.timer
systemctl --user enable --now jarvis-weekly-review.timer
systemctl --user enable --now jarvis-lint.timer
systemctl --user enable --now jarvis-project-status.timer
systemctl --user enable --now jarvis-collect-apple-music.timer
systemctl --user enable --now jarvis-collect-podcasts.timer
systemctl --user enable --now jarvis-db-maintenance.timer
systemctl --user enable --now jarvis-db-backup.timer
```

Verify:
```bash
systemctl --user list-timers --all | grep jarvis
```

## 5. Restore the database

If the vault is intact, `_llm/data/jarvis.db` should already be there.

If restoring from backup:
```bash
cp "_llm/data/backups/jarvis-YYYY-MM-DD.db" "_llm/data/jarvis.db"
```

Backups are kept for 7 days in `~/Documents/Day to day/_llm/data/backups/`.

If no backup exists, the collectors will recreate the schema on first run — you'll lose historical data but the system will work.

## 6. Verify everything

```bash
# Check database
PYTHONPATH=~/Projects/llm-wiki/scripts \
  ~/Projects/llm-wiki/scripts/.venv/bin/python \
  ~/Projects/llm-wiki/scripts/query_db.py collector-status

# Check health receiver
curl -s http://localhost:9876/health

# Run a test backup
bash ~/Projects/llm-wiki/scripts/backup-db.sh

# Check timers
systemctl --user list-timers --all | grep jarvis
```

## What lives where

| Component | Location | Backed up? |
|-----------|----------|-----------|
| Scripts & config | `~/Projects/llm-wiki/` | Git + GitHub |
| Systemd units | `~/.config/systemd/user/` (symlinks to repo) | Git + GitHub |
| Obsidian vault | `~/Documents/Day to day/` | Not yet — manual |
| SQLite database | `~/Documents/Day to day/_llm/data/jarvis.db` | Daily backup (7-day rotation) |
| Credentials | `~/.config/jarvis/credentials.env` | Password manager |
| DB backups | `~/Documents/Day to day/_llm/data/backups/` | Local only |
