from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends
from database.connection import get_db
from database.queries import get_attendance_stats, get_attendance_history, get_event
from middleware.auth import get_current_user, require_raid_leader, require_officer
from models.schemas import AttendanceMarkRequest, AbsenceCreate

router = APIRouter(prefix="/api", tags=["attendance"])


# ── Personal attendance ───────────────────────────────────────────────────────

@router.get("/attendance/me")
async def my_stats(user: dict = Depends(get_current_user)):
    discord_id = int(user["user_id"])
    guild_id = int(user["guild_id"])
    return await get_attendance_stats(discord_id, guild_id)


@router.get("/attendance/me/history")
async def my_history(user: dict = Depends(get_current_user)):
    discord_id = int(user["user_id"])
    guild_id = int(user["guild_id"])
    return await get_attendance_history(discord_id, guild_id)


# ── Absence requests ──────────────────────────────────────────────────────────

@router.post("/absences", status_code=201)
async def submit_absence(body: AbsenceCreate, user: dict = Depends(get_current_user)):
    discord_id = int(user["user_id"])
    guild_id = int(user["guild_id"])

    event = await get_event(body.event_id, guild_id)
    if not event:
        raise HTTPException(404, "Event not found")
    if event["status"] != "active":
        raise HTTPException(400, "Event is no longer active")

    async with get_db() as db:
        await db.execute(
            """INSERT INTO absences (discord_id, guild_id, event_id, reason, submitted_at)
               VALUES (?,?,?,?,?)""",
            (discord_id, guild_id, body.event_id, body.reason,
             datetime.now(timezone.utc).isoformat()),
        )
        await db.commit()

    return {"message": "Absence submitted"}


@router.get("/absences/me")
async def my_absences(user: dict = Depends(get_current_user)):
    discord_id = int(user["user_id"])
    guild_id = int(user["guild_id"])
    async with get_db() as db:
        cur = await db.execute(
            """SELECT a.*, e.event_name, e.event_date
               FROM absences a
               LEFT JOIN events e ON e.event_id = a.event_id
               WHERE a.discord_id=? AND a.guild_id=?
               ORDER BY a.submitted_at DESC LIMIT 20""",
            (discord_id, guild_id),
        )
        rows = await cur.fetchall()
    return [dict(r) for r in rows]


# ── Raid-leader: mark attendance ─────────────────────────────────────────────

@router.post("/attendance/mark")
async def mark_attendance(body: AttendanceMarkRequest, user: dict = Depends(require_raid_leader)):
    guild_id = int(user["guild_id"])
    marked_by = int(user["user_id"])

    event = await get_event(body.event_id, guild_id)
    if not event:
        raise HTTPException(404, "Event not found")

    now = datetime.now(timezone.utc).isoformat()
    async with get_db() as db:
        for record in body.records:
            await db.execute(
                """INSERT INTO attendance (event_id, discord_id, char_name, status, marked_by, timestamp)
                   VALUES (?,?,?,?,?,?)
                   ON CONFLICT(event_id, discord_id) DO UPDATE SET
                   status=excluded.status, marked_by=excluded.marked_by, timestamp=excluded.timestamp""",
                (body.event_id, int(record.discord_id), "", record.status, marked_by, now),
            )
        await db.commit()

    return {"message": f"Marked {len(body.records)} attendance records"}


# ── Officer: reports ──────────────────────────────────────────────────────────

@router.get("/attendance/report")
async def low_attendance_report(user: dict = Depends(require_officer)):
    guild_id = int(user["guild_id"])
    async with get_db() as db:
        cur = await db.execute(
            "SELECT attendance_threshold FROM guild_settings WHERE guild_id=?",
            (guild_id,),
        )
        row = await cur.fetchone()
        threshold = row["attendance_threshold"] if row else 75

        # Get all unique members who have any attendance record in this guild
        cur2 = await db.execute(
            """SELECT DISTINCT a.discord_id
               FROM attendance a
               JOIN events e ON e.event_id = a.event_id
               WHERE e.guild_id=?""",
            (guild_id,),
        )
        member_rows = await cur2.fetchall()

    results = []
    for mr in member_rows:
        stats = await get_attendance_stats(mr["discord_id"], guild_id)
        if stats["percentage"] < threshold:
            results.append({"discord_id": str(mr["discord_id"]), **stats})

    results.sort(key=lambda x: x["percentage"])
    return {"threshold": threshold, "members": results}


@router.get("/attendance/event/{event_id}")
async def event_attendance(event_id: int, user: dict = Depends(require_raid_leader)):
    guild_id = int(user["guild_id"])
    event = await get_event(event_id, guild_id)
    if not event:
        raise HTTPException(404, "Event not found")

    async with get_db() as db:
        cur = await db.execute(
            "SELECT * FROM attendance WHERE event_id=? ORDER BY status ASC",
            (event_id,),
        )
        rows = await cur.fetchall()
    return [dict(r) for r in rows]
