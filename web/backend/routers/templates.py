from fastapi import APIRouter, HTTPException, Depends
from database.connection import get_db
from database.queries import get_event, get_guild_settings
from middleware.auth import require_raid_leader
from models.schemas import TemplateSave, TemplateLoad

router = APIRouter(prefix="/api/templates", tags=["templates"])


@router.get("")
async def list_templates(user: dict = Depends(require_raid_leader)):
    guild_id = int(user["guild_id"])
    async with get_db() as db:
        cur = await db.execute(
            "SELECT * FROM event_templates WHERE guild_id=? ORDER BY template_name ASC",
            (guild_id,),
        )
        rows = await cur.fetchall()
    return [dict(r) for r in rows]


@router.post("", status_code=201)
async def save_template(body: TemplateSave, user: dict = Depends(require_raid_leader)):
    guild_id = int(user["guild_id"])
    created_by = int(user["user_id"])

    event = await get_event(body.event_id, guild_id)
    if not event:
        raise HTTPException(404, "Event not found")

    template_name = body.template_name.strip()
    if not template_name:
        raise HTTPException(400, "Template name cannot be empty")

    async with get_db() as db:
        await db.execute(
            """INSERT INTO event_templates
               (guild_id, template_name, event_name, event_type, event_time,
                description, max_tanks, max_healers, max_dps, created_by)
               VALUES (?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(guild_id, template_name) DO UPDATE SET
                 event_name=excluded.event_name,
                 event_type=excluded.event_type,
                 event_time=excluded.event_time,
                 description=excluded.description,
                 max_tanks=excluded.max_tanks,
                 max_healers=excluded.max_healers,
                 max_dps=excluded.max_dps""",
            (guild_id, template_name, event["event_name"], event["event_type"],
             event["event_time"], event["description"],
             event["max_tanks"], event["max_healers"], event["max_dps"], created_by),
        )
        await db.commit()

    return {"message": f"Template '{template_name}' saved"}


@router.post("/{template_name}/load", status_code=201)
async def load_template(template_name: str, body: TemplateLoad, user: dict = Depends(require_raid_leader)):
    guild_id = int(user["guild_id"])
    created_by = int(user["user_id"])

    async with get_db() as db:
        cur = await db.execute(
            "SELECT * FROM event_templates WHERE guild_id=? AND template_name=?",
            (guild_id, template_name),
        )
        tmpl = await cur.fetchone()
        if not tmpl:
            raise HTTPException(404, f"Template '{template_name}' not found")

        cur2 = await db.execute(
            """INSERT INTO events
               (guild_id, event_name, event_type, event_date, event_time,
                description, created_by, max_tanks, max_healers, max_dps, status)
               VALUES (?,?,?,?,?,?,?,?,?,?,'active')""",
            (guild_id, tmpl["event_name"], tmpl["event_type"], body.date,
             tmpl["event_time"], tmpl["description"], created_by,
             tmpl["max_tanks"], tmpl["max_healers"], tmpl["max_dps"]),
        )
        await db.commit()
        event_id = cur2.lastrowid

    return {"message": "Event created from template", "event_id": event_id}


@router.delete("/{template_name}", status_code=204)
async def delete_template(template_name: str, user: dict = Depends(require_raid_leader)):
    guild_id = int(user["guild_id"])
    async with get_db() as db:
        cur = await db.execute(
            "SELECT 1 FROM event_templates WHERE guild_id=? AND template_name=?",
            (guild_id, template_name),
        )
        if not await cur.fetchone():
            raise HTTPException(404, f"Template '{template_name}' not found")
        await db.execute(
            "DELETE FROM event_templates WHERE guild_id=? AND template_name=?",
            (guild_id, template_name),
        )
        await db.commit()
