#!/usr/bin/env python3
"""Collect recent listening data from Apple Music API and write to SQLite."""

import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import jwt
import requests

from db import get_db, init_db, log_run

APPLE_MUSIC_API = "https://api.music.apple.com/v1"

TEAM_ID = os.environ.get("APPLE_TEAM_ID")
KEY_ID = os.environ.get("APPLE_MUSIC_KEY_ID")
PRIVATE_KEY_PATH = os.environ.get("APPLE_MUSIC_PRIVATE_KEY_PATH")
MUSIC_USER_TOKEN = os.environ.get("APPLE_MUSIC_USER_TOKEN")


def generate_developer_token() -> str:
    """Generate a MusicKit developer token (JWT, valid 6 months max)."""
    key_path = Path(PRIVATE_KEY_PATH).expanduser()
    private_key = key_path.read_text()

    now = int(time.time())
    payload = {
        "iss": TEAM_ID,
        "iat": now,
        "exp": now + (60 * 60 * 24 * 180),  # 180 days
    }
    headers = {
        "alg": "ES256",
        "kid": KEY_ID,
    }
    return jwt.encode(payload, private_key, algorithm="ES256", headers=headers)


def apple_music_get(endpoint: str, dev_token: str, params: dict | None = None) -> dict:
    """Make an authenticated request to the Apple Music API."""
    resp = requests.get(
        f"{APPLE_MUSIC_API}{endpoint}",
        headers={
            "Authorization": f"Bearer {dev_token}",
            "Music-User-Token": MUSIC_USER_TOKEN,
        },
        params=params or {},
        timeout=30,
    )
    if not resp.ok:
        print(
            f"API error {resp.status_code} for {endpoint}: {resp.text}", file=sys.stderr
        )
        resp.raise_for_status()
    return resp.json()


def collect_recent_tracks(dev_token: str) -> list[dict]:
    """Fetch recently played tracks."""
    data = apple_music_get("/me/recent/played/tracks", dev_token, {"limit": 30})
    tracks = data.get("data", [])
    return [
        {
            "track": t.get("attributes", {}).get("name", ""),
            "artist": t.get("attributes", {}).get("artistName", ""),
            "album": t.get("attributes", {}).get("albumName", ""),
            "duration_ms": t.get("attributes", {}).get("durationInMillis", 0),
            "genre": (t.get("attributes", {}).get("genreNames", []) or [""])[0],
            "url": t.get("attributes", {}).get("url", ""),
            "artwork": t.get("attributes", {}).get("artwork", {}).get("url", ""),
            "played_at": t.get("attributes", {}).get("lastPlayedDate", ""),
            "id": t.get("id", ""),
        }
        for t in tracks
    ]


def collect_heavy_rotation(dev_token: str) -> list[dict]:
    """Fetch heavy rotation (frequently played)."""
    data = apple_music_get("/me/history/heavy-rotation", dev_token, {"limit": 10})
    items = data.get("data", [])
    return [
        {
            "name": item.get("attributes", {}).get("name", ""),
            "artist": item.get("attributes", {}).get("artistName", ""),
            "type": item.get("type", ""),
            "url": item.get("attributes", {}).get("url", ""),
            "id": item.get("id", ""),
        }
        for item in items
    ]


def _write_to_db(conn, tracks: list[dict], rotation: list[dict], today: str):
    """Write collected music data to SQLite."""
    t0 = time.monotonic()
    rows = 0
    try:
        for t in tracks:
            track_id = t.get("id", "")
            if not track_id:
                track_id = (
                    f"{t.get('track', '')}|{t.get('artist', '')}|{t.get('album', '')}"
                )
            conn.execute(
                "INSERT OR IGNORE INTO music_tracks "
                "(date, track_id, track, artist, album, genre, duration_ms, played_at, url) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    today,
                    track_id,
                    t.get("track", ""),
                    t.get("artist", ""),
                    t.get("album", ""),
                    t.get("genre", ""),
                    t.get("duration_ms", 0),
                    t.get("played_at", ""),
                    t.get("url", ""),
                ),
            )
            rows += 1

        for item in rotation:
            conn.execute(
                "INSERT INTO music_rotation "
                "(fetched_date, name, artist, type, url, apple_id) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    today,
                    item.get("name", ""),
                    item.get("artist", ""),
                    item.get("type", ""),
                    item.get("url", ""),
                    item.get("id", ""),
                ),
            )

        conn.commit()
        duration = time.monotonic() - t0
        log_run(
            conn,
            "apple-music",
            "success",
            rows_affected=rows,
            duration_seconds=round(duration, 2),
        )
    except Exception as e:
        duration = time.monotonic() - t0
        log_run(
            conn,
            "apple-music",
            "error",
            error_message=str(e),
            duration_seconds=round(duration, 2),
        )
        raise


def main():
    missing = []
    if not TEAM_ID:
        missing.append("APPLE_TEAM_ID")
    if not KEY_ID:
        missing.append("APPLE_MUSIC_KEY_ID")
    if not PRIVATE_KEY_PATH:
        missing.append("APPLE_MUSIC_PRIVATE_KEY_PATH")
    if not MUSIC_USER_TOKEN:
        missing.append("APPLE_MUSIC_USER_TOKEN")
    if missing:
        print(
            f"Error: Missing environment variables: {', '.join(missing)}",
            file=sys.stderr,
        )
        sys.exit(1)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    dev_token = generate_developer_token()

    recent = collect_recent_tracks(dev_token)
    print(f"Fetched {len(recent)} recent tracks")

    rotation = collect_heavy_rotation(dev_token)
    print(f"Fetched {len(rotation)} heavy rotation items")

    db_conn = get_db()
    init_db(db_conn)
    _write_to_db(db_conn, recent, rotation, today)
    db_conn.close()
    print("Written to SQLite")


if __name__ == "__main__":
    main()
