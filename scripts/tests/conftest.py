"""Shared fixtures for Jarvis SQLite tests.

Uses in-memory SQLite for speed and isolation. Loads real JSON files
from the vault as test fixtures for realistic data processing tests.
"""

import json
import sqlite3
from pathlib import Path

import pytest

VAULT_DATA = Path.home() / "Documents" / "Day to day" / "_llm" / "data"


@pytest.fixture
def db():
    """Fresh in-memory SQLite database with schema applied."""
    # Import is deferred so tests can be written before db.py exists
    from db import get_db, init_db

    conn = get_db(":memory:")
    init_db(conn)
    yield conn
    conn.close()


@pytest.fixture
def sample_health_json():
    """Load a real health daily JSON file for test data."""
    health_dir = VAULT_DATA / "health"
    # Find a file with decent data (not today's partial)
    candidates = sorted(health_dir.glob("20*.json"), reverse=True)
    for path in candidates[1:]:  # Skip today, use yesterday or earlier
        data = json.loads(path.read_text())
        if data.get("metrics") and len(data["metrics"]) > 3:
            return data
    # Fallback: use whatever exists
    if candidates:
        return json.loads(candidates[0].read_text())
    pytest.skip("No health JSON files available for testing")


@pytest.fixture
def sample_music_json():
    """Load a real music daily JSON file."""
    path = VAULT_DATA / "music" / "2026-04-09.json"
    if not path.exists():
        # Try any daily snapshot
        candidates = list((VAULT_DATA / "music").glob("20*.json"))
        if candidates:
            path = candidates[0]
        else:
            pytest.skip("No music JSON files available for testing")
    return json.loads(path.read_text())


@pytest.fixture
def sample_podcast_json():
    """Load a real podcast daily JSON file."""
    path = VAULT_DATA / "podcasts" / "2026-04-09.json"
    if not path.exists():
        candidates = list((VAULT_DATA / "podcasts").glob("20*.json"))
        if candidates:
            path = candidates[0]
        else:
            pytest.skip("No podcast JSON files available for testing")
    return json.loads(path.read_text())


@pytest.fixture
def sample_health_webhook_payload():
    """A realistic Health Auto Export webhook payload for testing the receiver."""
    return {
        "data": {
            "metrics": [
                {
                    "name": "step_count",
                    "units": "count",
                    "data": [
                        {"date": "2026-04-09 08:00:00 +0100", "qty": 1234},
                        {"date": "2026-04-09 09:00:00 +0100", "qty": 567},
                        {"date": "2026-04-09 10:00:00 +0100", "qty": 890},
                    ],
                },
                {
                    "name": "heart_rate",
                    "units": "bpm",
                    "data": [
                        {"date": "2026-04-09 08:05:00 +0100", "qty": 72},
                        {"date": "2026-04-09 09:15:00 +0100", "qty": 68},
                        {"date": "2026-04-09 10:30:00 +0100", "qty": 75},
                    ],
                },
                {
                    "name": "resting_heart_rate",
                    "units": "bpm",
                    "data": [
                        {"date": "2026-04-09 06:00:00 +0100", "qty": 48},
                    ],
                },
            ],
            "workouts": [
                {
                    "name": "running",
                    "start": "2026-04-09 07:00:00 +0100",
                    "duration": 45.5,
                    "totalDistance": 8.2,
                    "totalEnergyBurned": 650,
                    "avgHeartRate": 168,
                    "maxHeartRate": 185,
                },
            ],
        }
    }
