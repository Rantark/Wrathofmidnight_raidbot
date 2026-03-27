from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse
from auth.oauth import exchange_code, get_user_info, get_user_guilds
from auth.jwt_handler import create_jwt
from database.connection import get_db
from config import ALLOWED_GUILD_ID, DISCORD_OAUTH_URL

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/discord")
async def discord_login():
    """Redirect browser to Discord's OAuth2 consent page."""
    return RedirectResponse(DISCORD_OAUTH_URL)


@router.get("/discord/callback")
async def discord_callback(code: str):
    """
    Discord redirects here after the user grants access.
    Returns a JWT the frontend stores in localStorage.
    """
    try:
        token_data = await exchange_code(code)
    except Exception:
        raise HTTPException(400, "Failed to exchange OAuth code with Discord")

    access_token = token_data.get("access_token")
    if not access_token:
        raise HTTPException(400, "Discord did not return an access token")

    user_info = await get_user_info(access_token)
    discord_id = user_info["id"]
    username = user_info.get("global_name") or user_info.get("username", "Unknown")

    # Verify guild membership
    try:
        guilds = await get_user_guilds(access_token)
    except Exception:
        raise HTTPException(400, "Failed to fetch your Discord guild list")

    guild_ids = {g["id"] for g in guilds}
    if ALLOWED_GUILD_ID and ALLOWED_GUILD_ID not in guild_ids:
        raise HTTPException(403, "You must be a member of the Wrath of Midnight guild to use this app")

    # Look up bot-level role from database
    async with get_db() as db:
        cur = await db.execute(
            "SELECT role FROM permissions WHERE discord_id=? AND guild_id=?",
            (int(discord_id), int(ALLOWED_GUILD_ID)),
        )
        row = await cur.fetchone()
        role = row["role"] if row else "member"

    jwt_token = create_jwt(discord_id, username, role, ALLOWED_GUILD_ID)
    avatar_hash = user_info.get("avatar")
    avatar_url = (
        f"https://cdn.discordapp.com/avatars/{discord_id}/{avatar_hash}.png"
        if avatar_hash
        else f"https://cdn.discordapp.com/embed/avatars/{int(discord_id) % 5}.png"
    )

    return {
        "token": jwt_token,
        "user": {
            "user_id": discord_id,
            "username": username,
            "role": role,
            "avatar_url": avatar_url,
        },
    }


@router.get("/me")
async def get_me(authorization: str | None = None):
    """Refresh role from database and return updated user info."""
    from middleware.auth import get_current_user
    from fastapi import Header
    # Re-use dependency inline for simplicity
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing token")
    from auth.jwt_handler import verify_jwt
    try:
        payload = verify_jwt(authorization.split(" ", 1)[1])
    except ValueError as e:
        raise HTTPException(401, str(e))

    discord_id = int(payload["user_id"])
    guild_id = int(payload["guild_id"])

    async with get_db() as db:
        cur = await db.execute(
            "SELECT role FROM permissions WHERE discord_id=? AND guild_id=?",
            (discord_id, guild_id),
        )
        row = await cur.fetchone()
        role = row["role"] if row else "member"

    new_token = create_jwt(str(discord_id), payload["username"], role, str(guild_id))
    return {
        "token": new_token,
        "user": {
            "user_id": str(discord_id),
            "username": payload["username"],
            "role": role,
        },
    }
