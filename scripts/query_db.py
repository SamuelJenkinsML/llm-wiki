#!/usr/bin/env python3
"""CLI query interface for Jarvis SQLite database.

Outputs JSON to stdout for consumption by Claude CLI during briefing generation.

Usage:
    python query_db.py health-today
    python query_db.py health-trends
    python query_db.py music-recent
    python query_db.py podcasts-recent
    python query_db.py memory
    python query_db.py user-notes [--days N]
    python query_db.py rotation
    python query_db.py collector-status
    python query_db.py maintenance
"""

import json
import sqlite3
import sys
from datetime import date, datetime, timedelta, timezone

from db import get_db, init_db

# Known collectors for status reporting
KNOWN_COLLECTORS = ["health-receiver", "apple-music", "pocketcasts"]


def _row_to_dict(row: sqlite3.Row) -> dict:
    return dict(row)


def _rows_to_list(rows: list[sqlite3.Row]) -> list[dict]:
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# health-today
# ---------------------------------------------------------------------------

def health_today(conn: sqlite3.Connection) -> dict:
    """Today + yesterday daily summaries and recent workouts."""
    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    daily = conn.execute(
        "SELECT date, metric, units, sample_count, daily_total, average, "
        "min_value, max_value, latest_value "
        "FROM health_daily WHERE date IN (?, ?) ORDER BY date DESC, metric",
        (today, yesterday),
    ).fetchall()

    # Workouts from last 3 days
    three_ago = (date.today() - timedelta(days=3)).isoformat()
    workouts = conn.execute(
        "SELECT date, type, start_time, duration_minutes, distance_km, "
        "energy_kcal, avg_heart_rate, max_heart_rate "
        "FROM workouts WHERE date >= ? ORDER BY date DESC, start_time DESC",
        (three_ago,),
    ).fetchall()

    return {
        "daily": _rows_to_list(daily),
        "workouts": _rows_to_list(workouts),
    }


# ---------------------------------------------------------------------------
# health-trends
# ---------------------------------------------------------------------------

def health_trends(conn: sqlite3.Connection) -> dict:
    """7d/30d averages and trend directions for all health metrics."""
    today = date.today()
    d7 = (today - timedelta(days=7)).isoformat()
    d30 = (today - timedelta(days=30)).isoformat()
    today_str = today.isoformat()

    # Get all metrics that have data in the last 30 days
    metrics = conn.execute(
        "SELECT DISTINCT metric FROM health_daily WHERE date > ? AND date < ?",
        (d30, today_str),
    ).fetchall()

    result = {}
    for row in metrics:
        metric = row["metric"]

        # 7-day average
        r7 = conn.execute(
            "SELECT AVG(COALESCE(daily_total, average)) as avg_val, COUNT(*) as cnt "
            "FROM health_daily WHERE metric = ? AND date > ? AND date < ?",
            (metric, d7, today_str),
        ).fetchone()

        # 30-day average
        r30 = conn.execute(
            "SELECT AVG(COALESCE(daily_total, average)) as avg_val, COUNT(*) as cnt "
            "FROM health_daily WHERE metric = ? AND date > ? AND date < ?",
            (metric, d30, today_str),
        ).fetchone()

        # Older window (days 8-30) for trend comparison
        older = conn.execute(
            "SELECT AVG(COALESCE(daily_total, average)) as avg_val, COUNT(*) as cnt "
            "FROM health_daily WHERE metric = ? AND date > ? AND date <= ?",
            (metric, d30, d7),
        ).fetchone()

        avg_7d = round(r7["avg_val"], 1) if r7["avg_val"] is not None else None
        avg_30d = round(r30["avg_val"], 1) if r30["avg_val"] is not None else None

        # Compute trend direction
        trend = None
        if (
            r7["avg_val"] is not None
            and older["avg_val"] is not None
            and older["cnt"] >= 3
            and r7["cnt"] >= 3
        ):
            pct = (r7["avg_val"] - older["avg_val"]) / older["avg_val"] * 100 if older["avg_val"] else 0
            if pct > 5:
                trend = "increasing"
            elif pct < -5:
                trend = "declining"
            else:
                trend = "stable"

        result[metric] = {
            "avg_7d": avg_7d,
            "avg_30d": avg_30d,
            "trend": trend,
        }

    # Workout counts
    wk7 = conn.execute(
        "SELECT COUNT(*) as cnt FROM workouts WHERE date > ? AND date < ?",
        (d7, today_str),
    ).fetchone()
    wk30 = conn.execute(
        "SELECT COUNT(*) as cnt FROM workouts WHERE date > ? AND date < ?",
        (d30, today_str),
    ).fetchone()

    # Workout types in 30d
    workout_types_rows = conn.execute(
        "SELECT type, COUNT(*) as cnt FROM workouts WHERE date > ? AND date < ? GROUP BY type ORDER BY cnt DESC",
        (d30, today_str),
    ).fetchall()

    result["workout_count_7d"] = wk7["cnt"]
    result["workout_count_30d"] = wk30["cnt"]
    result["workout_types_30d"] = {r["type"]: r["cnt"] for r in workout_types_rows}

    return result


# ---------------------------------------------------------------------------
# music-recent
# ---------------------------------------------------------------------------

def music_recent(conn: sqlite3.Connection) -> dict:
    """Last 50 tracks and current heavy rotation."""
    tracks = conn.execute(
        "SELECT date, track_id, track, artist, album, genre, duration_ms, played_at, url "
        "FROM music_tracks ORDER BY date DESC, id DESC LIMIT 50"
    ).fetchall()

    # Most recent heavy rotation snapshot
    latest_date = conn.execute(
        "SELECT MAX(fetched_date) as d FROM music_rotation"
    ).fetchone()
    rotation = []
    if latest_date and latest_date["d"]:
        rotation = conn.execute(
            "SELECT name, artist, type, url, apple_id "
            "FROM music_rotation WHERE fetched_date = ?",
            (latest_date["d"],),
        ).fetchall()

    return {
        "tracks": _rows_to_list(tracks),
        "heavy_rotation": _rows_to_list(rotation),
    }


# ---------------------------------------------------------------------------
# podcasts-recent
# ---------------------------------------------------------------------------

def podcasts_recent(conn: sqlite3.Connection) -> dict:
    """Recent episodes and subscription count."""
    episodes = conn.execute(
        "SELECT date, uuid, podcast, title, url, duration_seconds, "
        "played_up_to_seconds, playing_status, published "
        "FROM podcast_episodes ORDER BY date DESC, id DESC LIMIT 30"
    ).fetchall()

    sub_count = conn.execute(
        "SELECT COUNT(*) as cnt FROM podcast_subscriptions"
    ).fetchone()

    return {
        "episodes": _rows_to_list(episodes),
        "subscription_count": sub_count["cnt"],
    }


# ---------------------------------------------------------------------------
# memory
# ---------------------------------------------------------------------------

def memory(conn: sqlite3.Connection) -> dict:
    """All session memory key-value pairs, with JSON values parsed."""
    rows = conn.execute("SELECT key, value FROM session_memory").fetchall()
    result = {}
    for row in rows:
        try:
            result[row["key"]] = json.loads(row["value"])
        except (json.JSONDecodeError, TypeError):
            result[row["key"]] = row["value"]
    return result


# ---------------------------------------------------------------------------
# user-notes
# ---------------------------------------------------------------------------

def user_notes(conn: sqlite3.Connection, days: int = 7) -> list[dict]:
    """Recent non-archived user notes."""
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    rows = conn.execute(
        "SELECT id, date, text, tags, source FROM user_notes "
        "WHERE archived = 0 AND date >= ? ORDER BY date DESC",
        (cutoff,),
    ).fetchall()

    result = []
    for row in rows:
        d = dict(row)
        try:
            d["tags"] = json.loads(d["tags"]) if d["tags"] else []
        except json.JSONDecodeError:
            d["tags"] = []
        result.append(d)
    return result


# ---------------------------------------------------------------------------
# rotation
# ---------------------------------------------------------------------------

def rotation(conn: sqlite3.Connection) -> dict:
    """Current backlog rotation state from session_memory."""
    row = conn.execute(
        "SELECT value FROM session_memory WHERE key = 'rotation'"
    ).fetchone()
    if not row or not row["value"]:
        return {}
    try:
        return json.loads(row["value"])
    except (json.JSONDecodeError, TypeError):
        return {}


# ---------------------------------------------------------------------------
# collector-status
# ---------------------------------------------------------------------------

def collector_status(conn: sqlite3.Connection) -> dict:
    """Status of each known collector: ok, stale, error, never_run."""
    now = datetime.now(timezone.utc)
    stale_threshold = (now - timedelta(hours=24)).isoformat()

    result = {}
    for collector in KNOWN_COLLECTORS:
        # Last successful run
        last_success = conn.execute(
            "SELECT started_at, completed_at FROM collector_runs "
            "WHERE collector = ? AND status = 'success' "
            "ORDER BY started_at DESC LIMIT 1",
            (collector,),
        ).fetchone()

        # Last error
        last_error = conn.execute(
            "SELECT error_message, started_at FROM collector_runs "
            "WHERE collector = ? AND status = 'error' "
            "ORDER BY started_at DESC LIMIT 1",
            (collector,),
        ).fetchone()

        if not last_success:
            status = "never_run"
            result[collector] = {
                "status": status,
                "last_success": None,
                "last_error": last_error["error_message"] if last_error else None,
            }
        else:
            is_stale = last_success["started_at"] < stale_threshold
            result[collector] = {
                "status": "stale" if is_stale else "ok",
                "last_success": last_success["started_at"],
                "last_error": last_error["error_message"] if last_error else None,
            }

    return result


# ---------------------------------------------------------------------------
# maintenance
# ---------------------------------------------------------------------------

def maintenance(conn: sqlite3.Connection) -> dict:
    """Run retention policy. Returns summary of deletions."""
    today = date.today()
    deleted = {}

    # health_samples: 90 days
    cutoff_90 = (today - timedelta(days=90)).isoformat()
    cursor = conn.execute(
        "DELETE FROM health_samples WHERE date < ?", (cutoff_90,)
    )
    deleted["health_samples"] = cursor.rowcount

    # music_tracks: 90 days
    cursor = conn.execute(
        "DELETE FROM music_tracks WHERE date < ?", (cutoff_90,)
    )
    deleted["music_tracks"] = cursor.rowcount

    # music_rotation: 30 days
    cutoff_30 = (today - timedelta(days=30)).isoformat()
    cursor = conn.execute(
        "DELETE FROM music_rotation WHERE fetched_date < ?", (cutoff_30,)
    )
    deleted["music_rotation"] = cursor.rowcount

    # collector_runs: 30 days
    cursor = conn.execute(
        "DELETE FROM collector_runs WHERE started_at < ?", (cutoff_30,)
    )
    deleted["collector_runs"] = cursor.rowcount

    conn.commit()
    return {"deleted": deleted}


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Query Jarvis database")
    parser.add_argument("command", choices=[
        "health-today", "health-trends", "music-recent", "podcasts-recent",
        "memory", "user-notes", "rotation", "collector-status", "maintenance",
    ])
    parser.add_argument("--days", type=int, default=7, help="Days window for user-notes")
    args = parser.parse_args()

    conn = get_db()
    init_db(conn)

    commands = {
        "health-today": lambda: health_today(conn),
        "health-trends": lambda: health_trends(conn),
        "music-recent": lambda: music_recent(conn),
        "podcasts-recent": lambda: podcasts_recent(conn),
        "memory": lambda: memory(conn),
        "user-notes": lambda: user_notes(conn, days=args.days),
        "rotation": lambda: rotation(conn),
        "collector-status": lambda: collector_status(conn),
        "maintenance": lambda: maintenance(conn),
    }

    result = commands[args.command]()
    print(json.dumps(result, indent=2))
    conn.close()


if __name__ == "__main__":
    main()
