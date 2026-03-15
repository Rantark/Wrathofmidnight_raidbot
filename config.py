"""
Configuration management for the WoW Raid Bot.
Loads and validates environment variables on startup.
"""

import os
import sys
import logging
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)


def _require(key: str) -> str:
    """Retrieve a required environment variable or exit with a clear error."""
    value = os.getenv(key, "").strip()
    if not value:
        print(f"[FATAL] Missing required environment variable: {key}")
        print(f"        Please copy .env.example to .env and fill in all required values.")
        sys.exit(1)
    return value


def _optional(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


# ── Version ───────────────────────────────────────────────────────────────────
VERSION: str = "1.5.0"

# ── Required ──────────────────────────────────────────────────────────────────
DISCORD_TOKEN: str = _require("DISCORD_TOKEN")
# Comma-separated list of guild IDs for instant command syncing (e.g. "123,456,789").
# Commands are also synced globally, but guild syncs are immediate while global
# syncs can take up to an hour to propagate.  Leave blank to skip guild syncing.
GUILD_IDS: list[int] = [
    int(gid.strip())
    for gid in _optional("GUILD_IDS", _optional("GUILD_ID")).split(",")
    if gid.strip()
]

# ── Optional with defaults ─────────────────────────────────────────────────────
EVENT_CHANNEL_ID: int | None = int(v) if (v := _optional("EVENT_CHANNEL_ID")) else None
LOG_CHANNEL_ID: int | None = int(v) if (v := _optional("LOG_CHANNEL_ID")) else None
ATTENDANCE_WARNING_THRESHOLD: int = int(_optional("ATTENDANCE_WARNING_THRESHOLD", "75"))
TIMEZONE: str = _optional("TIMEZONE", "America/New_York")
COMMAND_PREFIX: str = _optional("COMMAND_PREFIX", "!")
DATABASE_PATH: str = _optional("DATABASE_PATH", "./data/raidbot.db")

# ── Blizzard Battle.net API (optional – enables auto character lookup) ─────────
BNET_CLIENT_ID:     str = _optional("BNET_CLIENT_ID")
BNET_CLIENT_SECRET: str = _optional("BNET_CLIENT_SECRET")

# Derived
import pathlib
DB_DIR = pathlib.Path(DATABASE_PATH).parent
DB_DIR.mkdir(parents=True, exist_ok=True)
