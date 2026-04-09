"""TDD tests for collector dual-write to SQLite.

Written BEFORE modifying collectors. Tests verify that collectors
write to SQLite alongside JSON, with proper dedup and error logging.
"""

import importlib
import json
import sqlite3
from unittest.mock import patch, MagicMock

import pytest

# Import modules with hyphens in names
health_receiver = importlib.import_module("health-receiver")
collect_apple_music = importlib.import_module("collect-apple-music")
collect_pocketcasts = importlib.import_module("collect-pocketcasts")


# ---------------------------------------------------------------------------
# Health receiver tests
# ---------------------------------------------------------------------------

class TestHealthReceiverDB:
    def test_writes_to_db(self, db, sample_health_webhook_payload):
        """Webhook POST should write samples and daily summaries to DB."""
        health_receiver._process_to_db(db, sample_health_webhook_payload["data"])

        # Should have samples for step_count (3) + heart_rate (3) + resting_heart_rate (1) = 7
        count = db.execute("SELECT COUNT(*) FROM health_samples").fetchone()[0]
        assert count == 7

        # Should have daily summaries
        daily_count = db.execute("SELECT COUNT(*) FROM health_daily").fetchone()[0]
        assert daily_count == 3  # 3 metrics

    def test_dedup_samples(self, db, sample_health_webhook_payload):
        """POSTing same data twice should not duplicate samples."""
        health_receiver._process_to_db(db, sample_health_webhook_payload["data"])
        count1 = db.execute("SELECT COUNT(*) FROM health_samples").fetchone()[0]

        health_receiver._process_to_db(db, sample_health_webhook_payload["data"])
        count2 = db.execute("SELECT COUNT(*) FROM health_samples").fetchone()[0]

        assert count1 == count2

    def test_recomputes_daily(self, db):
        """New samples for existing date should update daily summary."""
        # First batch
        data1 = {
            "metrics": [{
                "name": "step_count", "units": "count",
                "data": [{"date": "2026-04-09 08:00:00 +0100", "qty": 1000}],
            }],
            "workouts": [],
        }
        health_receiver._process_to_db(db, data1)

        total1 = db.execute(
            "SELECT daily_total FROM health_daily WHERE metric='step_count' AND date='2026-04-09'"
        ).fetchone()[0]

        # Second batch with new timestamp
        data2 = {
            "metrics": [{
                "name": "step_count", "units": "count",
                "data": [{"date": "2026-04-09 09:00:00 +0100", "qty": 2000}],
            }],
            "workouts": [],
        }
        health_receiver._process_to_db(db, data2)

        total2 = db.execute(
            "SELECT daily_total FROM health_daily WHERE metric='step_count' AND date='2026-04-09'"
        ).fetchone()[0]

        assert total2 == 3000  # 1000 + 2000

    def test_logs_run(self, db, sample_health_webhook_payload):
        """Should log a collector run after processing."""
        health_receiver._process_to_db(db, sample_health_webhook_payload["data"])

        row = db.execute(
            "SELECT collector, status FROM collector_runs WHERE collector='health-receiver'"
        ).fetchone()
        assert row is not None
        assert row[0] == "health-receiver"
        assert row[1] == "success"

    def test_writes_workouts(self, db, sample_health_webhook_payload):
        """Workouts in the payload should be written to the workouts table."""
        health_receiver._process_to_db(db, sample_health_webhook_payload["data"])

        row = db.execute(
            "SELECT type, duration_minutes, distance_km FROM workouts"
        ).fetchone()
        assert row is not None
        assert row[0] == "running"
        assert row[1] == 45.5
        assert row[2] == 8.2


# ---------------------------------------------------------------------------
# Apple Music collector tests
# ---------------------------------------------------------------------------

class TestMusicCollectorDB:
    def _mock_tracks(self):
        return [
            {"id": "t1", "track": "Song A", "artist": "Artist A", "album": "Album A",
             "genre": "Rock", "duration_ms": 240000, "played_at": "", "url": ""},
            {"id": "t2", "track": "Song B", "artist": "Artist B", "album": "Album B",
             "genre": "Pop", "duration_ms": 300000, "played_at": "", "url": ""},
        ]

    def _mock_rotation(self):
        return [
            {"id": "hr1", "name": "White Pony", "artist": "Deftones", "type": "albums", "url": ""},
        ]

    def test_writes_tracks(self, db):
        """Should write tracks to music_tracks table."""
        collect_apple_music._write_to_db(db, self._mock_tracks(), self._mock_rotation(), "2026-04-09")

        count = db.execute("SELECT COUNT(*) FROM music_tracks").fetchone()[0]
        assert count == 2

    def test_writes_rotation(self, db):
        """Should write heavy rotation to music_rotation table."""
        collect_apple_music._write_to_db(db, self._mock_tracks(), self._mock_rotation(), "2026-04-09")

        count = db.execute("SELECT COUNT(*) FROM music_rotation").fetchone()[0]
        assert count == 1

    def test_dedup_across_runs(self, db):
        """Two runs on same day should not duplicate tracks."""
        collect_apple_music._write_to_db(db, self._mock_tracks(), self._mock_rotation(), "2026-04-09")
        collect_apple_music._write_to_db(db, self._mock_tracks(), self._mock_rotation(), "2026-04-09")

        count = db.execute("SELECT COUNT(*) FROM music_tracks").fetchone()[0]
        assert count == 2  # Same track_ids, same date

    def test_logs_error(self, db):
        """Error during collection should be logged."""
        from db import log_run

        log_run(db, "apple-music", "error", error_message="401 token expired")

        row = db.execute(
            "SELECT status, error_message FROM collector_runs WHERE collector='apple-music'"
        ).fetchone()
        assert row[0] == "error"
        assert "401" in row[1]


# ---------------------------------------------------------------------------
# Podcast collector tests
# ---------------------------------------------------------------------------

class TestPodcastCollectorDB:
    def _mock_episodes(self):
        return [
            {"uuid": "ep1", "podcast": "Latent Space", "title": "Ep 100",
             "url": "", "duration_seconds": 3600, "played_up_to_seconds": 3600,
             "playing_status": 3, "published": "2026-04-08"},
        ]

    def _mock_subs(self):
        return [
            {"uuid": "sub1", "title": "Latent Space", "author": "Swyx", "url": ""},
            {"uuid": "sub2", "title": "Lex Fridman", "author": "Lex", "url": ""},
        ]

    def test_writes_episodes(self, db):
        """Should write episodes to podcast_episodes table."""
        collect_pocketcasts._write_to_db(db, self._mock_episodes(), self._mock_subs(), "2026-04-09")

        count = db.execute("SELECT COUNT(*) FROM podcast_episodes").fetchone()[0]
        assert count == 1

    def test_upserts_subscriptions(self, db):
        """Subscriptions should be upserted, not duplicated."""
        collect_pocketcasts._write_to_db(db, self._mock_episodes(), self._mock_subs(), "2026-04-09")
        collect_pocketcasts._write_to_db(db, [], self._mock_subs(), "2026-04-10")

        count = db.execute("SELECT COUNT(*) FROM podcast_subscriptions").fetchone()[0]
        assert count == 2  # Same UUIDs, upserted

        # last_seen should be updated
        row = db.execute(
            "SELECT last_seen FROM podcast_subscriptions WHERE uuid='sub1'"
        ).fetchone()
        assert row[0] == "2026-04-10"
