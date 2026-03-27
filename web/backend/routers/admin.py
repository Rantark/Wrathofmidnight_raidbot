from fastapi import APIRouter, HTTPException, Depends
from database.connection import get_db
from database.queries import get_all_characters, get_guild_settings
from middleware.auth import require_officer
from models.schemas import CharacterAdminUpdate

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/characters")
async def all_characters(user: dict = Depends(require_officer)):
    guild_id = int(user["guild_id"])
    return await get_all_characters(guild_id)


@router.patch("/characters/{char_name}")
async def admin_edit_character(
    char_name: str,
    discord_id: int,
    body: CharacterAdminUpdate,
    user: dict = Depends(require_officer),
):
    guild_id = int(user["guild_id"])
    async with get_db() as db:
        cur = await db.execute(
            "SELECT 1 FROM characters WHERE discord_id=? AND guild_id=? AND char_name=?",
            (discord_id, guild_id, char_name),
        )
        if not await cur.fetchone():
            raise HTTPException(404, "Character not found")

        updates = {k: v for k, v in body.model_dump().items() if v is not None}
        if not updates:
            raise HTTPException(400, "No fields to update")

        set_clause = ", ".join(f"{k}=?" for k in updates)
        values = list(updates.values()) + [discord_id, guild_id, char_name]
        await db.execute(
            f"UPDATE characters SET {set_clause} WHERE discord_id=? AND guild_id=? AND char_name=?",
            values,
        )
        await db.commit()
    return {"message": "Character updated"}


@router.get("/config")
async def get_config(user: dict = Depends(require_officer)):
    guild_id = int(user["guild_id"])
    settings = await get_guild_settings(guild_id)
    if not settings:
        raise HTTPException(404, "Guild settings not found — run the bot first")
    return settings


@router.get("/stats")
async def dashboard_stats(user: dict = Depends(require_officer)):
    guild_id = int(user["guild_id"])
    async with get_db() as db:
        chars = await db.execute(
            "SELECT COUNT(*) as cnt FROM characters WHERE guild_id=?", (guild_id,)
        )
        char_row = await chars.fetchone()

        members = await db.execute(
            "SELECT COUNT(DISTINCT discord_id) as cnt FROM characters WHERE guild_id=?",
            (guild_id,),
        )
        member_row = await members.fetchone()

        events = await db.execute(
            "SELECT COUNT(*) as cnt FROM events WHERE guild_id=? AND status='active'",
            (guild_id,),
        )
        event_row = await events.fetchone()

        upcoming = await db.execute(
            """SELECT COUNT(*) as cnt FROM events
               WHERE guild_id=? AND status='active' AND event_date >= date('now')""",
            (guild_id,),
        )
        upcoming_row = await upcoming.fetchone()

    return {
        "total_characters": char_row["cnt"],
        "total_members": member_row["cnt"],
        "active_events": event_row["cnt"],
        "upcoming_events": upcoming_row["cnt"],
    }
