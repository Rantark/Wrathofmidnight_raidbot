"""
Database initialisation.  Creates all tables and indexes on first run.
Safe to call every startup – uses CREATE TABLE IF NOT EXISTS.
"""

import aiosqlite
import logging

log = logging.getLogger(__name__)

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- ── Guild settings ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS guild_settings (
    guild_id              INTEGER PRIMARY KEY,
    event_channel_id      INTEGER,
    log_channel_id        INTEGER,
    attendance_threshold  INTEGER DEFAULT 75,
    timezone              TEXT    DEFAULT 'America/New_York',
    default_max_tanks     INTEGER DEFAULT 2,
    default_max_healers   INTEGER DEFAULT 5,
    default_max_dps       INTEGER DEFAULT 13
);

-- ── Raid leader / officer roles ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS permissions (
    guild_id   INTEGER NOT NULL,
    discord_id INTEGER NOT NULL,
    role       TEXT    NOT NULL CHECK(role IN ('officer','raid_leader')),
    PRIMARY KEY (guild_id, discord_id)
);

-- ── Characters ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS characters (
    discord_id  INTEGER NOT NULL,
    guild_id    INTEGER NOT NULL,
    char_name   TEXT    NOT NULL,
    char_class  TEXT    NOT NULL,
    main_spec   TEXT    NOT NULL,
    off_spec    TEXT,
    is_main     INTEGER NOT NULL DEFAULT 0,
    ilvl        INTEGER,
    notes       TEXT,
    PRIMARY KEY (discord_id, guild_id, char_name)
);

-- ── Events ───────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS events (
    event_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id      INTEGER NOT NULL,
    event_name    TEXT    NOT NULL,
    event_type    TEXT    NOT NULL,
    event_date    TEXT    NOT NULL,
    event_time    TEXT    NOT NULL,
    description   TEXT,
    channel_id    INTEGER,
    message_id    INTEGER,
    created_by    INTEGER NOT NULL,
    max_tanks     INTEGER NOT NULL DEFAULT 2,
    max_healers   INTEGER NOT NULL DEFAULT 5,
    max_dps       INTEGER NOT NULL DEFAULT 13,
    locked        INTEGER NOT NULL DEFAULT 0,
    status        TEXT    NOT NULL DEFAULT 'active'
                          CHECK(status IN ('active','cancelled','completed'))
);

-- ── Event templates ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS event_templates (
    template_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id      INTEGER NOT NULL,
    template_name TEXT    NOT NULL,
    event_name    TEXT    NOT NULL,
    event_type    TEXT    NOT NULL,
    event_time    TEXT    NOT NULL,
    description   TEXT,
    max_tanks     INTEGER NOT NULL DEFAULT 2,
    max_healers   INTEGER NOT NULL DEFAULT 5,
    max_dps       INTEGER NOT NULL DEFAULT 13,
    created_by    INTEGER NOT NULL,
    UNIQUE (guild_id, template_name)
);

-- ── Signups ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS signups (
    signup_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id      INTEGER NOT NULL REFERENCES events(event_id) ON DELETE CASCADE,
    discord_id    INTEGER NOT NULL,
    char_name     TEXT    NOT NULL,
    char_class    TEXT    NOT NULL,
    main_spec     TEXT    NOT NULL,
    role          TEXT    NOT NULL CHECK(role IN ('tank','healer','dps')),
    signup_status TEXT    NOT NULL DEFAULT 'confirmed'
                          CHECK(signup_status IN ('confirmed','bench','tentative','declined')),
    signup_time   TEXT    NOT NULL,
    UNIQUE (event_id, discord_id)
);

-- ── Attendance ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS attendance (
    attendance_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id      INTEGER NOT NULL REFERENCES events(event_id) ON DELETE CASCADE,
    discord_id    INTEGER NOT NULL,
    char_name     TEXT    NOT NULL,
    status        TEXT    NOT NULL DEFAULT 'absent'
                          CHECK(status IN ('present','absent','late','excused')),
    marked_by     INTEGER,
    timestamp     TEXT    NOT NULL,
    UNIQUE (event_id, discord_id)
);

-- ── Absences ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS absences (
    absence_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id   INTEGER NOT NULL,
    guild_id     INTEGER NOT NULL,
    event_id     INTEGER REFERENCES events(event_id) ON DELETE SET NULL,
    reason       TEXT    NOT NULL,
    submitted_at TEXT    NOT NULL
);

-- ── Reminders ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS reminders (
    reminder_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id     INTEGER NOT NULL REFERENCES events(event_id) ON DELETE CASCADE,
    fire_at      TEXT    NOT NULL,
    label        TEXT    NOT NULL,
    sent         INTEGER NOT NULL DEFAULT 0
);

-- ── Boss progress per event ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS event_bosses (
    boss_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id    INTEGER NOT NULL REFERENCES events(event_id) ON DELETE CASCADE,
    raid_name   TEXT    NOT NULL,
    boss_name   TEXT    NOT NULL,
    sort_order  INTEGER NOT NULL DEFAULT 0,
    defeated    INTEGER NOT NULL DEFAULT 0,
    defeated_at TEXT,
    marked_by   INTEGER,
    UNIQUE (event_id, boss_name)
);

-- ── Event channels (multiple channels per guild) ─────────────────────────────
CREATE TABLE IF NOT EXISTS event_channels (
    guild_id    INTEGER NOT NULL,
    channel_id  INTEGER NOT NULL,
    label       TEXT    NOT NULL DEFAULT '',
    PRIMARY KEY (guild_id, channel_id)
);

-- ── Indexes ──────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_event_bosses_event   ON event_bosses(event_id);
CREATE INDEX IF NOT EXISTS idx_event_channels_guild ON event_channels(guild_id);
CREATE INDEX IF NOT EXISTS idx_characters_guild    ON characters(guild_id);
CREATE INDEX IF NOT EXISTS idx_events_guild        ON events(guild_id);
CREATE INDEX IF NOT EXISTS idx_signups_event       ON signups(event_id);
CREATE INDEX IF NOT EXISTS idx_attendance_event    ON attendance(event_id);
CREATE INDEX IF NOT EXISTS idx_attendance_user     ON attendance(discord_id);
CREATE INDEX IF NOT EXISTS idx_reminders_fire      ON reminders(fire_at, sent);
"""


async def init_db(db_path: str) -> None:
    """Create all tables and indexes.  Safe to call on every startup."""
    async with aiosqlite.connect(db_path) as db:
        await db.executescript(SCHEMA)

        # ── Schema migrations (idempotent ALTER TABLE additions) ──────────────
        # These handle upgrading existing databases that predate a column.
        migrations = [
            "ALTER TABLE events ADD COLUMN boss_message_id INTEGER",
            "ALTER TABLE events ADD COLUMN boss_channel_id INTEGER",
        ]
        for sql in migrations:
            try:
                await db.execute(sql)
            except Exception:
                pass  # Column already exists – that's fine

        await db.commit()
    log.info("Database initialised at %s", db_path)
