from fastapi import APIRouter, HTTPException, Depends, Query
from database.connection import get_db
from database.queries import get_active_events, get_event, get_event_signups
from middleware.auth import get_current_user

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("")
async def list_events(
    limit: int = Query(20, ge=1, le=100),
    user: dict = Depends(get_current_user),
):
    guild_id = int(user["guild_id"])
    events = await get_active_events(guild_id, limit)
    return events


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
        elif status == "bench":
            roster["bench"].append(s)
        elif status == "tentative":
            roster["tentative"].append(s)
        elif status == "declined":
            roster["declined"].append(s)
    return roster
