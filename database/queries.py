"""
All database query functions.  Every function accepts a db_path string and
opens its own short-lived connection, ensuring thread/async safety.
"""

from __future__ import annotations

import aiosqlite
import logging
from datetime import datetime, timezone
from typing import Any, Optional

log = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _fetchone(db_path: str, sql: str, params: tuple = ()) -> Optional[dict]:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(sql, params) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def _fetchall(db_path: str, sql: str, params: tuple = ()) -> list[dict]:
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(sql, params) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def _execute(db_path: str, sql: str, params: tuple = ()) -> int:
    """Execute a statement and return lastrowid."""
    async with aiosqlite.connect(db_path) as db:
        await db.execute("PRAGMA foreign_keys=ON")
        cur = await db.execute(sql, params)
        await db.commit()
        return cur.lastrowid or 0


# ══════════════════════════════════════════════════════════════════════════════
# Guild Settings
# ══════════════════════════════════════════════════════════════════════════════

async def get_guild_settings(db_path: str, guild_id: int) -> dict:
    row = await _fetchone(
        db_path, "SELECT * FROM guild_settings WHERE guild_id=?", (guild_id,)
    )
    if not row:
        # Auto-create default settings row
        await _execute(
            db_path,
            "INSERT OR IGNORE INTO guild_settings (guild_id) VALUES (?)",
            (guild_id,),
        )
        row = await _fetchone(
            db_path, "SELECT * FROM guild_settings WHERE guild_id=?", (guild_id,)
        )
    return row or {}


async def update_guild_setting(db_path: str, guild_id: int, key: str, value: Any) -> None:
    allowed = {
        "event_channel_id", "log_channel_id", "attendance_threshold",
        "timezone", "default_max_tanks", "default_max_healers", "default_max_dps",
        "roster_channel_id", "roster_message_id",
    }
    if key not in allowed:
        raise ValueError(f"Unknown setting key: {key}")
    await _execute(
        db_path,
        f"UPDATE guild_settings SET {key}=? WHERE guild_id=?",
        (value, guild_id),
    )


# ══════════════════════════════════════════════════════════════════════════════
# Permissions
# ══════════════════════════════════════════════════════════════════════════════

async def set_permission(db_path: str, guild_id: int, discord_id: int, role: str) -> None:
    await _execute(
        db_path,
        "INSERT OR REPLACE INTO permissions (guild_id, discord_id, role) VALUES (?,?,?)",
        (guild_id, discord_id, role),
    )


async def remove_permission(db_path: str, guild_id: int, discord_id: int) -> None:
    await _execute(
        db_path,
        "DELETE FROM permissions WHERE guild_id=? AND discord_id=?",
        (guild_id, discord_id),
    )


async def get_permission(db_path: str, guild_id: int, discord_id: int) -> Optional[str]:
    row = await _fetchone(
        db_path,
        "SELECT role FROM permissions WHERE guild_id=? AND discord_id=?",
        (guild_id, discord_id),
    )
    return row["role"] if row else None


# ══════════════════════════════════════════════════════════════════════════════
# Characters
# ══════════════════════════════════════════════════════════════════════════════

async def add_character(
    db_path: str,
    discord_id: int,
    guild_id: int,
    char_name: str,
    char_class: str,
    main_spec: str,
    off_spec: Optional[str] = None,
    ilvl: Optional[int] = None,
    race: Optional[str] = None,
    realm: Optional[str] = None,
    region: Optional[str] = None,
    avatar_url: Optional[str] = None,
    faction: Optional[str] = None,
    professions: Optional[str] = None,
    progression: Optional[str] = None,
) -> None:
    # If this is the user's first character, make it their main automatically
    existing = await get_user_characters(db_path, discord_id, guild_id)
    is_main = 1 if not existing else 0
    await _execute(
        db_path,
        """INSERT INTO characters
           (discord_id, guild_id, char_name, char_class, main_spec, off_spec,
            is_main, ilvl, race, realm, region, avatar_url, faction,
            professions, progression)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (discord_id, guild_id, char_name, char_class, main_spec, off_spec,
         is_main, ilvl, race, realm, region, avatar_url, faction,
         professions, progression),
    )


async def get_user_characters(
    db_path: str, discord_id: int, guild_id: int
) -> list[dict]:
    return await _fetchall(
        db_path,
        "SELECT * FROM characters WHERE discord_id=? AND guild_id=? ORDER BY is_main DESC, char_name",
        (discord_id, guild_id),
    )


async def get_guild_characters_for_sync(db_path: str, guild_id: int) -> list[dict]:
    """Return all characters syncable with Raider.IO.

    Includes characters that have realm+region stored AND characters that
    have a raiderio_url stored (added via /char link or admin edit), since
    region/realm/name can be parsed directly from the URL for the latter.
    """
    return await _fetchall(
        db_path,
        "SELECT discord_id, char_name, realm, region, raiderio_url FROM characters "
        "WHERE guild_id=? AND (realm IS NOT NULL AND region IS NOT NULL OR raiderio_url IS NOT NULL) "
        "ORDER BY char_name",
        (guild_id,),
    )


async def get_all_guild_characters(db_path: str, guild_id: int) -> list[dict]:
    """Return all characters registered in a guild, sorted by class then name."""
    return await _fetchall(
        db_path,
        "SELECT * FROM characters WHERE guild_id=? ORDER BY char_class, char_name",
        (guild_id,),
    )


async def get_guild_character_by_name(
    db_path: str, guild_id: int, char_name: str
) -> Optional[dict]:
    """Find any character in a guild by name (case-insensitive), regardless of owner."""
    return await _fetchone(
        db_path,
        "SELECT * FROM characters WHERE guild_id=? AND LOWER(char_name)=LOWER(?)",
        (guild_id, char_name),
    )


async def get_character(
    db_path: str, discord_id: int, guild_id: int, char_name: str
) -> Optional[dict]:
    return await _fetchone(
        db_path,
        "SELECT * FROM characters WHERE discord_id=? AND guild_id=? AND LOWER(char_name)=LOWER(?)",
        (discord_id, guild_id, char_name),
    )


async def get_main_character(
    db_path: str, discord_id: int, guild_id: int
) -> Optional[dict]:
    return await _fetchone(
        db_path,
        "SELECT * FROM characters WHERE discord_id=? AND guild_id=? AND is_main=1",
        (discord_id, guild_id),
    )


async def set_main_character(
    db_path: str, discord_id: int, guild_id: int, char_name: str
) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute("PRAGMA foreign_keys=ON")
        await db.execute(
            "UPDATE characters SET is_main=0 WHERE discord_id=? AND guild_id=?",
            (discord_id, guild_id),
        )
        await db.execute(
            "UPDATE characters SET is_main=1 WHERE discord_id=? AND guild_id=? AND LOWER(char_name)=LOWER(?)",
            (discord_id, guild_id, char_name),
        )
        await db.commit()


async def update_character(
    db_path: str,
    discord_id: int,
    guild_id: int,
    char_name: str,
    **kwargs: Any,
) -> None:
    allowed = {"main_spec", "off_spec", "ilvl", "notes", "race", "realm", "region", "avatar_url", "faction", "professions", "progression", "raiderio_url"}
    updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
    if not updates:
        return
    set_clause = ", ".join(f"{k}=?" for k in updates)
    vals = list(updates.values()) + [discord_id, guild_id, char_name]
    await _execute(
        db_path,
        f"UPDATE characters SET {set_clause} WHERE discord_id=? AND guild_id=? AND LOWER(char_name)=LOWER(?)",
        tuple(vals),
    )


async def remove_character(
    db_path: str, discord_id: int, guild_id: int, char_name: str
) -> None:
    await _execute(
        db_path,
        "DELETE FROM characters WHERE discord_id=? AND guild_id=? AND LOWER(char_name)=LOWER(?)",
        (discord_id, guild_id, char_name),
    )


# ══════════════════════════════════════════════════════════════════════════════
# Events
# ══════════════════════════════════════════════════════════════════════════════

# Rotating palette used to assign a distinct color to each new event so that
# two simultaneous sign-up posts of the same type are visually distinguishable.
_EVENT_COLOR_PALETTE: list[int] = [
    0x3498DB,  # Blue
    0xE74C3C,  # Red
    0x2ECC71,  # Green
    0x9B59B6,  # Purple
    0xE67E22,  # Orange
    0x1ABC9C,  # Teal
    0xF1C40F,  # Gold
    0xE91E8C,  # Pink
]


async def _next_event_color(db_path: str, guild_id: int) -> int:
    """Return the next palette color for the guild, cycling through the list."""
    row = await _fetchone(
        db_path,
        "SELECT COUNT(*) as cnt FROM events WHERE guild_id=?",
        (guild_id,),
    )
    idx = (row["cnt"] if row else 0) % len(_EVENT_COLOR_PALETTE)
    return _EVENT_COLOR_PALETTE[idx]


async def create_event(
    db_path: str,
    guild_id: int,
    event_name: str,
    event_type: str,
    event_date: str,
    event_time: str,
    created_by: int,
    description: str = "",
    channel_id: Optional[int] = None,
    max_tanks: int = 2,
    max_healers: int = 5,
    max_dps: int = 13,
) -> int:
    color = await _next_event_color(db_path, guild_id)
    return await _execute(
        db_path,
        """INSERT INTO events
           (guild_id, event_name, event_type, event_date, event_time,
            description, channel_id, created_by, max_tanks, max_healers, max_dps, color)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (guild_id, event_name, event_type, event_date, event_time,
         description, channel_id, created_by, max_tanks, max_healers, max_dps, color),
    )


async def set_event_message(db_path: str, event_id: int, message_id: int, channel_id: int) -> None:
    await _execute(
        db_path,
        "UPDATE events SET message_id=?, channel_id=? WHERE event_id=?",
        (message_id, channel_id, event_id),
    )


async def get_event(db_path: str, event_id: int) -> Optional[dict]:
    return await _fetchone(
        db_path, "SELECT * FROM events WHERE event_id=?", (event_id,)
    )


async def get_upcoming_events(db_path: str, guild_id: int) -> list[dict]:
    today = datetime.now().strftime("%Y-%m-%d")
    return await _fetchall(
        db_path,
        "SELECT * FROM events WHERE guild_id=? AND status='active' AND event_date>=? ORDER BY event_date, event_time",
        (guild_id, today),
    )


async def get_all_active_events(db_path: str) -> list[dict]:
    """Return every active event across all guilds (used for view re-registration on startup)."""
    return await _fetchall(
        db_path,
        "SELECT * FROM events WHERE status='active'",
    )


async def update_event(db_path: str, event_id: int, **kwargs: Any) -> None:
    allowed = {"event_name","event_type","event_date","event_time","description",
               "max_tanks","max_healers","max_dps","locked","status"}
    updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
    if not updates:
        return
    set_clause = ", ".join(f"{k}=?" for k in updates)
    vals = list(updates.values()) + [event_id]
    await _execute(
        db_path,
        f"UPDATE events SET {set_clause} WHERE event_id=?",
        tuple(vals),
    )


async def cancel_event(db_path: str, event_id: int) -> None:
    await _execute(
        db_path, "UPDATE events SET status='cancelled' WHERE event_id=?", (event_id,)
    )


async def complete_event(db_path: str, event_id: int) -> None:
    await _execute(
        db_path, "UPDATE events SET status='completed' WHERE event_id=?", (event_id,)
    )


# ── Templates ─────────────────────────────────────────────────────────────────

async def save_template(
    db_path: str,
    guild_id: int,
    template_name: str,
    event_name: str,
    event_type: str,
    event_time: str,
    description: str,
    created_by: int,
    max_tanks: int = 2,
    max_healers: int = 5,
    max_dps: int = 13,
) -> None:
    await _execute(
        db_path,
        """INSERT OR REPLACE INTO event_templates
           (guild_id, template_name, event_name, event_type, event_time,
            description, max_tanks, max_healers, max_dps, created_by)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (guild_id, template_name, event_name, event_type, event_time,
         description, max_tanks, max_healers, max_dps, created_by),
    )


async def get_template(
    db_path: str, guild_id: int, template_name: str
) -> Optional[dict]:
    return await _fetchone(
        db_path,
        "SELECT * FROM event_templates WHERE guild_id=? AND LOWER(template_name)=LOWER(?)",
        (guild_id, template_name),
    )


async def list_templates(db_path: str, guild_id: int) -> list[dict]:
    return await _fetchall(
        db_path,
        "SELECT * FROM event_templates WHERE guild_id=? ORDER BY template_name",
        (guild_id,),
    )


async def delete_template(db_path: str, guild_id: int, template_name: str) -> None:
    await _execute(
        db_path,
        "DELETE FROM event_templates WHERE guild_id=? AND LOWER(template_name)=LOWER(?)",
        (guild_id, template_name),
    )


# ══════════════════════════════════════════════════════════════════════════════
# Signups
# ══════════════════════════════════════════════════════════════════════════════

async def add_signup(
    db_path: str,
    event_id: int,
    discord_id: int,
    char_name: str,
    char_class: str,
    main_spec: str,
    role: str,
    signup_status: str = "confirmed",
) -> int:
    return await _execute(
        db_path,
        """INSERT OR REPLACE INTO signups
           (event_id, discord_id, char_name, char_class, main_spec, role, signup_status, signup_time)
           VALUES (?,?,?,?,?,?,?,?)""",
        (event_id, discord_id, char_name, char_class, main_spec, role, signup_status, _now()),
    )


async def update_signup_status(
    db_path: str, event_id: int, discord_id: int, signup_status: str
) -> None:
    await _execute(
        db_path,
        "UPDATE signups SET signup_status=? WHERE event_id=? AND discord_id=?",
        (signup_status, event_id, discord_id),
    )


async def remove_signup(db_path: str, event_id: int, discord_id: int) -> None:
    await _execute(
        db_path,
        "DELETE FROM signups WHERE event_id=? AND discord_id=?",
        (event_id, discord_id),
    )


async def get_signup(
    db_path: str, event_id: int, discord_id: int
) -> Optional[dict]:
    return await _fetchone(
        db_path,
        "SELECT * FROM signups WHERE event_id=? AND discord_id=?",
        (event_id, discord_id),
    )


async def get_event_signups(db_path: str, event_id: int) -> list[dict]:
    return await _fetchall(
        db_path,
        "SELECT * FROM signups WHERE event_id=? ORDER BY signup_time",
        (event_id,),
    )


def categorise_signups(
    signups: list[dict],
    max_tanks: int,
    max_healers: int,
    max_dps: int,
) -> dict[str, list[dict]]:
    """
    Split a flat list of signup rows into categorised buckets:
    tanks / healers / dps / bench / tentative / declined.
    Overflow beyond role caps goes to bench in signup-time order.
    """
    buckets: dict[str, list[dict]] = {
        "tanks": [], "healers": [], "dps": [],
        "bench": [], "tentative": [], "declined": [],
    }
    for s in signups:
        status = s["signup_status"]
        if status == "declined":
            buckets["declined"].append(s)
        elif status == "tentative":
            buckets["tentative"].append(s)
        elif status == "bench":
            buckets["bench"].append(s)
        elif status == "confirmed":
            role = s["role"]
            if role == "tank" and len(buckets["tanks"]) < max_tanks:
                buckets["tanks"].append(s)
            elif role == "healer" and len(buckets["healers"]) < max_healers:
                buckets["healers"].append(s)
            elif role == "dps" and len(buckets["dps"]) < max_dps:
                buckets["dps"].append(s)
            else:
                buckets["bench"].append(s)
    return buckets


# ══════════════════════════════════════════════════════════════════════════════
# Attendance
# ══════════════════════════════════════════════════════════════════════════════

async def upsert_attendance(
    db_path: str,
    event_id: int,
    discord_id: int,
    char_name: str,
    status: str,
    marked_by: Optional[int] = None,
) -> None:
    await _execute(
        db_path,
        """INSERT INTO attendance (event_id, discord_id, char_name, status, marked_by, timestamp)
           VALUES (?,?,?,?,?,?)
           ON CONFLICT(event_id, discord_id) DO UPDATE SET status=excluded.status,
               marked_by=excluded.marked_by, timestamp=excluded.timestamp""",
        (event_id, discord_id, char_name, status, marked_by, _now()),
    )


async def get_event_attendance(db_path: str, event_id: int) -> list[dict]:
    return await _fetchall(
        db_path,
        "SELECT * FROM attendance WHERE event_id=? ORDER BY char_name",
        (event_id,),
    )


async def get_user_attendance(
    db_path: str, discord_id: int, guild_id: int, days: Optional[int] = None
) -> list[dict]:
    """Fetch attendance records for a user, optionally restricted to last N days."""
    if days:
        from datetime import timedelta
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        sql = """
            SELECT a.*, e.event_name, e.event_date FROM attendance a
            JOIN events e ON e.event_id=a.event_id
            WHERE a.discord_id=? AND e.guild_id=? AND e.event_date>=?
            ORDER BY e.event_date
        """
        return await _fetchall(db_path, sql, (discord_id, guild_id, cutoff))
    else:
        sql = """
            SELECT a.*, e.event_name, e.event_date FROM attendance a
            JOIN events e ON e.event_id=a.event_id
            WHERE a.discord_id=? AND e.guild_id=?
            ORDER BY e.event_date
        """
        return await _fetchall(db_path, sql, (discord_id, guild_id))


def compute_attendance_stats(records: list[dict]) -> dict:
    """Calculate attendance statistics from a list of attendance rows."""
    total    = len(records)
    present  = sum(1 for r in records if r["status"] in ("present", "late"))
    late     = sum(1 for r in records if r["status"] == "late")
    excused  = sum(1 for r in records if r["status"] == "excused")
    absent   = sum(1 for r in records if r["status"] == "absent")
    unexcused = absent

    denominator = total - excused
    pct = (present / denominator * 100) if denominator > 0 else 0.0

    return {
        "total":        total,
        "attended":     present,
        "late":         late,
        "excused":      excused,
        "unexcused":    unexcused,
        "pct_all_time": round(pct, 1),
    }


async def get_low_attendance_members(
    db_path: str, guild_id: int, threshold: int
) -> list[dict]:
    """Return users with all-time attendance below threshold%."""
    sql = """
        SELECT a.discord_id,
               COUNT(*) AS total,
               SUM(CASE WHEN a.status IN ('present','late') THEN 1 ELSE 0 END) AS attended,
               SUM(CASE WHEN a.status='excused' THEN 1 ELSE 0 END) AS excused
        FROM attendance a
        JOIN events e ON e.event_id=a.event_id
        WHERE e.guild_id=?
        GROUP BY a.discord_id
        HAVING (attended * 100.0 / NULLIF(total - excused, 0)) < ?
    """
    return await _fetchall(db_path, sql, (guild_id, threshold))


# ══════════════════════════════════════════════════════════════════════════════
# Absences
# ══════════════════════════════════════════════════════════════════════════════

async def add_absence(
    db_path: str,
    discord_id: int,
    guild_id: int,
    event_id: Optional[int],
    reason: str,
) -> None:
    await _execute(
        db_path,
        """INSERT INTO absences (discord_id, guild_id, event_id, reason, submitted_at)
           VALUES (?,?,?,?,?)""",
        (discord_id, guild_id, event_id, reason, _now()),
    )


async def get_user_absences(
    db_path: str, discord_id: int, guild_id: int
) -> list[dict]:
    sql = """
        SELECT ab.*, e.event_name, e.event_date FROM absences ab
        LEFT JOIN events e ON e.event_id=ab.event_id
        WHERE ab.discord_id=? AND ab.guild_id=?
        ORDER BY ab.submitted_at DESC
        LIMIT 20
    """
    return await _fetchall(db_path, sql, (discord_id, guild_id))


async def get_event_absences(db_path: str, event_id: int) -> list[dict]:
    return await _fetchall(
        db_path,
        "SELECT * FROM absences WHERE event_id=? ORDER BY submitted_at",
        (event_id,),
    )


# ══════════════════════════════════════════════════════════════════════════════
# Reminders
# ══════════════════════════════════════════════════════════════════════════════

async def schedule_reminders(
    db_path: str, event_id: int, fire_times: list[tuple[str, str]]
) -> None:
    """Insert reminder rows.  fire_times is list of (ISO datetime str, label)."""
    async with aiosqlite.connect(db_path) as db:
        await db.executemany(
            "INSERT INTO reminders (event_id, fire_at, label) VALUES (?,?,?)",
            [(event_id, ft, label) for ft, label in fire_times],
        )
        await db.commit()


async def get_pending_reminders(db_path: str) -> list[dict]:
    now = _now()
    return await _fetchall(
        db_path,
        "SELECT * FROM reminders WHERE sent=0 AND fire_at<=? ORDER BY fire_at",
        (now,),
    )


async def mark_reminder_sent(db_path: str, reminder_id: int) -> None:
    await _execute(
        db_path, "UPDATE reminders SET sent=1 WHERE reminder_id=?", (reminder_id,)
    )


async def set_reminder_message(
    db_path: str, reminder_id: int, message_id: int, channel_id: int
) -> None:
    """Store the Discord message ID of a posted reminder so it can be deleted later."""
    await _execute(
        db_path,
        "UPDATE reminders SET message_id=?, msg_channel_id=? WHERE reminder_id=?",
        (message_id, channel_id, reminder_id),
    )


async def get_sent_reminder_messages(db_path: str, event_id: int) -> list[dict]:
    """Return all previously sent reminder rows for an event that have a stored message_id."""
    return await _fetchall(
        db_path,
        "SELECT reminder_id, message_id, msg_channel_id FROM reminders WHERE event_id=? AND sent=1 AND message_id IS NOT NULL",
        (event_id,),
    )


async def delete_unsent_reminders(db_path: str, event_id: int) -> None:
    """Delete all unsent reminders for an event (used when rescheduling)."""
    await _execute(
        db_path, "DELETE FROM reminders WHERE event_id=? AND sent=0", (event_id,)
    )


# ══════════════════════════════════════════════════════════════════════════════
# Event Channels
# ══════════════════════════════════════════════════════════════════════════════

async def add_event_channel(
    db_path: str, guild_id: int, channel_id: int, label: str = ""
) -> None:
    await _execute(
        db_path,
        "INSERT OR REPLACE INTO event_channels (guild_id, channel_id, label) VALUES (?,?,?)",
        (guild_id, channel_id, label),
    )


async def remove_event_channel(db_path: str, guild_id: int, channel_id: int) -> None:
    await _execute(
        db_path,
        "DELETE FROM event_channels WHERE guild_id=? AND channel_id=?",
        (guild_id, channel_id),
    )


async def get_event_channels(db_path: str, guild_id: int) -> list[dict]:
    """Return all registered event channels for the guild, ordered by label."""
    return await _fetchall(
        db_path,
        "SELECT channel_id, label FROM event_channels WHERE guild_id=? ORDER BY label, channel_id",
        (guild_id,),
    )


# ══════════════════════════════════════════════════════════════════════════════
# Boss Progress
# ══════════════════════════════════════════════════════════════════════════════

async def set_event_bosses(
    db_path: str, event_id: int, raid_name: str, boss_names: list[str]
) -> None:
    """
    Replace the boss list for an event.
    Deletes any existing bosses for this event then inserts the new list.
    """
    async with aiosqlite.connect(db_path) as db:
        await db.execute("PRAGMA foreign_keys=ON")
        await db.execute("DELETE FROM event_bosses WHERE event_id=?", (event_id,))
        await db.executemany(
            "INSERT INTO event_bosses (event_id, raid_name, boss_name, sort_order) VALUES (?,?,?,?)",
            [(event_id, raid_name, name, i) for i, name in enumerate(boss_names)],
        )
        await db.commit()


async def get_event_bosses(db_path: str, event_id: int) -> list[dict]:
    """Return all boss rows for an event in encounter order."""
    return await _fetchall(
        db_path,
        "SELECT * FROM event_bosses WHERE event_id=? ORDER BY sort_order",
        (event_id,),
    )


async def mark_boss(
    db_path: str,
    event_id: int,
    boss_name: str,
    defeated: bool,
    marked_by: Optional[int] = None,
) -> None:
    """Toggle a single boss's defeated status."""
    defeated_at = _now() if defeated else None
    await _execute(
        db_path,
        """UPDATE event_bosses
           SET defeated=?, defeated_at=?, marked_by=?
           WHERE event_id=? AND LOWER(boss_name)=LOWER(?)""",
        (1 if defeated else 0, defeated_at, marked_by, event_id, boss_name),
    )


async def clear_boss_progress(db_path: str, event_id: int) -> None:
    """Reset all bosses for an event back to alive."""
    await _execute(
        db_path,
        "UPDATE event_bosses SET defeated=0, defeated_at=NULL, marked_by=NULL WHERE event_id=?",
        (event_id,),
    )


# ── Scheduled deletions ───────────────────────────────────────────────────────

async def add_scheduled_deletion(
    db_path: str, channel_id: int, message_id: int, delete_at: str
) -> None:
    """Persist a message to be deleted at delete_at (ISO-8601 UTC)."""
    await _execute(
        db_path,
        "INSERT INTO scheduled_deletions (channel_id, message_id, delete_at) VALUES (?, ?, ?)",
        (channel_id, message_id, delete_at),
    )


async def get_due_deletions(db_path: str) -> list[dict]:
    """Return all scheduled deletions whose delete_at time has passed."""
    return await _fetchall(
        db_path,
        "SELECT * FROM scheduled_deletions WHERE delete_at <= ?",
        (_now(),),
    )


async def remove_scheduled_deletion(db_path: str, deletion_id: int) -> None:
    """Remove a completed (or failed) scheduled deletion record."""
    await _execute(
        db_path,
        "DELETE FROM scheduled_deletions WHERE deletion_id = ?",
        (deletion_id,),
    )


# ══════════════════════════════════════════════════════════════════════════════
# Recurring Events
# ══════════════════════════════════════════════════════════════════════════════

async def add_recurring_event(
    db_path: str,
    guild_id: int,
    template_name: str,
    day_of_week: int,
    created_by: int,
    channel_id: Optional[int] = None,
    days_advance: int = 7,
) -> int:
    return await _execute(
        db_path,
        """INSERT INTO recurring_events
           (guild_id, template_name, day_of_week, channel_id, days_advance, created_by)
           VALUES (?,?,?,?,?,?)""",
        (guild_id, template_name, day_of_week, channel_id, days_advance, created_by),
    )


async def get_recurring_events(db_path: str, guild_id: int) -> list[dict]:
    return await _fetchall(
        db_path,
        "SELECT * FROM recurring_events WHERE guild_id=? ORDER BY recurring_id",
        (guild_id,),
    )


async def get_all_recurring_events(db_path: str) -> list[dict]:
    """Return every enabled recurring event across all guilds (used by background loop)."""
    return await _fetchall(
        db_path,
        "SELECT * FROM recurring_events WHERE enabled=1",
    )


async def update_recurring_last_posted(db_path: str, recurring_id: int, date_str: str) -> None:
    await _execute(
        db_path,
        "UPDATE recurring_events SET last_posted_date=? WHERE recurring_id=?",
        (date_str, recurring_id),
    )


async def toggle_recurring_event(db_path: str, recurring_id: int, enabled: bool) -> None:
    await _execute(
        db_path,
        "UPDATE recurring_events SET enabled=? WHERE recurring_id=?",
        (1 if enabled else 0, recurring_id),
    )


async def remove_recurring_event(db_path: str, guild_id: int, recurring_id: int) -> None:
    await _execute(
        db_path,
        "DELETE FROM recurring_events WHERE recurring_id=? AND guild_id=?",
        (recurring_id, guild_id),
    )


async def set_boss_embed(
    db_path: str, event_id: int, message_id: int, channel_id: int
) -> None:
    """Store the message ID of the live boss-progress embed."""
    await _execute(
        db_path,
        "UPDATE events SET boss_message_id=?, boss_channel_id=? WHERE event_id=?",
        (message_id, channel_id, event_id),
    )


# ══════════════════════════════════════════════════════════════════════════════
# Web → Discord action queue
# ══════════════════════════════════════════════════════════════════════════════

async def get_pending_web_actions(db_path: str) -> list[dict]:
    """Return unprocessed web_actions ordered by creation time."""
    return await _fetchall(
        db_path,
        "SELECT * FROM web_actions WHERE processed=0 ORDER BY created_at ASC",
    )


async def mark_web_action_processed(db_path: str, action_id: int) -> None:
    await _execute(
        db_path,
        "UPDATE web_actions SET processed=1 WHERE action_id=?",
        (action_id,),
    )
