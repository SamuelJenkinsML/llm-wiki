"""Shared SQLite database module for Jarvis data layer.

Provides database connection, schema initialization, and helper functions
used by all collectors and the query CLI.

Database location: $JARVIS_VAULT_PATH/_llm/data/jarvis.db
(defaults to ~/Documents/Day to day/_llm/data/jarvis.db)
"""

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

_vault = os.environ.get(
    "JARVIS_VAULT_PATH", str(Path.home() / "Documents" / "Day to day")
)
DEFAULT_DB_PATH = Path(_vault) / "_llm" / "data" / "jarvis.db"

SCHEMA_VERSION = 1

SCHEMA_SQL = """
-- Raw health metric readings (~2000-4000 rows/day)
CREATE TABLE IF NOT EXISTS health_samples (
    id INTEGER PRIMARY KEY,
    date TEXT NOT NULL,
    metric TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    value REAL NOT NULL,
    units TEXT,
    UNIQUE(metric, timestamp)
);
CREATE INDEX IF NOT EXISTS idx_health_samples_date ON health_samples(date);
CREATE INDEX IF NOT EXISTS idx_health_samples_metric_date ON health_samples(metric, date);

-- Daily summaries, one row per metric per day
CREATE TABLE IF NOT EXISTS health_daily (
    date TEXT NOT NULL,
    metric TEXT NOT NULL,
    units TEXT,
    sample_count INTEGER,
    daily_total REAL,
    average REAL,
    min_value REAL,
    max_value REAL,
    latest_value REAL,
    PRIMARY KEY (date, metric)
);

-- Individual workout sessions
CREATE TABLE IF NOT EXISTS workouts (
    id INTEGER PRIMARY KEY,
    date TEXT NOT NULL,
    type TEXT NOT NULL,
    start_time TEXT,
    duration_minutes REAL,
    distance_km REAL,
    energy_kcal REAL,
    avg_heart_rate REAL,
    max_heart_rate REAL,
    UNIQUE(type, start_time)
);
CREATE INDEX IF NOT EXISTS idx_workouts_date ON workouts(date);

-- Music play records
CREATE TABLE IF NOT EXISTS music_tracks (
    id INTEGER PRIMARY KEY,
    date TEXT NOT NULL,
    track_id TEXT,
    track TEXT,
    artist TEXT,
    album TEXT,
    genre TEXT,
    duration_ms INTEGER,
    played_at TEXT,
    url TEXT,
    UNIQUE(track_id, date)
);
CREATE INDEX IF NOT EXISTS idx_music_tracks_date ON music_tracks(date);

-- Heavy rotation snapshots
CREATE TABLE IF NOT EXISTS music_rotation (
    id INTEGER PRIMARY KEY,
    fetched_date TEXT NOT NULL,
    name TEXT,
    artist TEXT,
    type TEXT,
    url TEXT,
    apple_id TEXT
);

-- Podcast listen history
CREATE TABLE IF NOT EXISTS podcast_episodes (
    id INTEGER PRIMARY KEY,
    date TEXT NOT NULL,
    uuid TEXT,
    podcast TEXT,
    title TEXT,
    url TEXT,
    duration_seconds INTEGER,
    played_up_to_seconds INTEGER,
    playing_status INTEGER,
    published TEXT,
    UNIQUE(uuid)
);
CREATE INDEX IF NOT EXISTS idx_podcast_episodes_date ON podcast_episodes(date);

-- Podcast subscriptions (overwritten each run)
CREATE TABLE IF NOT EXISTS podcast_subscriptions (
    uuid TEXT PRIMARY KEY,
    title TEXT,
    author TEXT,
    url TEXT,
    last_seen TEXT
);

-- User notes (replaces user-notes.json)
CREATE TABLE IF NOT EXISTS user_notes (
    id INTEGER PRIMARY KEY,
    date TEXT NOT NULL,
    text TEXT NOT NULL,
    tags TEXT,
    source TEXT DEFAULT 'conversation',
    archived INTEGER DEFAULT 0
);

-- Session memory (replaces memory.json)
CREATE TABLE IF NOT EXISTS session_memory (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TEXT
);

-- Collector health tracking
CREATE TABLE IF NOT EXISTS collector_runs (
    id INTEGER PRIMARY KEY,
    collector TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL,
    rows_affected INTEGER,
    error_message TEXT,
    duration_seconds REAL
);
CREATE INDEX IF NOT EXISTS idx_collector_runs_collector ON collector_runs(collector, started_at);

-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);
"""


def get_db(path: str | Path | None = None) -> sqlite3.Connection:
    """Open a connection to the Jarvis database.

    Args:
        path: Database path. Use ":memory:" for tests. Defaults to the vault location.
    """
    if path is None:
        path = DEFAULT_DB_PATH
    db_path = str(path)

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Create all tables if they don't exist. Idempotent."""
    conn.executescript(SCHEMA_SQL)

    # Record schema version if not already present
    existing = conn.execute(
        "SELECT version FROM schema_version WHERE version = ?", (SCHEMA_VERSION,)
    ).fetchone()
    if not existing:
        conn.execute(
            "INSERT OR IGNORE INTO schema_version (version, applied_at) VALUES (?, ?)",
            (SCHEMA_VERSION, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()


def log_run(
    conn: sqlite3.Connection,
    collector: str,
    status: str,
    rows_affected: int | None = None,
    error_message: str | None = None,
    duration_seconds: float | None = None,
) -> None:
    """Log a collector run to the collector_runs table."""
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO collector_runs "
        "(collector, started_at, completed_at, status, rows_affected, error_message, duration_seconds) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (collector, now, now if status != "timeout" else None, status, rows_affected, error_message, duration_seconds),
    )
    conn.commit()
