Run the DAILY BRIEFING operation. Generate today's Good Morning summary.

Read `vault-config.md` first to understand the vault location, structure, key files, and backlog rotation schedule.

## Data Source — SQLite Database

All personal data (health, music, podcasts, session memory, user notes) is in a SQLite database queried via `query_db.py`. Run the queries below using bash:

```bash
SCRIPT=./scripts/query_db.py
VENV=./scripts/.venv/bin/python
PYTHONPATH=./scripts
```

## Session Memory — Read First

0. Run `PYTHONPATH=$PYTHONPATH $VENV $SCRIPT memory` to get cross-session context. This contains context from your previous briefings — health trends you noticed, music phases, items you flagged for follow-up, and recent observations. Use this to provide continuity: reference yesterday's observations, follow up on flagged items, note when trends continue or break. If the output is empty `{}`, this is your first run — proceed normally.

1. Run `PYTHONPATH=$PYTHONPATH $VENV $SCRIPT user-notes --days 7` to get things the user explicitly asked Jarvis to remember. Weave any notes naturally into the relevant briefing sections (e.g., a food note in the listening section context, a tech note near project pulse). Don't create a separate "notes" section — integrate them where they belong.

## Collector Health — Check First

1a. Run `PYTHONPATH=$PYTHONPATH $VENV $SCRIPT collector-status` to check if data collectors are running. If any collector shows "stale" or "never_run", note it in the briefing so the user knows data may be incomplete (e.g., "Apple Music collector hasn't run in 3 days — no recent listening data").

## Gather Data

2. Get today's date and day of week
3. Read the current weekly note (most recent root-level YYYY-MM-DD.md in the vault — see vault-config.md for path)
4. Pull today's date-specific todos (look for [[today's date]] section headers)
5. List incomplete work and life items, flag anything carrying forward 2+ weeks
6. Check ~/Projects/ for recent file modifications (last 3 days) to determine project activity
7. Use the backlog rotation schedule from vault-config.md for today's day of week
8. Read exercise table from weekly note, note filled vs empty days
9. Run `PYTHONPATH=$PYTHONPATH $VENV $SCRIPT rotation` to get backlog rotation state. Surface an item from today's category using engagement-aware rotation:
   - If the category has an `items` map, prefer items with low `surfaced_count` or never surfaced
   - Deprioritize items surfaced 3+ times with `engaged: false` (the user keeps ignoring them)
   - Check if previously surfaced items appeared in the weekly note or user-notes since last surfacing — if so, mark `engaged: true`
   - After choosing an item, update the rotation state (see Session Memory — Write Last)
   - If no `items` map exists yet, fall back to sequential `index` rotation and start building the map

## Health Data

10. Run `PYTHONPATH=$PYTHONPATH $VENV $SCRIPT health-today` to get today's and yesterday's health summaries plus recent workouts.
    - Also run `PYTHONPATH=$PYTHONPATH $VENV $SCRIPT health-trends` for 7d/30d averages and trend directions.
    - Summarize: steps, active calories, sleep duration, resting heart rate
    - Highlight any workouts (type, duration, distance, heart rate zones)
    - Cross-reference with the exercise table in the weekly note (note discrepancies but do NOT edit the table)
    - Provide a brief training insight: recovery status, volume trends, suggestions for running/climbing/strength
    - Compare with session memory health_trends — note continuations ("running streak now at 4 days") or breaks
    - If data is empty, note "no recent health data" instead

## Music Data

11. Run `PYTHONPATH=$PYTHONPATH $VENV $SCRIPT music-recent` to get recent tracks and heavy rotation.
    - Highlight what was listened to yesterday, any new artists or albums discovered
    - Note listening patterns (heavy listening day? genre shift? new discovery?)
    - If an artist/album appears in Music/Albums/, cross-reference it
    - Brief commentary: taste observations, recommendations, "you've been on a X kick"
    - Compare with session memory music_phase — note shifts or deepening trends
    - If data is empty, note "no recent music data" instead

## Podcast Data

12. Run `PYTHONPATH=$PYTHONPATH $VENV $SCRIPT podcasts-recent` to get recent episodes.
    - List episodes listened to since last briefing
    - Brief synopsis of each episode's topic
    - Surface connections to vault content (e.g., podcast about distributed systems → link to Tech/ notes)
    - Suggest a discussion point or idea sparked by the podcast content
    - If data is empty, note "no recent podcast data" instead

## Calendar & Email

13. If Google Calendar MCP is available, fetch today's and tomorrow's events
14. If Gmail MCP is available, check unread/important emails

## Reflection

15. Add a 'Something to Think About' section — a connection between vault pages, a dormant idea, or a nudge from old notes

## Write Output

16. Write to the vault's `_llm/daily/YYYY-MM-DD.md` (use today's actual date)
17. Open in Obsidian (use the vault name from vault-config.md): `obsidian open vault="VAULT_NAME" path="_llm/daily/YYYY-MM-DD.md"`
18. Append to the vault's `_llm/log.md`

## Session Memory — Write Last

19. Update session memory in the SQLite database. Run a Python snippet to write the updated values:

```bash
PYTHONPATH=$PYTHONPATH $VENV -c "
import json
from db import get_db, init_db
conn = get_db()
init_db(conn)
now = __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()

updates = {
    'last_briefing': json.dumps('YYYY-MM-DD'),  # today's actual date
    'running_context': json.dumps({
        'health_trends': 'one-line summary of current health state',
        'music_phase': 'one-line summary of current listening',
        'active_focus': 'what the user is working on',
        'carrying_items_age': {},
        'recent_observations': [],  # append today's key observation, max 7
        'follow_ups': [],
    }),
}

for key, value in updates.items():
    conn.execute(
        'INSERT OR REPLACE INTO session_memory (key, value, updated_at) VALUES (?, ?, ?)',
        (key, value, now)
    )

# Update rotation state too
rotation_json = json.dumps({...})  # updated rotation state
conn.execute(
    'INSERT OR REPLACE INTO session_memory (key, value, updated_at) VALUES (?, ?, ?)',
    ('rotation', rotation_json, now)
)
conn.commit()
conn.close()
"
```

Replace the placeholder values above with the actual computed values from this briefing run.

Use a warm, concise tone — like a personal assistant briefing over coffee.
