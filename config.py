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


# ── Required ──────────────────────────────────────────────────────────────────
DISCORD_TOKEN: str = _require("DISCORD_TOKEN")
GUILD_ID: int = int(_require("GUILD_ID"))

# ── Optional with defaults ─────────────────────────────────────────────────────
EVENT_CHANNEL_ID: int | None = int(v) if (v := _optional("EVENT_CHANNEL_ID")) else None
LOG_CHANNEL_ID: int | None = int(v) if (v := _optional("LOG_CHANNEL_ID")) else None
ATTENDANCE_WARNING_THRESHOLD: int = int(_optional("ATTENDANCE_WARNING_THRESHOLD", "75"))
TIMEZONE: str = _optional("TIMEZONE", "America/New_York")
COMMAND_PREFIX: str = _optional("COMMAND_PREFIX", "!")
DATABASE_PATH: str = _optional("DATABASE_PATH", "./data/raidbot.db")

# Derived
import pathlib
DB_DIR = pathlib.Path(DATABASE_PATH).parent
DB_DIR.mkdir(parents=True, exist_ok=True)
