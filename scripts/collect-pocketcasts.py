#!/usr/bin/env python3
"""Collect recent listening data from Pocket Casts and write to SQLite."""

import os
import sys
import time
from datetime import datetime, timezone

import requests

from db import get_db, init_db, log_run

POCKETCASTS_API = "https://api.pocketcasts.com"

EMAIL = os.environ.get("POCKETCASTS_EMAIL")
PASSWORD = os.environ.get("POCKETCASTS_PASSWORD")


def login() -> str:
    resp = requests.post(
        f"{POCKETCASTS_API}/user/login",
        json={"email": EMAIL, "password": PASSWORD},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    token = data.get("token", "")
    if not token:
        print(f"Error: No token in login response: {data}", file=sys.stderr)
        sys.exit(1)
    return token


def get_history(token: str) -> list[dict]:
    resp = requests.post(
        f"{POCKETCASTS_API}/user/history",
        json={},
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    resp.raise_for_status()
    episodes = resp.json().get("episodes", [])
    return [
        {
            "podcast": ep.get("podcastTitle", ""),
            "title": ep.get("title", ""),
            "url": ep.get("url", ""),
            "duration_seconds": ep.get("duration", 0),
            "played_up_to_seconds": ep.get("playedUpTo", 0),
            "playing_status": ep.get("playingStatus", 0),
            "published": ep.get("published", ""),
            "uuid": ep.get("uuid", ""),
        }
        for ep in episodes[:30]  # Keep last 30 episodes
    ]


def get_subscriptions(token: str) -> list[dict]:
    resp = requests.post(
        f"{POCKETCASTS_API}/user/podcast/list",
        json={},
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    resp.raise_for_status()
    podcasts = resp.json().get("podcasts", [])
    return [
        {
            "title": p.get("title", ""),
            "author": p.get("author", ""),
            "uuid": p.get("uuid", ""),
            "url": p.get("url", ""),
        }
        for p in podcasts
    ]


def _write_to_db(conn, episodes: list[dict], subs: list[dict], today: str):
    """Write collected podcast data to SQLite."""
    t0 = time.monotonic()
    rows = 0
    try:
        for ep in episodes:
            conn.execute(
                "INSERT OR IGNORE INTO podcast_episodes "
                "(date, uuid, podcast, title, url, duration_seconds, "
                "played_up_to_seconds, playing_status, published) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    today, ep.get("uuid", ""), ep.get("podcast", ""),
                    ep.get("title", ""), ep.get("url", ""),
                    ep.get("duration_seconds", 0), ep.get("played_up_to_seconds", 0),
                    ep.get("playing_status", 0), ep.get("published", ""),
                ),
            )
            rows += 1

        for sub in subs:
            conn.execute(
                "INSERT OR REPLACE INTO podcast_subscriptions "
                "(uuid, title, author, url, last_seen) VALUES (?, ?, ?, ?, ?)",
                (
                    sub.get("uuid", ""), sub.get("title", ""),
                    sub.get("author", ""), sub.get("url", ""), today,
                ),
            )

        conn.commit()
        duration = time.monotonic() - t0
        log_run(conn, "pocketcasts", "success", rows_affected=rows, duration_seconds=round(duration, 2))
    except Exception as e:
        duration = time.monotonic() - t0
        log_run(conn, "pocketcasts", "error", error_message=str(e), duration_seconds=round(duration, 2))
        raise


def main():
    if not EMAIL or not PASSWORD:
        print("Error: POCKETCASTS_EMAIL and POCKETCASTS_PASSWORD must be set", file=sys.stderr)
        sys.exit(1)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    token = login()

    history = get_history(token)
    print(f"Fetched {len(history)} recent episodes")

    subs = get_subscriptions(token)
    print(f"Fetched {len(subs)} subscriptions")

    db_conn = get_db()
    init_db(db_conn)
    _write_to_db(db_conn, history, subs, today)
    db_conn.close()
    print("Written to SQLite")


if __name__ == "__main__":
    main()
