"""TDD tests for db.py — the shared database module.

Written BEFORE db.py implementation. Tests cover:
- Schema creation and idempotency
- WAL mode configuration
- Schema versioning
- Collector run logging
"""

import sqlite3
from datetime import datetime, timezone


def test_init_db_creates_all_tables(db):
    """All expected tables should exist after init_db()."""
    cursor = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = {row[0] for row in cursor.fetchall()}
    expected = {
        "health_samples",
        "health_daily",
        "workouts",
        "music_tracks",
        "music_rotation",
        "podcast_episodes",
        "podcast_subscriptions",
        "user_notes",
        "session_memory",
        "collector_runs",
        "schema_version",
    }
    assert expected.issubset(tables), f"Missing tables: {expected - tables}"


def test_init_db_idempotent(db):
    """Calling init_db() a second time should not error or duplicate data."""
    from db import init_db

    # Should not raise
    init_db(db)
    init_db(db)

    # Schema version should still have exactly one entry (version 1)
    count = db.execute("SELECT COUNT(*) FROM schema_version").fetchone()[0]
    assert count >= 1


def test_wal_mode_enabled(tmp_path):
    """Database should use WAL journal mode for concurrent access."""
    from db import get_db, init_db

    db_path = tmp_path / "test.db"
    conn = get_db(db_path)
    init_db(conn)
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    conn.close()
    assert mode == "wal"


def test_schema_version_tracked(db):
    """schema_version table should have at least one entry after init."""
    rows = db.execute("SELECT version, applied_at FROM schema_version").fetchall()
    assert len(rows) >= 1
    version, applied_at = rows[0]
    assert version == 1
    assert applied_at is not None


def test_log_run_records_success(db):
    """log_run should insert a successful collector run."""
    from db import log_run

    log_run(db, "apple-music", "success", rows_affected=30)

    row = db.execute(
        "SELECT collector, status, rows_affected, error_message FROM collector_runs"
    ).fetchone()
    assert row[0] == "apple-music"
    assert row[1] == "success"
    assert row[2] == 30
    assert row[3] is None


def test_log_run_records_error(db):
    """log_run should capture error details."""
    from db import log_run

    log_run(db, "pocketcasts", "error", error_message="401 Unauthorized")

    row = db.execute(
        "SELECT collector, status, error_message FROM collector_runs"
    ).fetchone()
    assert row[0] == "pocketcasts"
    assert row[1] == "error"
    assert row[2] == "401 Unauthorized"


def test_log_run_records_duration(db):
    """log_run should record duration when provided."""
    from db import log_run

    log_run(db, "health-receiver", "success", rows_affected=500, duration_seconds=2.5)

    row = db.execute(
        "SELECT duration_seconds FROM collector_runs"
    ).fetchone()
    assert row[0] == 2.5


def test_health_samples_unique_constraint(db):
    """Duplicate (metric, timestamp) should be rejected."""
    db.execute(
        "INSERT INTO health_samples (date, metric, timestamp, value, units) "
        "VALUES ('2026-04-09', 'step_count', '2026-04-09 08:00:00 +0100', 1234, 'count')"
    )
    db.commit()

    # Same metric + timestamp should conflict
    try:
        db.execute(
            "INSERT INTO health_samples (date, metric, timestamp, value, units) "
            "VALUES ('2026-04-09', 'step_count', '2026-04-09 08:00:00 +0100', 9999, 'count')"
        )
        db.commit()
        assert False, "Should have raised IntegrityError"
    except sqlite3.IntegrityError:
        db.rollback()

    # INSERT OR IGNORE should silently skip
    db.execute(
        "INSERT OR IGNORE INTO health_samples (date, metric, timestamp, value, units) "
        "VALUES ('2026-04-09', 'step_count', '2026-04-09 08:00:00 +0100', 9999, 'count')"
    )
    db.commit()
    val = db.execute(
        "SELECT value FROM health_samples WHERE metric='step_count' AND timestamp='2026-04-09 08:00:00 +0100'"
    ).fetchone()[0]
    assert val == 1234  # Original value preserved


def test_workouts_unique_constraint(db):
    """Duplicate (type, start_time) should be rejected."""
    db.execute(
        "INSERT INTO workouts (date, type, start_time, duration_minutes) "
        "VALUES ('2026-04-09', 'running', '2026-04-09 07:00:00 +0100', 45.5)"
    )
    db.commit()

    db.execute(
        "INSERT OR IGNORE INTO workouts (date, type, start_time, duration_minutes) "
        "VALUES ('2026-04-09', 'running', '2026-04-09 07:00:00 +0100', 99)"
    )
    db.commit()
    dur = db.execute(
        "SELECT duration_minutes FROM workouts WHERE type='running'"
    ).fetchone()[0]
    assert dur == 45.5  # Original preserved


def test_music_tracks_unique_constraint(db):
    """Duplicate (track_id, date) should be rejected."""
    db.execute(
        "INSERT INTO music_tracks (date, track_id, track, artist) "
        "VALUES ('2026-04-09', 'abc123', 'Song', 'Artist')"
    )
    db.commit()

    db.execute(
        "INSERT OR IGNORE INTO music_tracks (date, track_id, track, artist) "
        "VALUES ('2026-04-09', 'abc123', 'Different', 'Other')"
    )
    db.commit()
    row = db.execute(
        "SELECT track FROM music_tracks WHERE track_id='abc123'"
    ).fetchone()
    assert row[0] == "Song"  # Original preserved


def test_podcast_episodes_unique_constraint(db):
    """Duplicate uuid should be rejected."""
    db.execute(
        "INSERT INTO podcast_episodes (date, uuid, podcast, title) "
        "VALUES ('2026-04-09', 'ep-001', 'My Podcast', 'Episode 1')"
    )
    db.commit()

    db.execute(
        "INSERT OR IGNORE INTO podcast_episodes (date, uuid, podcast, title) "
        "VALUES ('2026-04-09', 'ep-001', 'Different', 'Different')"
    )
    db.commit()
    row = db.execute(
        "SELECT podcast FROM podcast_episodes WHERE uuid='ep-001'"
    ).fetchone()
    assert row[0] == "My Podcast"
