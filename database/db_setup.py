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
    default_max_dps       INTEGER DEFAULT 13,
    roster_channel_id     INTEGER,
    roster_message_id     INTEGER
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
    professions TEXT,
    progression TEXT,
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

-- ── Scheduled message deletions ─────────────────────────────────────────────
-- Used to delete cancelled-event messages after a delay (survives restarts).
CREATE TABLE IF NOT EXISTS scheduled_deletions (
    deletion_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id   INTEGER NOT NULL,
    message_id   INTEGER NOT NULL,
    delete_at    TEXT    NOT NULL   -- ISO-8601 UTC timestamp
);

-- ── Recurring events ──────────────────────────────────────────────────────────
-- Stores schedules that auto-post a new event each week from a template.
CREATE TABLE IF NOT EXISTS recurring_events (
    recurring_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id         INTEGER NOT NULL,
    template_name    TEXT    NOT NULL,
    day_of_week      INTEGER NOT NULL,  -- 0=Monday … 6=Sunday
    channel_id       INTEGER,           -- NULL = use guild default
    days_advance     INTEGER NOT NULL DEFAULT 7,  -- post N days before the event
    enabled          INTEGER NOT NULL DEFAULT 1,
    created_by       INTEGER NOT NULL,
    last_posted_date TEXT    -- YYYY-MM-DD of the event_date last auto-created
);

-- ── Web → Discord action queue ───────────────────────────────────────────────
-- The web portal writes rows here; the bot's background task reads and acts on them.
-- action: 'post_event' | 'update_event' | 'cancel_event' | 'delete_event'
-- payload: JSON string with extra data (e.g. channel_id/message_id for deletes, reason for cancel)
CREATE TABLE IF NOT EXISTS web_actions (
    action_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id   INTEGER NOT NULL,
    action     TEXT    NOT NULL,
    event_id   INTEGER,
    payload    TEXT    DEFAULT '{}',
    created_at TEXT    NOT NULL DEFAULT (datetime('now','utc')),
    processed  INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_web_actions_pending ON web_actions(processed, created_at);

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
            # Blizzard API enrichment columns on characters
            "ALTER TABLE characters ADD COLUMN race       TEXT",
            "ALTER TABLE characters ADD COLUMN realm      TEXT",
            "ALTER TABLE characters ADD COLUMN region     TEXT",
            "ALTER TABLE characters ADD COLUMN avatar_url TEXT",
            "ALTER TABLE characters ADD COLUMN faction    TEXT",
            # Professions and raid progression per character
            "ALTER TABLE characters ADD COLUMN professions TEXT",
            "ALTER TABLE characters ADD COLUMN progression TEXT",
            # Public roster embed tracking in guild settings
            "ALTER TABLE guild_settings ADD COLUMN roster_channel_id INTEGER",
            "ALTER TABLE guild_settings ADD COLUMN roster_message_id INTEGER",
            "ALTER TABLE recurring_events ADD COLUMN last_posted_date TEXT",
            "ALTER TABLE characters ADD COLUMN raiderio_url TEXT",
            # Track Discord message IDs for posted reminder messages so old ones can be deleted
            "ALTER TABLE reminders ADD COLUMN message_id INTEGER",
            "ALTER TABLE reminders ADD COLUMN msg_channel_id INTEGER",
            # Per-event accent color (integer Discord color) so simultaneous events are visually distinct
            "ALTER TABLE events ADD COLUMN color INTEGER",
        ]
        # Idempotent CREATE for tables added after initial schema (can't use ALTER TABLE)
        new_tables = [
            """CREATE TABLE IF NOT EXISTS web_actions (
                action_id  INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id   INTEGER NOT NULL,
                action     TEXT    NOT NULL,
                event_id   INTEGER,
                payload    TEXT    DEFAULT '{}',
                created_at TEXT    NOT NULL DEFAULT (datetime('now','utc')),
                processed  INTEGER NOT NULL DEFAULT 0
            )""",
            "CREATE INDEX IF NOT EXISTS idx_web_actions_pending ON web_actions(processed, created_at)",
        ]
        for sql in new_tables:
            try:
                await db.execute(sql)
            except Exception:
                pass
        for sql in migrations:
            try:
                await db.execute(sql)
            except Exception:
                pass  # Column already exists – that's fine

        await db.commit()
    log.info("Database initialised at %s", db_path)
