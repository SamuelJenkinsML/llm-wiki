#!/usr/bin/env python3
"""Collect recent listening data from Last.fm API and write to vault."""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

LASTFM_API = "https://ws.audioscrobbler.com/2.0/"
DATA_DIR = Path.home() / "Documents" / "Day to day" / "_llm" / "data" / "music"

API_KEY = os.environ.get("LASTFM_API_KEY")
USERNAME = os.environ.get("LASTFM_USERNAME")


def lastfm_get(method: str, **params) -> dict:
    resp = requests.get(
        LASTFM_API,
        params={"method": method, "user": USERNAME, "api_key": API_KEY, "format": "json", **params},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def collect_recent_tracks() -> list[dict]:
    data = lastfm_get("user.getrecenttracks", limit=50)
    tracks = data.get("recenttracks", {}).get("track", [])
    return [
        {
            "artist": t.get("artist", {}).get("#text", ""),
            "track": t.get("name", ""),
            "album": t.get("album", {}).get("#text", ""),
            "url": t.get("url", ""),
            "now_playing": "@attr" in t and t["@attr"].get("nowplaying") == "true",
            "played_at": t.get("date", {}).get("#text", ""),
            "timestamp": t.get("date", {}).get("uts", ""),
        }
        for t in tracks
    ]


def collect_weekly_top() -> dict:
    artists_data = lastfm_get("user.gettopartists", period="7day", limit=10)
    tracks_data = lastfm_get("user.gettoptracks", period="7day", limit=10)

    top_artists = [
        {"name": a["name"], "playcount": int(a["playcount"]), "url": a["url"]}
        for a in artists_data.get("topartists", {}).get("artist", [])
    ]
    top_tracks = [
        {
            "artist": t["artist"]["name"],
            "track": t["name"],
            "playcount": int(t["playcount"]),
            "url": t["url"],
        }
        for t in tracks_data.get("toptracks", {}).get("track", [])
    ]
    return {"top_artists": top_artists, "top_tracks": top_tracks, "period": "7day"}


def main():
    if not API_KEY or not USERNAME:
        print("Error: LASTFM_API_KEY and LASTFM_USERNAME must be set", file=sys.stderr)
        sys.exit(1)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Fetch recent tracks
    recent = collect_recent_tracks()
    (DATA_DIR / "recent-tracks.json").write_text(
        json.dumps({"fetched": today, "tracks": recent}, indent=2)
    )
    print(f"Wrote {len(recent)} recent tracks")

    # Fetch weekly tops
    weekly = collect_weekly_top()
    weekly["fetched"] = today
    (DATA_DIR / "weekly-top.json").write_text(json.dumps(weekly, indent=2))
    print(f"Wrote weekly top: {len(weekly['top_artists'])} artists, {len(weekly['top_tracks'])} tracks")

    # Daily snapshot
    snapshot = {"date": today, "recent_tracks": recent, "weekly": weekly}
    (DATA_DIR / f"{today}.json").write_text(json.dumps(snapshot, indent=2))
    print(f"Wrote daily snapshot: {DATA_DIR / today}.json")


if __name__ == "__main__":
    main()
