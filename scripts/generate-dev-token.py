#!/usr/bin/env python3
"""Generate an Apple Music developer token (JWT).

Prints the token to stdout. Use this to get the developer token needed
for the browser-based user authorization flow.

Requires APPLE_TEAM_ID, APPLE_MUSIC_KEY_ID, and APPLE_MUSIC_PRIVATE_KEY_PATH
in ~/.config/jarvis/credentials.env or as environment variables.
"""

import os
import sys
import time
from pathlib import Path

# Load credentials from env file if not already set
env_file = Path.home() / ".config" / "jarvis" / "credentials.env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())

import jwt  # noqa: E402

TEAM_ID = os.environ.get("APPLE_TEAM_ID")
KEY_ID = os.environ.get("APPLE_MUSIC_KEY_ID")
PRIVATE_KEY_PATH = os.environ.get("APPLE_MUSIC_PRIVATE_KEY_PATH")

if not all([TEAM_ID, KEY_ID, PRIVATE_KEY_PATH]):
    print("Error: Set APPLE_TEAM_ID, APPLE_MUSIC_KEY_ID, APPLE_MUSIC_PRIVATE_KEY_PATH", file=sys.stderr)
    sys.exit(1)

key_path = Path(PRIVATE_KEY_PATH).expanduser()
if not key_path.exists():
    print(f"Error: Private key not found at {key_path}", file=sys.stderr)
    sys.exit(1)

private_key = key_path.read_text()
now = int(time.time())

token = jwt.encode(
    {"iss": TEAM_ID, "iat": now, "exp": now + (60 * 60 * 24 * 180)},
    private_key,
    algorithm="ES256",
    headers={"alg": "ES256", "kid": KEY_ID},
)

print(token)
