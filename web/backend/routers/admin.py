from fastapi import APIRouter, HTTPException, Depends
from database.connection import get_db
from database.queries import get_all_characters, get_guild_settings
from middleware.auth import require_officer
from models.schemas import CharacterAdminUpdate, PermissionGrant, GuildConfigUpdate

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ── Characters ────────────────────────────────────────────────────────────────

@router.get("/characters")
async def all_characters(user: dict = Depends(require_officer)):
    return await get_all_characters(int(user["guild_id"]))


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


# ── Stats ─────────────────────────────────────────────────────────────────────

@router.get("/stats")
async def dashboard_stats(user: dict = Depends(require_officer)):
    guild_id = int(user["guild_id"])
    async with get_db() as db:
        char_row   = await (await db.execute("SELECT COUNT(*) as cnt FROM characters WHERE guild_id=?", (guild_id,))).fetchone()
        member_row = await (await db.execute("SELECT COUNT(DISTINCT discord_id) as cnt FROM characters WHERE guild_id=?", (guild_id,))).fetchone()
        event_row  = await (await db.execute("SELECT COUNT(*) as cnt FROM events WHERE guild_id=? AND status='active'", (guild_id,))).fetchone()
        upcoming   = await (await db.execute(
            "SELECT COUNT(*) as cnt FROM events WHERE guild_id=? AND status='active' AND event_date >= date('now')",
            (guild_id,),
        )).fetchone()
    return {
        "total_characters": char_row["cnt"],
        "total_members": member_row["cnt"],
        "active_events": event_row["cnt"],
        "upcoming_events": upcoming["cnt"],
    }


# ── Config ────────────────────────────────────────────────────────────────────

@router.get("/config")
async def get_config(user: dict = Depends(require_officer)):
    guild_id = int(user["guild_id"])
    settings = await get_guild_settings(guild_id)
    if not settings:
        raise HTTPException(404, "Guild settings not found — run the Discord bot first")
    return settings


@router.put("/config")
async def update_config(body: GuildConfigUpdate, user: dict = Depends(require_officer)):
    guild_id = int(user["guild_id"])
    settings = await get_guild_settings(guild_id)
    if not settings:
        raise HTTPException(404, "Guild settings not found — run the Discord bot first")

    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(400, "No fields to update")

    set_clause = ", ".join(f"{k}=?" for k in updates)
    values = list(updates.values()) + [guild_id]
    async with get_db() as db:
        await db.execute(
            f"UPDATE guild_settings SET {set_clause} WHERE guild_id=?",
            values,
        )
        await db.commit()
    return {"message": "Config updated"}


# ── Status overview ───────────────────────────────────────────────────────────

@router.get("/status")
async def bot_status(user: dict = Depends(require_officer)):
    guild_id = int(user["guild_id"])
    settings = await get_guild_settings(guild_id)
    async with get_db() as db:
        perm_count = await (await db.execute(
            "SELECT COUNT(*) as cnt FROM permissions WHERE guild_id=?", (guild_id,)
        )).fetchone()
        template_count = await (await db.execute(
            "SELECT COUNT(*) as cnt FROM event_templates WHERE guild_id=?", (guild_id,)
        )).fetchone()
        recurring_count = await (await db.execute(
            "SELECT COUNT(*) as cnt FROM recurring_events WHERE guild_id=? AND enabled=1", (guild_id,)
        )).fetchone()
    return {
        "guild_id": guild_id,
        "settings": settings,
        "permission_count": perm_count["cnt"],
        "template_count": template_count["cnt"],
        "recurring_count": recurring_count["cnt"],
    }


# ── Permissions ───────────────────────────────────────────────────────────────

@router.get("/permissions")
async def list_permissions(user: dict = Depends(require_officer)):
    guild_id = int(user["guild_id"])
    async with get_db() as db:
        cur = await db.execute(
            "SELECT discord_id, username, role FROM permissions WHERE guild_id=? ORDER BY role ASC, discord_id ASC",
            (guild_id,),
        )
        rows = await cur.fetchall()
    return [dict(r) for r in rows]


@router.post("/permissions", status_code=201)
async def grant_permission(body: PermissionGrant, user: dict = Depends(require_officer)):
    guild_id = int(user["guild_id"])
    try:
        discord_id = int(body.discord_id)
    except ValueError:
        raise HTTPException(400, "discord_id must be a numeric string")

    async with get_db() as db:
        await db.execute(
            """INSERT INTO permissions (guild_id, discord_id, role, username)
               VALUES (?,?,?,?)
               ON CONFLICT(guild_id, discord_id) DO UPDATE SET role=excluded.role, username=excluded.username""",
            (guild_id, discord_id, body.role, body.username or None),
        )
        await db.commit()
    return {"message": f"Granted {body.role} to {body.discord_id}"}


@router.delete("/permissions/{discord_id}", status_code=204)
async def revoke_permission(discord_id: str, user: dict = Depends(require_officer)):
    guild_id = int(user["guild_id"])
    try:
        did = int(discord_id)
    except ValueError:
        raise HTTPException(400, "discord_id must be numeric")

    async with get_db() as db:
        cur = await db.execute(
            "SELECT 1 FROM permissions WHERE guild_id=? AND discord_id=?",
            (guild_id, did),
        )
        if not await cur.fetchone():
            raise HTTPException(404, "Permission record not found")
        await db.execute(
            "DELETE FROM permissions WHERE guild_id=? AND discord_id=?",
            (guild_id, did),
        )
        await db.commit()


# ── Member audit ──────────────────────────────────────────────────────────────

@router.get("/audit")
async def member_audit(user: dict = Depends(require_officer)):
    """Return guild members who have no characters registered."""
    guild_id = int(user["guild_id"])
    async with get_db() as db:
        # Members with no characters
        cur = await db.execute(
            """SELECT gm.discord_id, gm.username, gm.display_name
               FROM guild_members gm
               WHERE gm.guild_id=? AND gm.is_bot=0
                 AND NOT EXISTS (
                   SELECT 1 FROM characters c
                   WHERE c.guild_id=gm.guild_id AND c.discord_id=gm.discord_id
                 )
               ORDER BY gm.display_name, gm.username""",
            (guild_id,),
        )
        unregistered = [dict(r) for r in await cur.fetchall()]

        # Total non-bot member count for context
        total_cur = await db.execute(
            "SELECT COUNT(*) as cnt FROM guild_members WHERE guild_id=? AND is_bot=0",
            (guild_id,),
        )
        total_row = await total_cur.fetchone()
        total_members = total_row["cnt"] if total_row else 0

    return {
        "total_members": total_members,
        "unregistered_count": len(unregistered),
        "unregistered": unregistered,
    }
