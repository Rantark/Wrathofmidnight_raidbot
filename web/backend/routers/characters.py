from fastapi import APIRouter, HTTPException, Depends
from database.connection import get_db
from database.queries import get_user_characters, get_all_characters
from middleware.auth import get_current_user, require_officer
from models.schemas import CharacterCreate, CharacterUpdate, CharacterAdminUpdate

router = APIRouter(prefix="/api/characters", tags=["characters"])


@router.get("")
async def list_characters(user: dict = Depends(get_current_user)):
    return await get_user_characters(int(user["user_id"]), int(user["guild_id"]))


@router.get("/roster")
async def guild_roster(user: dict = Depends(require_officer)):
    return await get_all_characters(int(user["guild_id"]))


# ── Officer: create character for any guild member ─────────────────────────────

@router.post("/officer", status_code=201)
async def officer_create_character(
    body: CharacterCreate,
    target_discord_id: int,
    user: dict = Depends(require_officer),
):
    guild_id = int(user["guild_id"])

    async with get_db() as db:
        cur = await db.execute(
            "SELECT 1 FROM characters WHERE discord_id=? AND guild_id=? AND char_name=?",
            (target_discord_id, guild_id, body.char_name),
        )
        if await cur.fetchone():
            raise HTTPException(409, f"{body.char_name} already exists for that member")

        cur2 = await db.execute(
            "SELECT COUNT(*) as cnt FROM characters WHERE discord_id=? AND guild_id=?",
            (target_discord_id, guild_id),
        )
        row = await cur2.fetchone()
        is_main = 1 if row["cnt"] == 0 else 0

        await db.execute(
            """INSERT INTO characters
               (discord_id, guild_id, char_name, char_class, main_spec, off_spec,
                is_main, ilvl, realm, region, professions, progression, raiderio_url)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (target_discord_id, guild_id, body.char_name, body.char_class, body.main_spec,
             body.off_spec, is_main, body.ilvl, body.realm, body.region,
             body.professions, body.progression, body.raiderio_url),
        )
        await db.commit()

    return {"message": "Character created", "char_name": body.char_name}


# ── Officer: edit any guild member's character ─────────────────────────────────

@router.patch("/officer/{discord_id}/{char_name}")
async def officer_update_character(
    discord_id: int,
    char_name: str,
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


# ── Officer: delete any guild member's character ───────────────────────────────

@router.delete("/officer/{discord_id}/{char_name}", status_code=204)
async def officer_delete_character(
    discord_id: int,
    char_name: str,
    user: dict = Depends(require_officer),
):
    guild_id = int(user["guild_id"])

    async with get_db() as db:
        cur = await db.execute(
            "SELECT is_main FROM characters WHERE discord_id=? AND guild_id=? AND char_name=?",
            (discord_id, guild_id, char_name),
        )
        row = await cur.fetchone()
        if not row:
            raise HTTPException(404, "Character not found")

        await db.execute(
            "DELETE FROM characters WHERE discord_id=? AND guild_id=? AND char_name=?",
            (discord_id, guild_id, char_name),
        )
        if row["is_main"]:
            await db.execute(
                """UPDATE characters SET is_main=1
                   WHERE discord_id=? AND guild_id=?
                   AND rowid=(SELECT rowid FROM characters WHERE discord_id=? AND guild_id=? LIMIT 1)""",
                (discord_id, guild_id, discord_id, guild_id),
            )
        await db.commit()


@router.post("", status_code=201)
async def create_character(body: CharacterCreate, user: dict = Depends(get_current_user)):
    discord_id = int(user["user_id"])
    guild_id = int(user["guild_id"])

    async with get_db() as db:
        cur = await db.execute(
            "SELECT 1 FROM characters WHERE discord_id=? AND guild_id=? AND char_name=?",
            (discord_id, guild_id, body.char_name),
        )
        if await cur.fetchone():
            raise HTTPException(409, f"You already have a character named {body.char_name}")

        cur2 = await db.execute(
            "SELECT COUNT(*) as cnt FROM characters WHERE discord_id=? AND guild_id=?",
            (discord_id, guild_id),
        )
        row = await cur2.fetchone()
        is_main = 1 if row["cnt"] == 0 else 0

        await db.execute(
            """INSERT INTO characters
               (discord_id, guild_id, char_name, char_class, main_spec, off_spec,
                is_main, ilvl, realm, region, professions, progression, raiderio_url)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (discord_id, guild_id, body.char_name, body.char_class, body.main_spec,
             body.off_spec, is_main, body.ilvl, body.realm, body.region,
             body.professions, body.progression, body.raiderio_url),
        )
        await db.commit()

    return {"message": "Character created", "char_name": body.char_name, "is_main": bool(is_main)}


@router.patch("/{char_name}")
async def update_character(char_name: str, body: CharacterUpdate, user: dict = Depends(get_current_user)):
    discord_id = int(user["user_id"])
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


@router.delete("/{char_name}", status_code=204)
async def delete_character(char_name: str, user: dict = Depends(get_current_user)):
    discord_id = int(user["user_id"])
    guild_id = int(user["guild_id"])

    async with get_db() as db:
        cur = await db.execute(
            "SELECT is_main FROM characters WHERE discord_id=? AND guild_id=? AND char_name=?",
            (discord_id, guild_id, char_name),
        )
        row = await cur.fetchone()
        if not row:
            raise HTTPException(404, "Character not found")

        await db.execute(
            "DELETE FROM characters WHERE discord_id=? AND guild_id=? AND char_name=?",
            (discord_id, guild_id, char_name),
        )

        if row["is_main"]:
            await db.execute(
                """UPDATE characters SET is_main=1
                   WHERE discord_id=? AND guild_id=?
                   AND rowid=(SELECT rowid FROM characters WHERE discord_id=? AND guild_id=? LIMIT 1)""",
                (discord_id, guild_id, discord_id, guild_id),
            )

        await db.commit()


@router.post("/{char_name}/main")
async def set_main(char_name: str, user: dict = Depends(get_current_user)):
    discord_id = int(user["user_id"])
    guild_id = int(user["guild_id"])

    async with get_db() as db:
        cur = await db.execute(
            "SELECT 1 FROM characters WHERE discord_id=? AND guild_id=? AND char_name=?",
            (discord_id, guild_id, char_name),
        )
        if not await cur.fetchone():
            raise HTTPException(404, "Character not found")

        await db.execute(
            "UPDATE characters SET is_main=0 WHERE discord_id=? AND guild_id=?",
            (discord_id, guild_id),
        )
        await db.execute(
            "UPDATE characters SET is_main=1 WHERE discord_id=? AND guild_id=? AND char_name=?",
            (discord_id, guild_id, char_name),
        )
        await db.commit()

    return {"message": f"{char_name} is now your main"}
