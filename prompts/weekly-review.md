Run the WEEKLY REVIEW operation. Read the most recent weekly note at root level of ~/Documents/Day to day/ (find the latest YYYY-MM-DD.md file). Also read the previous week's note. Then:

## Data Source — SQLite Database

All personal data is in a SQLite database queried via `query-db.py`:

```bash
SCRIPT=~/Projects/llm-wiki/scripts/query_db.py
VENV=~/Projects/llm-wiki/scripts/.venv/bin/python
PYTHONPATH=~/Projects/llm-wiki/scripts
```

## Session Memory — Read First

0. Run `PYTHONPATH=$PYTHONPATH $VENV $SCRIPT memory` to get cross-session context. Use the `recent_observations` to inform your review — these are things you noticed across the week's daily briefings. Reference them in your synthesis (e.g., "Early in the week I noted a running streak; it held through Thursday").

1. Run `PYTHONPATH=$PYTHONPATH $VENV $SCRIPT user-notes --days 7` to get things the user asked Jarvis to remember this week. Include a "Notes from the Week" section in the review summarizing them. Connect notes to relevant projects or themes.

## Review

2. Identify completed vs incomplete todos (Work + Life sections)
3. Summarize accomplishments for the week
4. Surface backlog items from To Read.md, Game backlog.md, Tech blog ideas.md — rotate what gets highlighted
5. Check project status across all domains — scan type: project files and ~/Projects/ for recent activity
6. Identify items carrying forward from previous week — flag anything carrying for 3+ weeks with a nudge
7. Run `PYTHONPATH=$PYTHONPATH $VENV $SCRIPT rotation` to get backlog rotation state and update it

## Write Output

8. Write review to ~/Documents/Day to day/_llm/reviews/YYYY-MM-DD.md (use current week's Monday date)
9. Append to ~/Documents/Day to day/_llm/log.md
10. Open the review in Obsidian: obsidian open vault="Day to day" path="_llm/reviews/YYYY-MM-DD.md"

## Session Memory — Write Last

11. Update session memory in the SQLite database:

```bash
PYTHONPATH=$PYTHONPATH $VENV -c "
import json
from db import get_db, init_db
conn = get_db()
init_db(conn)
now = __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()

updates = {
    'weekly_summary': json.dumps({
        'week_of': 'YYYY-MM-DD',  # this week's Monday date
        'themes': '1-2 sentence summary of the week',
    }),
    'running_context': json.dumps({
        'health_trends': 'updated if shifted this week',
        'music_phase': 'updated if shifted this week',
        'active_focus': 'updated from weekly note',
        'carrying_items_age': {},  # update ages, remove completed
        'recent_observations': [],  # reset to empty for new week
        'follow_ups': [],  # clear addressed items
    }),
}

for key, value in updates.items():
    conn.execute(
        'INSERT OR REPLACE INTO session_memory (key, value, updated_at) VALUES (?, ?, ?)',
        (key, value, now)
    )

# Update rotation state
rotation_json = json.dumps({...})  # updated rotation state
conn.execute(
    'INSERT OR REPLACE INTO session_memory (key, value, updated_at) VALUES (?, ?, ?)',
    ('rotation', rotation_json, now)
)
conn.commit()
conn.close()
"
```

Replace the placeholder values above with the actual computed values from this review.
