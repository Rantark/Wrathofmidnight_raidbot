"""Reusable query helpers used across routers."""
from typing import Optional
from database.connection import get_db


async def get_user_role(guild_id: int, discord_id: int) -> str:
    """Return 'officer', 'raid_leader', or 'member'."""
    async with get_db() as db:
        cur = await db.execute(
            "SELECT role FROM permissions WHERE guild_id=? AND discord_id=?",
            (guild_id, discord_id),
        )
        row = await cur.fetchone()
        return row["role"] if row else "member"


async def get_guild_settings(guild_id: int) -> Optional[dict]:
    async with get_db() as db:
        cur = await db.execute(
            "SELECT * FROM guild_settings WHERE guild_id=?", (guild_id,)
        )
        row = await cur.fetchone()
        return dict(row) if row else None


async def get_active_events(guild_id: int, limit: int = 20) -> list[dict]:
    async with get_db() as db:
        cur = await db.execute(
            """SELECT * FROM events
               WHERE guild_id=? AND status='active'
               ORDER BY event_date ASC, event_time ASC
               LIMIT ?""",
            (guild_id, limit),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def get_event(event_id: int, guild_id: int) -> Optional[dict]:
    async with get_db() as db:
        cur = await db.execute(
            "SELECT * FROM events WHERE event_id=? AND guild_id=?",
            (event_id, guild_id),
        )
        row = await cur.fetchone()
        return dict(row) if row else None


async def get_event_signups(event_id: int) -> list[dict]:
    async with get_db() as db:
        cur = await db.execute(
            "SELECT * FROM signups WHERE event_id=? ORDER BY signup_time ASC",
            (event_id,),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def get_user_characters(discord_id: int, guild_id: int) -> list[dict]:
    async with get_db() as db:
        cur = await db.execute(
            """SELECT * FROM characters
               WHERE discord_id=? AND guild_id=?
               ORDER BY is_main DESC, char_name ASC""",
            (discord_id, guild_id),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def get_all_characters(guild_id: int) -> list[dict]:
    async with get_db() as db:
        cur = await db.execute(
            """SELECT * FROM characters
               WHERE guild_id=?
               ORDER BY char_class ASC, is_main DESC, char_name ASC""",
            (guild_id,),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def get_attendance_stats(discord_id: int, guild_id: int) -> dict:
    """Compute attendance stats for a user across all events in this guild."""
    async with get_db() as db:
        cur = await db.execute(
            """SELECT a.status
               FROM attendance a
               JOIN events e ON e.event_id = a.event_id
               WHERE a.discord_id=? AND e.guild_id=?""",
            (discord_id, guild_id),
        )
        rows = await cur.fetchall()
    statuses = [r["status"] for r in rows]
    total = len(statuses)
    present = statuses.count("present")
    late = statuses.count("late")
    excused = statuses.count("excused")
    absent = statuses.count("absent")
    eligible = total - excused
    percentage = round((present + late) / eligible * 100) if eligible > 0 else 100
    return {
        "total": total,
        "present": present,
        "late": late,
        "excused": excused,
        "absent": absent,
        "percentage": percentage,
    }


async def queue_web_action(guild_id: int, action: str, event_id: int | None = None, payload: str = "{}") -> None:
    """Insert a pending action for the Discord bot to pick up and execute."""
    async with get_db() as db:
        await db.execute(
            "INSERT INTO web_actions (guild_id, action, event_id, payload) VALUES (?,?,?,?)",
            (guild_id, action, event_id, payload),
        )
        await db.commit()


async def get_attendance_history(discord_id: int, guild_id: int, limit: int = 20) -> list[dict]:
    async with get_db() as db:
        cur = await db.execute(
            """SELECT a.status, a.timestamp, e.event_name, e.event_date, e.event_type, e.event_id
               FROM attendance a
               JOIN events e ON e.event_id = a.event_id
               WHERE a.discord_id=? AND e.guild_id=?
               ORDER BY e.event_date DESC, e.event_time DESC
               LIMIT ?""",
            (discord_id, guild_id, limit),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]
