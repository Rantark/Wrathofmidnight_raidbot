import json
from fastapi import APIRouter, HTTPException, Depends, Query
from database.connection import get_db
from database.queries import get_active_events, get_event, get_event_signups, get_guild_settings, queue_web_action
from middleware.auth import get_current_user, require_raid_leader
from models.schemas import EventCreate, EventUpdate, EventCancel

router = APIRouter(prefix="/api/events", tags=["events"])


# ── Read endpoints (all authenticated members) ────────────────────────────────

@router.get("")
async def list_events(
    limit: int = Query(20, ge=1, le=100),
    user: dict = Depends(get_current_user),
):
    guild_id = int(user["guild_id"])
    return await get_active_events(guild_id, limit)


@router.get("/{event_id}")
async def get_event_detail(event_id: int, user: dict = Depends(get_current_user)):
    guild_id = int(user["guild_id"])
    event = await get_event(event_id, guild_id)
    if not event:
        raise HTTPException(404, "Event not found")
    signups = await get_event_signups(event_id)
    return {**event, "signups": signups}


@router.get("/{event_id}/my-status")
async def my_signup_status(event_id: int, user: dict = Depends(get_current_user)):
    discord_id = int(user["user_id"])
    guild_id = int(user["guild_id"])
    event = await get_event(event_id, guild_id)
    if not event:
        raise HTTPException(404, "Event not found")
    async with get_db() as db:
        cur = await db.execute(
            "SELECT * FROM signups WHERE event_id=? AND discord_id=?",
            (event_id, discord_id),
        )
        row = await cur.fetchone()
    return dict(row) if row else {"signup_status": "none"}


@router.get("/{event_id}/roster")
async def event_roster(event_id: int, user: dict = Depends(get_current_user)):
    guild_id = int(user["guild_id"])
    event = await get_event(event_id, guild_id)
    if not event:
        raise HTTPException(404, "Event not found")
    signups = await get_event_signups(event_id)
    roster: dict = {"tank": [], "healer": [], "dps": [], "bench": [], "tentative": [], "declined": []}
    for s in signups:
        status = s["signup_status"]
        role = s["role"]
        if status == "confirmed":
            roster[role].append(s)
        elif status in ("bench", "tentative", "declined"):
            roster[status].append(s)
    return roster


# ── Write endpoints (raid leaders and officers) ───────────────────────────────

@router.post("", status_code=201)
async def create_event(body: EventCreate, user: dict = Depends(require_raid_leader)):
    guild_id = int(user["guild_id"])
    created_by = int(user["user_id"])

    # Fill unset slot caps from guild defaults
    settings = await get_guild_settings(guild_id)
    max_tanks   = body.max_tanks   if body.max_tanks   is not None else (settings["default_max_tanks"]   if settings else 2)
    max_healers = body.max_healers if body.max_healers is not None else (settings["default_max_healers"] if settings else 5)
    max_dps     = body.max_dps     if body.max_dps     is not None else (settings["default_max_dps"]     if settings else 13)

    async with get_db() as db:
        cur = await db.execute(
            """INSERT INTO events
               (guild_id, event_name, event_type, event_date, event_time,
                description, created_by, max_tanks, max_healers, max_dps, status)
               VALUES (?,?,?,?,?,?,?,?,?,?,'active')""",
            (guild_id, body.event_name, body.event_type, body.event_date,
             body.event_time, body.description, created_by,
             max_tanks, max_healers, max_dps),
        )
        await db.commit()
        event_id = cur.lastrowid

    await queue_web_action(guild_id, "post_event", event_id)
    return {"message": "Event created", "event_id": event_id}


@router.put("/{event_id}")
async def edit_event(event_id: int, body: EventUpdate, user: dict = Depends(require_raid_leader)):
    guild_id = int(user["guild_id"])
    event = await get_event(event_id, guild_id)
    if not event:
        raise HTTPException(404, "Event not found")
    if event["status"] != "active":
        raise HTTPException(400, "Cannot edit a cancelled or completed event")

    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(400, "No fields to update")

    set_clause = ", ".join(f"{k}=?" for k in updates)
    values = list(updates.values()) + [event_id, guild_id]
    async with get_db() as db:
        await db.execute(
            f"UPDATE events SET {set_clause} WHERE event_id=? AND guild_id=?",
            values,
        )
        await db.commit()

    await queue_web_action(guild_id, "update_event", event_id)
    return {"message": "Event updated"}


@router.delete("/{event_id}", status_code=204)
async def delete_event(event_id: int, user: dict = Depends(require_raid_leader)):
    guild_id = int(user["guild_id"])
    event = await get_event(event_id, guild_id)
    if not event:
        raise HTTPException(404, "Event not found")

    # Queue Discord deletion BEFORE removing the row (we need channel/message IDs)
    payload = json.dumps({
        "channel_id": event.get("channel_id"),
        "message_id": event.get("message_id"),
    })
    await queue_web_action(guild_id, "delete_event", event_id, payload)

    async with get_db() as db:
        await db.execute(
            "DELETE FROM events WHERE event_id=? AND guild_id=?",
            (event_id, guild_id),
        )
        await db.commit()


@router.post("/{event_id}/lock")
async def toggle_lock(event_id: int, user: dict = Depends(require_raid_leader)):
    guild_id = int(user["guild_id"])
    event = await get_event(event_id, guild_id)
    if not event:
        raise HTTPException(404, "Event not found")
    if event["status"] != "active":
        raise HTTPException(400, "Event is not active")

    new_lock = 0 if event["locked"] else 1
    async with get_db() as db:
        await db.execute(
            "UPDATE events SET locked=? WHERE event_id=? AND guild_id=?",
            (new_lock, event_id, guild_id),
        )
        await db.commit()

    await queue_web_action(guild_id, "update_event", event_id)
    return {"message": "Roster unlocked" if new_lock == 0 else "Roster locked", "locked": new_lock}


@router.post("/{event_id}/cancel")
async def cancel_event(event_id: int, body: EventCancel, user: dict = Depends(require_raid_leader)):
    guild_id = int(user["guild_id"])
    event = await get_event(event_id, guild_id)
    if not event:
        raise HTTPException(404, "Event not found")
    if event["status"] != "active":
        raise HTTPException(400, "Event is not active")

    # Append reason to description if provided
    desc = event.get("description") or ""
    if body.reason:
        desc = f"[CANCELLED: {body.reason}]{(' — ' + desc) if desc else ''}"

    async with get_db() as db:
        await db.execute(
            "UPDATE events SET status='cancelled', description=? WHERE event_id=? AND guild_id=?",
            (desc, event_id, guild_id),
        )
        await db.commit()

    await queue_web_action(
        guild_id, "cancel_event", event_id,
        json.dumps({"reason": body.reason or ""}),
    )
    return {"message": "Event cancelled"}
