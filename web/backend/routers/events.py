import json
import aiohttp
from fastapi import APIRouter, HTTPException, Depends, Query
from database.connection import get_db
from database.queries import get_active_events, get_event, get_event_signups, get_guild_settings, queue_web_action
from middleware.auth import get_current_user, require_raid_leader
from models.schemas import EventCreate, EventUpdate, EventCancel
import config as web_config

router = APIRouter(prefix="/api/events", tags=["events"])


# ── Read endpoints (all authenticated members) ────────────────────────────────

@router.get("")
async def list_events(
    limit: int = Query(20, ge=1, le=100),
    user: dict = Depends(get_current_user),
):
    guild_id = int(user["guild_id"])
    return await get_active_events(guild_id, limit)


@router.get("/channels")
async def list_event_channels(user: dict = Depends(get_current_user)):
    """Return the guild's configured event channels for the channel picker."""
    guild_id = int(user["guild_id"])
    async with get_db() as db:
        cur = await db.execute(
            "SELECT channel_id, label FROM event_channels WHERE guild_id=? ORDER BY label ASC",
            (guild_id,),
        )
        rows = await cur.fetchall()
        channels = [{**dict(r), "channel_id": str(r["channel_id"])} for r in rows]
    # Also include the guild default if set and not already listed
    settings = await get_guild_settings(guild_id)
    default_id = str(settings.get("event_channel_id")) if settings else None
    if default_id and not any(c["channel_id"] == default_id for c in channels):
        channels.insert(0, {"channel_id": default_id, "label": "Guild Default"})
    return channels


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

    # Fill unset slot caps and channel from guild defaults
    settings = await get_guild_settings(guild_id)
    max_tanks   = body.max_tanks   if body.max_tanks   is not None else (settings["default_max_tanks"]   if settings else 2)
    max_healers = body.max_healers if body.max_healers is not None else (settings["default_max_healers"] if settings else 5)
    max_dps     = body.max_dps     if body.max_dps     is not None else (settings["default_max_dps"]     if settings else 13)
    channel_id = settings.get("event_channel_id") if settings else body.channel_id

    async with get_db() as db:
        cur = await db.execute(
            """INSERT INTO events
               (guild_id, event_name, event_type, event_date, event_time,
                description, channel_id, created_by, max_tanks, max_healers, max_dps, status)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,'active')""",
            (guild_id, body.event_name, body.event_type, body.event_date,
             body.event_time, body.description, channel_id, created_by,
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


# ── Direct Discord post (bypasses bot polling) ────────────────────────────────

SOCIAL_EVENT_TYPES = {"Social Event", "Achievement Run", "PvP - RBG", "PvP - Arena", "Mythic+ Night"}
DISCORD_API = "https://discord.com/api/v10"


def _build_discord_payload(event: dict, signups: list[dict]) -> dict:
    """Build the Discord message payload (embed + buttons) matching the bot's format."""
    eid = event["event_id"]
    color = event.get("color") or 0x3498DB

    tanks   = [s for s in signups if s["role"] == "tank"   and s["signup_status"] == "confirmed"]
    healers = [s for s in signups if s["role"] == "healer" and s["signup_status"] == "confirmed"]
    dps     = [s for s in signups if s["role"] == "dps"    and s["signup_status"] == "confirmed"]
    bench   = [s for s in signups if s["signup_status"] == "bench"]
    tent    = [s for s in signups if s["signup_status"] == "tentative"]

    def names(lst: list) -> str:
        if not lst:
            return "_None_"
        lines = []
        for i, p in enumerate(lst):
            pfx = "└─" if i == len(lst) - 1 else "├─"
            lines.append(f"{pfx} **{p['char_name']}** ({p['char_class']} – {p['main_spec']})")
        return "\n".join(lines)

    is_social = event.get("event_type") in SOCIAL_EVENT_TYPES
    locked = bool(event.get("locked"))
    lock_tag = " 🔒 LOCKED" if locked else ""

    fields = [
        {"name": "🕐  Date & Time", "value": f"{event['event_date']}  @  {event['event_time']}", "inline": True},
        {"name": "🗂️  Type",        "value": event["event_type"],                                  "inline": True},
    ]
    if event.get("description"):
        fields.append({"name": "📝  Description", "value": event["description"], "inline": False})
    fields.append({"name": "\u200b", "value": "─" * 36, "inline": False})

    if is_social:
        attending = tanks + healers + dps
        fields += [
            {"name": f"✅ Attending ({len(attending)})", "value": "\n".join(f"├─ **{p['char_name']}**" for p in attending) or "_None_", "inline": False},
        ]
        if tent:
            fields.append({"name": f"❓ Tentative ({len(tent)})", "value": "\n".join(f"├─ **{p['char_name']}**" for p in tent), "inline": False})
        buttons = [
            {"type": 2, "style": 3, "label": "Attending ✅",     "custom_id": f"social_{eid}_attending"},
            {"type": 2, "style": 2, "label": "Tentative ❓",     "custom_id": f"social_{eid}_tentative"},
            {"type": 2, "style": 4, "label": "Not Attending ❌", "custom_id": f"social_{eid}_decline"},
        ]
    else:
        fields += [
            {"name": f"🛡️ Tanks ({len(tanks)}/{event['max_tanks']})",     "value": names(tanks),   "inline": True},
            {"name": f"💚 Healers ({len(healers)}/{event['max_healers']})", "value": names(healers), "inline": True},
            {"name": f"⚔️ DPS ({len(dps)}/{event['max_dps']})",            "value": names(dps),     "inline": True},
        ]
        if bench:
            fields.append({"name": f"💺 Bench ({len(bench)})", "value": "\n".join(f"├─ **{p['char_name']}**" for p in bench), "inline": False})
        if tent:
            fields.append({"name": f"❓ Tentative ({len(tent)})", "value": "\n".join(f"├─ **{p['char_name']}**" for p in tent), "inline": False})
        buttons = [
            {"type": 2, "style": 1, "label": "Tank 🛡️",      "custom_id": f"signup_{eid}_tank"},
            {"type": 2, "style": 3, "label": "Healer 💚",    "custom_id": f"signup_{eid}_healer"},
            {"type": 2, "style": 2, "label": "DPS ⚔️",       "custom_id": f"signup_{eid}_dps"},
            {"type": 2, "style": 2, "label": "Tentative ❓", "custom_id": f"signup_{eid}_tentative"},
            {"type": 2, "style": 4, "label": "Decline ❌",   "custom_id": f"signup_{eid}_decline"},
        ]

    return {
        "embeds": [{"title": f"📅  {event['event_name']}{lock_tag}", "color": color, "fields": fields}],
        "components": [{"type": 1, "components": buttons}],
    }


@router.post("/{event_id}/post-discord")
async def post_event_to_discord(event_id: int, user: dict = Depends(require_raid_leader)):
    """
    Post (or re-post) the event embed directly to Discord via the REST API.
    Uses the bot token so it works independently of whether the bot is polling.
    If the event already has a Discord message, edits it in place.
    """
    guild_id = int(user["guild_id"])
    event = await get_event(event_id, guild_id)
    if not event:
        raise HTTPException(404, "Event not found")

    channel_id = event.get("channel_id")
    if not channel_id:
        settings = await get_guild_settings(guild_id)
        channel_id = settings.get("event_channel_id") if settings else None
    if not channel_id:
        raise HTTPException(400, "No Discord channel configured for this event. Edit the event and set a channel first.")

    token = web_config.DISCORD_BOT_TOKEN
    if not token:
        raise HTTPException(500, "DISCORD_TOKEN not configured in web backend environment")

    signups = await get_event_signups(event_id)
    payload = _build_discord_payload(event, signups)
    headers = {"Authorization": f"Bot {token}", "Content-Type": "application/json"}

    existing_message_id = event.get("message_id")

    async with aiohttp.ClientSession() as session:
        if existing_message_id:
            # Edit the existing message
            url = f"{DISCORD_API}/channels/{channel_id}/messages/{existing_message_id}"
            async with session.patch(url, json=payload, headers=headers) as resp:
                if resp.status == 404:
                    # Message was deleted — fall through to post a new one
                    existing_message_id = None
                elif resp.status not in (200, 204):
                    body = await resp.text()
                    raise HTTPException(502, f"Discord API error {resp.status}: {body}")
                else:
                    return {"message": "Discord embed updated", "message_id": existing_message_id, "channel_id": channel_id}

        if not existing_message_id:
            # Post a new message
            url = f"{DISCORD_API}/channels/{channel_id}/messages"
            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status not in (200, 201):
                    body = await resp.text()
                    raise HTTPException(502, f"Discord API error {resp.status}: {body}")
                data = await resp.json()
                new_message_id = int(data["id"])

    # Store message_id + channel_id back to the event row
    async with get_db() as db:
        await db.execute(
            "UPDATE events SET message_id=?, channel_id=? WHERE event_id=? AND guild_id=?",
            (new_message_id, channel_id, event_id, guild_id),
        )
        await db.commit()

    return {"message": "Event posted to Discord", "message_id": new_message_id, "channel_id": channel_id}
