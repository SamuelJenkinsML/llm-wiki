#!/usr/bin/env python3
"""One-time migration of existing JSON data files into Jarvis SQLite database.

Reads health, music, podcast, and state JSON files from _llm/data/ and
inserts them into jarvis.db. Uses INSERT OR IGNORE throughout, so this
script is idempotent and safe to rerun.

Usage:
    python migrate_json_to_sqlite.py [--data-dir PATH]
"""

import json
import sqlite3
from pathlib import Path

from db import get_db, init_db

DEFAULT_DATA_DIR = Path.home() / "Documents" / "Day to day" / "_llm" / "data"
DEFAULT_STATE_DIR = Path.home() / "Documents" / "Day to day" / "_llm" / "state"

# Cumulative metrics (use daily_total)
CUMULATIVE_METRICS = {
    "step_count", "active_energy", "active_energy_burned", "basal_energy_burned",
    "dietary_energy_consumed", "distance_walking_running", "walking_running_distance",
    "flights_climbed", "apple_exercise_time", "apple_stand_time",
}

# Averaging metrics (use average/min/max)
AVERAGING_METRICS = {
    "heart_rate", "resting_heart_rate", "heart_rate_variability",
}


def _load_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def migrate_health(conn: sqlite3.Connection, health_dir: Path) -> dict:
    """Migrate health daily JSON files into health_samples and health_daily."""
    files = sorted(health_dir.glob("20*.json"))
    total_samples = 0
    total_days = 0

    for path in files:
        data = _load_json(path)
        if not data:
            continue

        day = data.get("date", path.stem)
        metrics = data.get("metrics", {})
        total_days += 1

        for name, entry in metrics.items():
            units = entry.get("units", "")
            samples = entry.get("samples", [])

            # Insert raw samples
            for s in samples:
                conn.execute(
                    "INSERT OR IGNORE INTO health_samples (date, metric, timestamp, value, units) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (day, name, s.get("date", ""), s.get("value", 0), units),
                )
                total_samples += 1

            # Insert daily summary
            daily_total = entry.get("daily_total")
            average = entry.get("average")
            min_val = entry.get("min")
            max_val = entry.get("max")
            latest = entry.get("latest_value")
            sample_count = entry.get("sample_count", len(samples))

            conn.execute(
                "INSERT OR REPLACE INTO health_daily "
                "(date, metric, units, sample_count, daily_total, average, min_value, max_value, latest_value) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (day, name, units, sample_count, daily_total, average, min_val, max_val, latest),
            )

    conn.commit()
    return {"files": len(files), "days": total_days, "samples": total_samples}


def migrate_workouts(conn: sqlite3.Connection, workouts_dir: Path) -> dict:
    """Migrate standalone workout JSON files."""
    files = list(workouts_dir.glob("20*.json"))
    count = 0

    for path in files:
        data = _load_json(path)
        if not data:
            continue

        wtype = data.get("type", "unknown")
        start = data.get("start", "")
        day = start[:10] if len(start) >= 10 else path.stem[:10]

        conn.execute(
            "INSERT OR IGNORE INTO workouts "
            "(date, type, start_time, duration_minutes, distance_km, energy_kcal, avg_heart_rate, max_heart_rate) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                day, wtype, start,
                data.get("duration_minutes", 0),
                data.get("distance_km", 0),
                data.get("energy_kcal", 0),
                data.get("avg_heart_rate", 0),
                data.get("max_heart_rate", 0),
            ),
        )
        count += 1

    conn.commit()
    return {"files": len(files), "workouts": count}


def migrate_music(conn: sqlite3.Connection, music_dir: Path) -> dict:
    """Migrate music daily snapshots into music_tracks and music_rotation."""
    files = sorted(music_dir.glob("20*.json"))
    track_count = 0
    rotation_count = 0

    for path in files:
        data = _load_json(path)
        if not data:
            continue

        day = data.get("date", path.stem)

        # Tracks
        for t in data.get("recent_tracks", []):
            track_id = t.get("id", "")
            if not track_id:
                # Fallback dedup key
                track_id = f"{t.get('track', '')}|{t.get('artist', '')}|{t.get('album', '')}"

            conn.execute(
                "INSERT OR IGNORE INTO music_tracks "
                "(date, track_id, track, artist, album, genre, duration_ms, played_at, url) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    day, track_id,
                    t.get("track", ""), t.get("artist", ""), t.get("album", ""),
                    t.get("genre", ""), t.get("duration_ms", 0),
                    t.get("played_at", ""), t.get("url", ""),
                ),
            )
            track_count += 1

        # Heavy rotation
        for item in data.get("heavy_rotation", []):
            conn.execute(
                "INSERT INTO music_rotation "
                "(fetched_date, name, artist, type, url, apple_id) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    day,
                    item.get("name", ""), item.get("artist", ""),
                    item.get("type", ""), item.get("url", ""),
                    item.get("id", ""),
                ),
            )
            rotation_count += 1

    conn.commit()
    return {"files": len(files), "tracks": track_count, "rotation": rotation_count}


def migrate_podcasts(conn: sqlite3.Connection, podcast_dir: Path) -> dict:
    """Migrate podcast daily snapshots into podcast_episodes and podcast_subscriptions."""
    files = sorted(podcast_dir.glob("20*.json"))
    ep_count = 0
    sub_count = 0

    for path in files:
        data = _load_json(path)
        if not data:
            continue

        day = data.get("date", path.stem)

        for ep in data.get("recent_episodes", []):
            conn.execute(
                "INSERT OR IGNORE INTO podcast_episodes "
                "(date, uuid, podcast, title, url, duration_seconds, "
                "played_up_to_seconds, playing_status, published) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    day, ep.get("uuid", ""), ep.get("podcast", ""),
                    ep.get("title", ""), ep.get("url", ""),
                    ep.get("duration_seconds", 0), ep.get("played_up_to_seconds", 0),
                    ep.get("playing_status", 0), ep.get("published", ""),
                ),
            )
            ep_count += 1

        for sub in data.get("subscriptions", []):
            conn.execute(
                "INSERT OR REPLACE INTO podcast_subscriptions "
                "(uuid, title, author, url, last_seen) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    sub.get("uuid", ""), sub.get("title", ""),
                    sub.get("author", ""), sub.get("url", ""), day,
                ),
            )
            sub_count += 1

    conn.commit()
    return {"files": len(files), "episodes": ep_count, "subscriptions": sub_count}


def migrate_state(conn: sqlite3.Connection, state_dir: Path) -> dict:
    """Migrate memory.json, user-notes.json, and rotation.json."""
    result = {"memory_keys": 0, "user_notes": 0, "rotation": False}

    # memory.json → session_memory (one row per top-level key)
    memory = _load_json(state_dir / "memory.json")
    if memory:
        for key, value in memory.items():
            conn.execute(
                "INSERT OR REPLACE INTO session_memory (key, value, updated_at) "
                "VALUES (?, ?, datetime('now'))",
                (key, json.dumps(value)),
            )
            result["memory_keys"] += 1

    # rotation.json → session_memory under key='rotation'
    rotation = _load_json(state_dir / "rotation.json")
    if rotation:
        conn.execute(
            "INSERT OR REPLACE INTO session_memory (key, value, updated_at) "
            "VALUES ('rotation', ?, datetime('now'))",
            (json.dumps(rotation),),
        )
        result["rotation"] = True

    # user-notes.json → user_notes table
    notes_data = _load_json(state_dir / "user-notes.json")
    if notes_data:
        for note in notes_data.get("notes", []):
            conn.execute(
                "INSERT INTO user_notes (date, text, tags, source) "
                "VALUES (?, ?, ?, ?)",
                (
                    note.get("date", ""),
                    note.get("text", ""),
                    json.dumps(note.get("tags", [])),
                    note.get("source", "conversation"),
                ),
            )
            result["user_notes"] += 1

    conn.commit()
    return result


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Migrate Jarvis JSON data to SQLite")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--state-dir", type=Path, default=DEFAULT_STATE_DIR)
    args = parser.parse_args()

    conn = get_db()
    init_db(conn)

    print("Migrating health data...")
    health_result = migrate_health(conn, args.data_dir / "health")
    print(f"  {health_result['files']} files, {health_result['days']} days, {health_result['samples']} samples")

    workouts_dir = args.data_dir / "health" / "workouts"
    if workouts_dir.exists():
        print("Migrating workouts...")
        workout_result = migrate_workouts(conn, workouts_dir)
        print(f"  {workout_result['files']} files, {workout_result['workouts']} workouts")

    print("Migrating music data...")
    music_result = migrate_music(conn, args.data_dir / "music")
    print(f"  {music_result['files']} files, {music_result['tracks']} tracks, {music_result['rotation']} rotation items")

    print("Migrating podcast data...")
    podcast_result = migrate_podcasts(conn, args.data_dir / "podcasts")
    print(f"  {podcast_result['files']} files, {podcast_result['episodes']} episodes, {podcast_result['subscriptions']} subscriptions")

    print("Migrating state files...")
    state_result = migrate_state(conn, args.state_dir)
    print(f"  {state_result['memory_keys']} memory keys, {state_result['user_notes']} user notes, rotation={'yes' if state_result['rotation'] else 'no'}")

    # Print final row counts
    print("\nFinal row counts:")
    for table in ["health_samples", "health_daily", "workouts", "music_tracks",
                   "music_rotation", "podcast_episodes", "podcast_subscriptions",
                   "user_notes", "session_memory"]:
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table}: {count}")

    conn.close()
    print("\nMigration complete.")


if __name__ == "__main__":
    main()
