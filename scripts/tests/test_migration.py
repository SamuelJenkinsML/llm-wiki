"""TDD tests for migrate-json-to-sqlite.py — one-time migration script.

Written BEFORE the migration implementation. Tests verify that JSON data
is correctly migrated into SQLite tables with proper dedup and accuracy.
"""

import json
import sqlite3
from pathlib import Path

import pytest


@pytest.fixture
def migration_db(db):
    """DB fixture with the migrate module imported."""
    return db


# ---------------------------------------------------------------------------
# Health migration
# ---------------------------------------------------------------------------

class TestMigrateHealth:
    def _make_health_json(self, tmp_path, day="2026-04-08"):
        """Create a minimal but realistic health JSON file."""
        data = {
            "date": day,
            "metrics": {
                "step_count": {
                    "units": "count",
                    "samples": [
                        {"date": f"{day} 08:00:00 +0100", "value": 1000},
                        {"date": f"{day} 09:00:00 +0100", "value": 2000},
                        {"date": f"{day} 10:00:00 +0100", "value": 1500},
                    ],
                    "sample_count": 3,
                    "daily_total": 4500,
                    "latest_value": 1500,
                    "latest_date": f"{day} 10:00:00 +0100",
                },
                "heart_rate": {
                    "units": "bpm",
                    "samples": [
                        {"date": f"{day} 08:05:00 +0100", "value": 72},
                        {"date": f"{day} 09:15:00 +0100", "value": 68},
                        {"date": f"{day} 10:30:00 +0100", "value": 75},
                    ],
                    "sample_count": 3,
                    "average": 71.7,
                    "min": 68.0,
                    "max": 75.0,
                    "latest_value": 75,
                    "latest_date": f"{day} 10:30:00 +0100",
                },
                "resting_heart_rate": {
                    "units": "bpm",
                    "samples": [
                        {"date": f"{day} 06:00:00 +0100", "value": 48},
                    ],
                    "sample_count": 1,
                    "average": 48.0,
                    "min": 48.0,
                    "max": 48.0,
                    "latest_value": 48,
                    "latest_date": f"{day} 06:00:00 +0100",
                },
            },
            "workouts": [],
            "last_updated": "2026-04-08T20:00:00+00:00",
            "export_count": 5,
        }
        health_dir = tmp_path / "health"
        health_dir.mkdir(parents=True)
        path = health_dir / f"{day}.json"
        path.write_text(json.dumps(data, indent=2))
        return health_dir

    def test_sample_count(self, db, tmp_path):
        """Migrated sample count should match the JSON file."""
        from migrate_json_to_sqlite import migrate_health

        health_dir = self._make_health_json(tmp_path)
        migrate_health(db, health_dir)

        count = db.execute("SELECT COUNT(*) FROM health_samples").fetchone()[0]
        # 3 step_count + 3 heart_rate + 1 resting_heart_rate = 7
        assert count == 7

    def test_daily_totals(self, db, tmp_path):
        """daily_total for cumulative metrics should match JSON."""
        from migrate_json_to_sqlite import migrate_health

        health_dir = self._make_health_json(tmp_path)
        migrate_health(db, health_dir)

        row = db.execute(
            "SELECT daily_total FROM health_daily WHERE date='2026-04-08' AND metric='step_count'"
        ).fetchone()
        assert row is not None
        assert row[0] == 4500.0

    def test_averages(self, db, tmp_path):
        """average for averaging metrics should match JSON."""
        from migrate_json_to_sqlite import migrate_health

        health_dir = self._make_health_json(tmp_path)
        migrate_health(db, health_dir)

        row = db.execute(
            "SELECT average, min_value, max_value FROM health_daily "
            "WHERE date='2026-04-08' AND metric='heart_rate'"
        ).fetchone()
        assert row is not None
        assert row[0] == 71.7
        assert row[1] == 68.0
        assert row[2] == 75.0

    def test_dedup_on_rerun(self, db, tmp_path):
        """Running migration twice should not duplicate rows."""
        from migrate_json_to_sqlite import migrate_health

        health_dir = self._make_health_json(tmp_path)
        migrate_health(db, health_dir)
        count1 = db.execute("SELECT COUNT(*) FROM health_samples").fetchone()[0]

        migrate_health(db, health_dir)
        count2 = db.execute("SELECT COUNT(*) FROM health_samples").fetchone()[0]

        assert count1 == count2

    def test_multiple_days(self, db, tmp_path):
        """Should migrate data from multiple day files."""
        from migrate_json_to_sqlite import migrate_health

        health_dir = self._make_health_json(tmp_path, "2026-04-07")
        # Add another day
        data2 = {
            "date": "2026-04-08",
            "metrics": {
                "step_count": {
                    "units": "count",
                    "samples": [
                        {"date": "2026-04-08 08:00:00 +0100", "value": 3000},
                    ],
                    "sample_count": 1,
                    "daily_total": 3000,
                },
            },
            "workouts": [],
        }
        (health_dir / "2026-04-08.json").write_text(json.dumps(data2))

        migrate_health(db, health_dir)

        days = db.execute(
            "SELECT DISTINCT date FROM health_daily ORDER BY date"
        ).fetchall()
        assert len(days) == 2


# ---------------------------------------------------------------------------
# Workout migration
# ---------------------------------------------------------------------------

class TestMigrateWorkouts:
    def _make_workout_files(self, tmp_path):
        workouts_dir = tmp_path / "health" / "workouts"
        workouts_dir.mkdir(parents=True)

        w1 = {
            "type": "running",
            "start": "2026-04-08 07:00:00 +0100",
            "duration_minutes": 45.5,
            "distance_km": 8.2,
            "energy_kcal": 650,
            "avg_heart_rate": 168,
            "max_heart_rate": 185,
        }
        (workouts_dir / "2026-04-08-running.json").write_text(json.dumps(w1))

        w2 = {
            "type": "strength",
            "start": "2026-04-07 18:00:00 +0100",
            "duration_minutes": 60,
            "distance_km": 0,
            "energy_kcal": 400,
            "avg_heart_rate": 130,
            "max_heart_rate": 155,
        }
        (workouts_dir / "2026-04-07-strength.json").write_text(json.dumps(w2))
        return workouts_dir

    def test_workout_fields(self, db, tmp_path):
        """All workout fields should be extracted correctly."""
        from migrate_json_to_sqlite import migrate_workouts

        workouts_dir = self._make_workout_files(tmp_path)
        migrate_workouts(db, workouts_dir)

        row = db.execute(
            "SELECT type, duration_minutes, distance_km, avg_heart_rate, max_heart_rate "
            "FROM workouts WHERE type='running'"
        ).fetchone()
        assert row is not None
        assert row[0] == "running"
        assert row[1] == 45.5
        assert row[2] == 8.2
        assert row[3] == 168
        assert row[4] == 185

    def test_workout_count(self, db, tmp_path):
        """Should import all workout files."""
        from migrate_json_to_sqlite import migrate_workouts

        workouts_dir = self._make_workout_files(tmp_path)
        migrate_workouts(db, workouts_dir)

        count = db.execute("SELECT COUNT(*) FROM workouts").fetchone()[0]
        assert count == 2

    def test_workout_dedup(self, db, tmp_path):
        """Running twice should not duplicate workouts."""
        from migrate_json_to_sqlite import migrate_workouts

        workouts_dir = self._make_workout_files(tmp_path)
        migrate_workouts(db, workouts_dir)
        migrate_workouts(db, workouts_dir)

        count = db.execute("SELECT COUNT(*) FROM workouts").fetchone()[0]
        assert count == 2


# ---------------------------------------------------------------------------
# Music migration
# ---------------------------------------------------------------------------

class TestMigrateMusic:
    def _make_music_files(self, tmp_path):
        music_dir = tmp_path / "music"
        music_dir.mkdir(parents=True)

        daily = {
            "date": "2026-04-09",
            "source": "apple-music",
            "recent_tracks": [
                {"id": "t1", "track": "Song A", "artist": "Artist A", "album": "Album A",
                 "genre": "Rock", "duration_ms": 240000, "played_at": "", "url": ""},
                {"id": "t2", "track": "Song B", "artist": "Artist B", "album": "Album B",
                 "genre": "Electronic", "duration_ms": 300000, "played_at": "", "url": ""},
                {"id": "t1", "track": "Song A", "artist": "Artist A", "album": "Album A",
                 "genre": "Rock", "duration_ms": 240000, "played_at": "", "url": ""},
            ],
            "heavy_rotation": [
                {"id": "hr1", "name": "White Pony", "artist": "Deftones", "type": "albums", "url": ""},
            ],
            "runs": 2,
        }
        (music_dir / "2026-04-09.json").write_text(json.dumps(daily))
        return music_dir

    def test_track_count(self, db, tmp_path):
        """Track count should match unique tracks in JSON."""
        from migrate_json_to_sqlite import migrate_music

        music_dir = self._make_music_files(tmp_path)
        migrate_music(db, music_dir)

        count = db.execute("SELECT COUNT(*) FROM music_tracks").fetchone()[0]
        # 3 tracks in JSON but t1 is duplicated, so 2 unique
        assert count == 2

    def test_dedup_by_track_id(self, db, tmp_path):
        """Duplicate track IDs should produce only 1 row."""
        from migrate_json_to_sqlite import migrate_music

        music_dir = self._make_music_files(tmp_path)
        migrate_music(db, music_dir)

        rows = db.execute(
            "SELECT track FROM music_tracks WHERE track_id='t1'"
        ).fetchall()
        assert len(rows) == 1

    def test_heavy_rotation(self, db, tmp_path):
        """Heavy rotation items should be migrated."""
        from migrate_json_to_sqlite import migrate_music

        music_dir = self._make_music_files(tmp_path)
        migrate_music(db, music_dir)

        count = db.execute("SELECT COUNT(*) FROM music_rotation").fetchone()[0]
        assert count == 1
        row = db.execute("SELECT name, artist FROM music_rotation").fetchone()
        assert row[0] == "White Pony"
        assert row[1] == "Deftones"


# ---------------------------------------------------------------------------
# Podcast migration
# ---------------------------------------------------------------------------

class TestMigratePodcasts:
    def _make_podcast_files(self, tmp_path):
        pod_dir = tmp_path / "podcasts"
        pod_dir.mkdir(parents=True)

        daily = {
            "date": "2026-04-09",
            "recent_episodes": [
                {"uuid": "ep1", "podcast": "Latent Space", "title": "Ep 100",
                 "url": "", "duration_seconds": 3600, "played_up_to_seconds": 3600,
                 "playing_status": 3, "published": "2026-04-08"},
                {"uuid": "ep2", "podcast": "Lex Fridman", "title": "Interview",
                 "url": "", "duration_seconds": 7200, "played_up_to_seconds": 1800,
                 "playing_status": 2, "published": "2026-04-07"},
            ],
            "subscriptions": [
                {"uuid": "sub1", "title": "Latent Space", "author": "AI Folks", "url": ""},
                {"uuid": "sub2", "title": "Lex Fridman", "author": "Lex", "url": ""},
            ],
        }
        (pod_dir / "2026-04-09.json").write_text(json.dumps(daily))
        return pod_dir

    def test_episode_count(self, db, tmp_path):
        """Episode count should match JSON."""
        from migrate_json_to_sqlite import migrate_podcasts

        pod_dir = self._make_podcast_files(tmp_path)
        migrate_podcasts(db, pod_dir)

        count = db.execute("SELECT COUNT(*) FROM podcast_episodes").fetchone()[0]
        assert count == 2

    def test_episode_fields(self, db, tmp_path):
        """Episode fields should be extracted correctly."""
        from migrate_json_to_sqlite import migrate_podcasts

        pod_dir = self._make_podcast_files(tmp_path)
        migrate_podcasts(db, pod_dir)

        row = db.execute(
            "SELECT podcast, title, duration_seconds FROM podcast_episodes WHERE uuid='ep1'"
        ).fetchone()
        assert row[0] == "Latent Space"
        assert row[1] == "Ep 100"
        assert row[2] == 3600

    def test_subscriptions(self, db, tmp_path):
        """Subscriptions should be migrated."""
        from migrate_json_to_sqlite import migrate_podcasts

        pod_dir = self._make_podcast_files(tmp_path)
        migrate_podcasts(db, pod_dir)

        count = db.execute("SELECT COUNT(*) FROM podcast_subscriptions").fetchone()[0]
        assert count == 2


# ---------------------------------------------------------------------------
# State migration
# ---------------------------------------------------------------------------

class TestMigrateState:
    def test_memory_json(self, db, tmp_path):
        """memory.json fields should populate session_memory."""
        from migrate_json_to_sqlite import migrate_state

        state_dir = tmp_path / "state"
        state_dir.mkdir()
        memory = {
            "last_briefing": "2026-04-09",
            "running_context": {
                "health_trends": "stable",
                "music_phase": "post-rock",
            },
        }
        (state_dir / "memory.json").write_text(json.dumps(memory))
        (state_dir / "user-notes.json").write_text(json.dumps({"notes": []}))
        (state_dir / "rotation.json").write_text(json.dumps({"last_updated": "2026-04-09"}))

        migrate_state(db, state_dir)

        row = db.execute(
            "SELECT value FROM session_memory WHERE key='last_briefing'"
        ).fetchone()
        assert row is not None
        assert json.loads(row[0]) == "2026-04-09"

        row = db.execute(
            "SELECT value FROM session_memory WHERE key='running_context'"
        ).fetchone()
        ctx = json.loads(row[0])
        assert ctx["health_trends"] == "stable"

    def test_rotation_json(self, db, tmp_path):
        """rotation.json should be stored in session_memory."""
        from migrate_json_to_sqlite import migrate_state

        state_dir = tmp_path / "state"
        state_dir.mkdir()
        (state_dir / "memory.json").write_text(json.dumps({}))
        (state_dir / "user-notes.json").write_text(json.dumps({"notes": []}))
        rotation = {
            "last_updated": "2026-04-09",
            "books": {"last_surfaced": "The Black Company", "index": 0},
        }
        (state_dir / "rotation.json").write_text(json.dumps(rotation))

        migrate_state(db, state_dir)

        row = db.execute(
            "SELECT value FROM session_memory WHERE key='rotation'"
        ).fetchone()
        assert row is not None
        rot = json.loads(row[0])
        assert rot["books"]["last_surfaced"] == "The Black Company"

    def test_user_notes(self, db, tmp_path):
        """user-notes.json entries should migrate to user_notes table."""
        from migrate_json_to_sqlite import migrate_state

        state_dir = tmp_path / "state"
        state_dir.mkdir()
        (state_dir / "memory.json").write_text(json.dumps({}))
        (state_dir / "rotation.json").write_text(json.dumps({}))
        notes = {
            "notes": [
                {"date": "2026-04-08", "text": "Try that ramen place", "tags": ["food"], "source": "conversation"},
                {"date": "2026-04-09", "text": "Blog about TPUs", "tags": ["tech"], "source": "conversation"},
            ]
        }
        (state_dir / "user-notes.json").write_text(json.dumps(notes))

        migrate_state(db, state_dir)

        count = db.execute("SELECT COUNT(*) FROM user_notes").fetchone()[0]
        assert count == 2
