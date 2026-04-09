"""TDD tests for query-db.py — the CLI query interface for Claude.

Written BEFORE query-db.py implementation. Tests cover all subcommands:
health-today, health-trends, music-recent, podcasts-recent, memory,
user-notes, collector-status, rotation, maintenance.
"""

import json
from datetime import date, timedelta


TODAY = date.today().isoformat()
YESTERDAY = (date.today() - timedelta(days=1)).isoformat()
TWO_DAYS_AGO = (date.today() - timedelta(days=2)).isoformat()


def _insert_health_daily(db, day, metric, daily_total=None, average=None, sample_count=5):
    db.execute(
        "INSERT INTO health_daily (date, metric, units, sample_count, daily_total, average, min_value, max_value, latest_value) "
        "VALUES (?, ?, 'count', ?, ?, ?, ?, ?, ?)",
        (day, metric, sample_count, daily_total, average,
         (average * 0.8 if average else None),
         (average * 1.2 if average else None),
         (daily_total or average)),
    )
    db.commit()


def _insert_health_samples(db, day, metric, values):
    for i, val in enumerate(values):
        db.execute(
            "INSERT OR IGNORE INTO health_samples (date, metric, timestamp, value, units) "
            "VALUES (?, ?, ?, ?, 'count')",
            (day, metric, f"{day} {8+i:02d}:00:00 +0100", val),
        )
    db.commit()


# ---------------------------------------------------------------------------
# health-today
# ---------------------------------------------------------------------------

class TestHealthToday:
    def test_returns_today_and_yesterday(self, db):
        """Should return summaries for today and yesterday only."""
        from query_db import health_today

        _insert_health_daily(db, TWO_DAYS_AGO, "step_count", daily_total=5000)
        _insert_health_daily(db, YESTERDAY, "step_count", daily_total=8000)
        _insert_health_daily(db, TODAY, "step_count", daily_total=3000)

        result = health_today(db)
        dates_in_result = {m["date"] for m in result.get("daily", [])}
        assert TODAY in dates_in_result
        assert YESTERDAY in dates_in_result
        assert TWO_DAYS_AGO not in dates_in_result

    def test_empty_db(self, db):
        """Should return empty structure, not crash."""
        from query_db import health_today

        result = health_today(db)
        assert "daily" in result
        assert "workouts" in result
        assert len(result["daily"]) == 0

    def test_includes_recent_workouts(self, db):
        """Should include workouts from the last 3 days."""
        from query_db import health_today

        three_ago = (date.today() - timedelta(days=3)).isoformat()
        four_ago = (date.today() - timedelta(days=4)).isoformat()

        db.execute(
            "INSERT INTO workouts (date, type, start_time, duration_minutes, distance_km, avg_heart_rate) "
            "VALUES (?, 'running', ?, 45.5, 8.2, 168)",
            (YESTERDAY, f"{YESTERDAY} 07:00:00 +0100"),
        )
        db.execute(
            "INSERT INTO workouts (date, type, start_time, duration_minutes) "
            "VALUES (?, 'strength', ?, 60)",
            (four_ago, f"{four_ago} 18:00:00 +0100"),
        )
        db.commit()

        result = health_today(db)
        workout_dates = {w["date"] for w in result.get("workouts", [])}
        assert YESTERDAY in workout_dates
        assert four_ago not in workout_dates


# ---------------------------------------------------------------------------
# health-trends
# ---------------------------------------------------------------------------

class TestHealthTrends:
    def _insert_days(self, db, metric, values_30d):
        """Insert daily values going back from yesterday."""
        for i, val in enumerate(values_30d):
            day = (date.today() - timedelta(days=i + 1)).isoformat()
            _insert_health_daily(db, day, metric, daily_total=val)

    def test_7d_avg(self, db):
        """7-day average should be computed correctly.

        _insert_days inserts at offsets 1..N (yesterday, 2 days ago, ...).
        health_trends queries date > (today-7), which captures offsets 1-6
        (6 days), since offset 7 = exactly today-7 is excluded by '>'.
        """
        from query_db import health_trends

        values = [10000, 9000, 11000, 8000, 10500, 9500, 10000, 7000, 6000, 5000]
        self._insert_days(db, "step_count", values)

        result = health_trends(db)
        steps = result.get("step_count", {})
        # Query uses date > (today-7), so it picks up offsets 1-6 (values[:6])
        included = values[:6]
        expected_7d = round(sum(included) / len(included), 1)
        assert steps.get("avg_7d") == expected_7d

    def test_30d_avg(self, db):
        """30-day average: date > (today-30) captures offsets 1-29."""
        from query_db import health_trends

        values = [10000] * 7 + [8000] * 23
        self._insert_days(db, "step_count", values)

        result = health_trends(db)
        steps = result.get("step_count", {})
        # date > (today-30) captures offsets 1-29 (values[:29])
        included = values[:29]
        expected_30d = round(sum(included) / len(included), 1)
        assert steps.get("avg_30d") == expected_30d

    def test_direction_increasing(self, db):
        """7d avg > older avg by >5% should be 'increasing'."""
        from query_db import health_trends

        # Recent 7 days: 10000, older 23 days: 8000
        values = [10000] * 7 + [8000] * 23
        self._insert_days(db, "step_count", values)

        result = health_trends(db)
        assert result.get("step_count", {}).get("trend") == "increasing"

    def test_direction_stable(self, db):
        """Within 5% should be 'stable'."""
        from query_db import health_trends

        values = [10000] * 7 + [9800] * 23  # ~2% diff
        self._insert_days(db, "step_count", values)

        result = health_trends(db)
        assert result.get("step_count", {}).get("trend") == "stable"

    def test_direction_declining(self, db):
        """7d avg < older avg by >5% should be 'declining'."""
        from query_db import health_trends

        values = [8000] * 7 + [10000] * 23
        self._insert_days(db, "step_count", values)

        result = health_trends(db)
        assert result.get("step_count", {}).get("trend") == "declining"

    def test_insufficient_data_no_trend(self, db):
        """With <10 days of data, trend should be None."""
        from query_db import health_trends

        values = [10000] * 5
        self._insert_days(db, "step_count", values)

        result = health_trends(db)
        assert result.get("step_count", {}).get("trend") is None

    def test_workout_counts(self, db):
        """Should count workouts in 7d and 30d windows."""
        from query_db import health_trends

        for i in range(3):
            day = (date.today() - timedelta(days=i + 1)).isoformat()
            db.execute(
                "INSERT INTO workouts (date, type, start_time, duration_minutes) "
                "VALUES (?, 'running', ?, 45)",
                (day, f"{day} 07:00:00 +0100"),
            )
        for i in range(5):
            day = (date.today() - timedelta(days=i + 10)).isoformat()
            db.execute(
                "INSERT INTO workouts (date, type, start_time, duration_minutes) "
                "VALUES (?, 'strength', ?, 60)",
                (day, f"{day} 18:00:00 +0100"),
            )
        db.commit()

        result = health_trends(db)
        assert result.get("workout_count_7d") == 3
        assert result.get("workout_count_30d") == 8
        assert "running" in result.get("workout_types_30d", {})


# ---------------------------------------------------------------------------
# music-recent
# ---------------------------------------------------------------------------

class TestMusicRecent:
    def test_returns_tracks(self, db):
        """Should return recently collected tracks."""
        from query_db import music_recent

        db.execute(
            "INSERT INTO music_tracks (date, track_id, track, artist, album, genre) "
            "VALUES (?, 'id1', 'Song A', 'Artist A', 'Album A', 'Rock')",
            (TODAY,),
        )
        db.commit()

        result = music_recent(db)
        assert len(result.get("tracks", [])) == 1
        assert result["tracks"][0]["track"] == "Song A"

    def test_dedup_by_track_id(self, db):
        """Duplicate track_id on same date should produce only 1 row."""
        from query_db import music_recent

        db.execute(
            "INSERT OR IGNORE INTO music_tracks (date, track_id, track, artist) "
            "VALUES (?, 'dup1', 'Song', 'Artist')",
            (TODAY,),
        )
        db.execute(
            "INSERT OR IGNORE INTO music_tracks (date, track_id, track, artist) "
            "VALUES (?, 'dup1', 'Song Copy', 'Artist Copy')",
            (TODAY,),
        )
        db.commit()

        result = music_recent(db)
        assert len(result.get("tracks", [])) == 1

    def test_limit_50(self, db):
        """Should return at most 50 tracks."""
        from query_db import music_recent

        for i in range(60):
            db.execute(
                "INSERT INTO music_tracks (date, track_id, track, artist) "
                "VALUES (?, ?, ?, 'Artist')",
                (TODAY, f"id-{i}", f"Song {i}"),
            )
        db.commit()

        result = music_recent(db)
        assert len(result.get("tracks", [])) == 50

    def test_includes_heavy_rotation(self, db):
        """Should include current heavy rotation items."""
        from query_db import music_recent

        db.execute(
            "INSERT INTO music_rotation (fetched_date, name, artist, type) "
            "VALUES (?, 'White Pony', 'Deftones', 'albums')",
            (TODAY,),
        )
        db.commit()

        result = music_recent(db)
        assert len(result.get("heavy_rotation", [])) >= 1


# ---------------------------------------------------------------------------
# podcasts-recent
# ---------------------------------------------------------------------------

class TestPodcastsRecent:
    def test_returns_episodes(self, db):
        """Should return recent podcast episodes."""
        from query_db import podcasts_recent

        db.execute(
            "INSERT INTO podcast_episodes (date, uuid, podcast, title, duration_seconds) "
            "VALUES (?, 'ep1', 'Latent Space', 'Episode 100', 3600)",
            (TODAY,),
        )
        db.commit()

        result = podcasts_recent(db)
        assert len(result.get("episodes", [])) == 1

    def test_sorted_by_date_desc(self, db):
        """Most recent episodes should come first."""
        from query_db import podcasts_recent

        db.execute(
            "INSERT INTO podcast_episodes (date, uuid, podcast, title) "
            "VALUES (?, 'ep-old', 'Pod', 'Old Episode')",
            (TWO_DAYS_AGO,),
        )
        db.execute(
            "INSERT INTO podcast_episodes (date, uuid, podcast, title) "
            "VALUES (?, 'ep-new', 'Pod', 'New Episode')",
            (TODAY,),
        )
        db.commit()

        result = podcasts_recent(db)
        episodes = result.get("episodes", [])
        assert episodes[0]["title"] == "New Episode"

    def test_includes_subscription_count(self, db):
        """Should report subscription count."""
        from query_db import podcasts_recent

        db.execute(
            "INSERT INTO podcast_subscriptions (uuid, title, author, last_seen) "
            "VALUES ('sub1', 'Pod A', 'Author', ?)",
            (TODAY,),
        )
        db.execute(
            "INSERT INTO podcast_subscriptions (uuid, title, author, last_seen) "
            "VALUES ('sub2', 'Pod B', 'Author', ?)",
            (TODAY,),
        )
        db.commit()

        result = podcasts_recent(db)
        assert result.get("subscription_count") == 2


# ---------------------------------------------------------------------------
# collector-status
# ---------------------------------------------------------------------------

class TestCollectorStatus:
    def test_flags_stale(self, db):
        """Collector with last run >24h ago should show warning."""
        from query_db import collector_status

        old_time = (date.today() - timedelta(days=2)).isoformat() + "T08:00:00"
        db.execute(
            "INSERT INTO collector_runs (collector, started_at, status, completed_at) "
            "VALUES ('apple-music', ?, 'success', ?)",
            (old_time, old_time),
        )
        db.commit()

        result = collector_status(db)
        am = result.get("apple-music", {})
        assert am.get("status") in ("stale", "warning")

    def test_shows_ok(self, db):
        """Collector with recent successful run should be ok."""
        from query_db import collector_status
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).isoformat()
        db.execute(
            "INSERT INTO collector_runs (collector, started_at, status, completed_at) "
            "VALUES ('apple-music', ?, 'success', ?)",
            (now, now),
        )
        db.commit()

        result = collector_status(db)
        assert result.get("apple-music", {}).get("status") == "ok"

    def test_shows_never_run(self, db):
        """Collector with no runs should show 'never_run'."""
        from query_db import collector_status

        result = collector_status(db)
        # All known collectors should be reported
        assert result.get("apple-music", {}).get("status") == "never_run"

    def test_shows_last_error(self, db):
        """Should surface the most recent error message."""
        from query_db import collector_status
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).isoformat()
        db.execute(
            "INSERT INTO collector_runs (collector, started_at, status, error_message) "
            "VALUES ('pocketcasts', ?, 'error', '401 Unauthorized')",
            (now,),
        )
        db.commit()

        result = collector_status(db)
        pc = result.get("pocketcasts", {})
        assert "401" in (pc.get("last_error") or "")


# ---------------------------------------------------------------------------
# memory & user-notes
# ---------------------------------------------------------------------------

class TestMemory:
    def test_read_memory(self, db):
        """Should return all session memory key-value pairs."""
        from query_db import memory

        db.execute(
            "INSERT INTO session_memory (key, value, updated_at) "
            "VALUES ('health_trends', '\"stable\"', ?)",
            (TODAY,),
        )
        db.execute(
            "INSERT INTO session_memory (key, value, updated_at) "
            "VALUES ('music_phase', '\"post-rock\"', ?)",
            (TODAY,),
        )
        db.commit()

        result = memory(db)
        assert result.get("health_trends") == "stable"
        assert result.get("music_phase") == "post-rock"

    def test_empty_memory(self, db):
        """Empty memory should return empty dict."""
        from query_db import memory

        result = memory(db)
        assert result == {}


class TestUserNotes:
    def test_recent_notes(self, db):
        """Should return notes from the specified window."""
        from query_db import user_notes

        db.execute(
            "INSERT INTO user_notes (date, text, tags, source) "
            "VALUES (?, 'Try that new ramen place', '[\"food\"]', 'conversation')",
            (TODAY,),
        )
        old = (date.today() - timedelta(days=30)).isoformat()
        db.execute(
            "INSERT INTO user_notes (date, text, tags, source) "
            "VALUES (?, 'Old note', '[\"misc\"]', 'conversation')",
            (old,),
        )
        db.commit()

        result = user_notes(db, days=7)
        assert len(result) == 1
        assert result[0]["text"] == "Try that new ramen place"

    def test_excludes_archived(self, db):
        """Archived notes should not be returned."""
        from query_db import user_notes

        db.execute(
            "INSERT INTO user_notes (date, text, tags, archived) "
            "VALUES (?, 'Archived', '[]', 1)",
            (TODAY,),
        )
        db.commit()

        result = user_notes(db, days=7)
        assert len(result) == 0


# ---------------------------------------------------------------------------
# rotation
# ---------------------------------------------------------------------------

class TestRotation:
    def test_read_rotation(self, db):
        """Should return rotation state from session_memory."""
        from query_db import rotation
        import json

        rot_data = {
            "last_updated": TODAY,
            "books": {"last_surfaced": "The Black Company", "index": 0},
        }
        db.execute(
            "INSERT INTO session_memory (key, value, updated_at) "
            "VALUES ('rotation', ?, ?)",
            (json.dumps(rot_data), TODAY),
        )
        db.commit()

        result = rotation(db)
        assert result.get("books", {}).get("last_surfaced") == "The Black Company"

    def test_empty_rotation(self, db):
        """Missing rotation state should return empty dict."""
        from query_db import rotation

        result = rotation(db)
        assert result == {}


# ---------------------------------------------------------------------------
# maintenance
# ---------------------------------------------------------------------------

class TestMaintenance:
    def test_deletes_old_samples(self, db):
        """Samples older than 90 days should be deleted."""
        from query_db import maintenance

        old = (date.today() - timedelta(days=100)).isoformat()
        recent = (date.today() - timedelta(days=30)).isoformat()

        db.execute(
            "INSERT INTO health_samples (date, metric, timestamp, value, units) "
            "VALUES (?, 'step_count', ?, 5000, 'count')",
            (old, f"{old} 08:00:00 +0100"),
        )
        db.execute(
            "INSERT INTO health_samples (date, metric, timestamp, value, units) "
            "VALUES (?, 'step_count', ?, 8000, 'count')",
            (recent, f"{recent} 08:00:00 +0100"),
        )
        db.commit()

        result = maintenance(db)

        remaining = db.execute("SELECT COUNT(*) FROM health_samples").fetchone()[0]
        assert remaining == 1  # Only recent sample survives

    def test_preserves_daily_summaries(self, db):
        """health_daily rows should survive maintenance regardless of age."""
        from query_db import maintenance

        old = (date.today() - timedelta(days=200)).isoformat()
        _insert_health_daily(db, old, "step_count", daily_total=5000)

        maintenance(db)

        remaining = db.execute("SELECT COUNT(*) FROM health_daily").fetchone()[0]
        assert remaining == 1

    def test_preserves_recent_samples(self, db):
        """Samples within 90 days should not be deleted."""
        from query_db import maintenance

        recent = (date.today() - timedelta(days=89)).isoformat()
        db.execute(
            "INSERT INTO health_samples (date, metric, timestamp, value, units) "
            "VALUES (?, 'step_count', ?, 8000, 'count')",
            (recent, f"{recent} 08:00:00 +0100"),
        )
        db.commit()

        maintenance(db)

        remaining = db.execute("SELECT COUNT(*) FROM health_samples").fetchone()[0]
        assert remaining == 1

    def test_deletes_old_music_tracks(self, db):
        """Music tracks older than 90 days should be deleted."""
        from query_db import maintenance

        old = (date.today() - timedelta(days=100)).isoformat()
        db.execute(
            "INSERT INTO music_tracks (date, track_id, track, artist) "
            "VALUES (?, 'old1', 'Old Song', 'Artist')",
            (old,),
        )
        db.execute(
            "INSERT INTO music_tracks (date, track_id, track, artist) "
            "VALUES (?, 'new1', 'New Song', 'Artist')",
            (TODAY,),
        )
        db.commit()

        maintenance(db)

        remaining = db.execute("SELECT COUNT(*) FROM music_tracks").fetchone()[0]
        assert remaining == 1

    def test_deletes_old_collector_runs(self, db):
        """Collector runs older than 30 days should be pruned."""
        from query_db import maintenance

        old = (date.today() - timedelta(days=35)).isoformat() + "T08:00:00"
        db.execute(
            "INSERT INTO collector_runs (collector, started_at, status) "
            "VALUES ('test', ?, 'success')",
            (old,),
        )
        db.commit()

        maintenance(db)

        remaining = db.execute("SELECT COUNT(*) FROM collector_runs").fetchone()[0]
        assert remaining == 0

    def test_returns_summary(self, db):
        """maintenance should return a summary of what was deleted."""
        from query_db import maintenance

        result = maintenance(db)
        assert "deleted" in result or "health_samples" in result
