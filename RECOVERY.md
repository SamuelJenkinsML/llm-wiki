# Recovery Runbook

How to restore the personal assistant system from scratch.

## Prerequisites

- Ubuntu/Debian Linux with systemd
- Python 3.13+
- Git, gh CLI
- Obsidian vault restored to its expected location

## 1. Clone the repo

```bash
git clone https://github.com/YOUR_USERNAME/llm-wiki ~/Projects/llm-wiki
cd ~/Projects/llm-wiki
```

## 2. Run setup

```bash
bash setup.sh
```

This will:
- Create `jarvis.conf` with your paths
- Generate `vault-config.md` from template
- Set up Python venv
- Generate systemd service files
- Optionally install systemd units

## 3. Restore credentials

If `~/.config/jarvis/credentials.env` wasn't backed up, recreate it from `credentials.env.example`:

```bash
cp credentials.env.example ~/.config/jarvis/credentials.env
# Fill in your API keys from your password manager
```

## 4. Enable systemd units

```bash
systemctl --user daemon-reload
systemctl --user enable --now jarvis-health-receiver.service

# Enable all timers
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

Backups are kept for 7 days in the vault's `_llm/data/backups/` directory.

If no backup exists, the collectors will recreate the schema on first run — you'll lose historical data but the system will work.

## 6. Restore vault-config.md

If `vault-config.md` was lost, regenerate from template:
```bash
sed -e "s|{{VAULT_PATH}}|$YOUR_VAULT_PATH|g" \
    -e "s|{{VAULT_NAME}}|$YOUR_VAULT_NAME|g" \
    vault-config.md.template > vault-config.md
```
Then customize it to match your vault structure.

## 7. Verify everything

```bash
# Check database
PYTHONPATH=./scripts ./scripts/.venv/bin/python ./scripts/query_db.py collector-status

# Check health receiver
curl -s http://localhost:9876/health

# Run a test backup
bash scripts/backup-db.sh

# Check timers
systemctl --user list-timers --all | grep jarvis

# Test a briefing
./scripts/run-jarvis.sh daily-briefing
```

## What lives where

| Component | Location | Backed up? |
|-----------|----------|-----------|
| Scripts & config | `~/Projects/llm-wiki/` | Git + GitHub |
| Systemd units | `~/.config/systemd/user/` (symlinks to repo) | Git + GitHub |
| Obsidian vault | (see jarvis.conf) | Manual / your backup system |
| SQLite database | vault `_llm/data/jarvis.db` | Daily backup (7-day rotation) |
| Credentials | `~/.config/jarvis/credentials.env` | Password manager |
| DB backups | vault `_llm/data/backups/` | Local only |
| Personal config | `jarvis.conf`, `vault-config.md` | Gitignored — regenerate via setup.sh |
