import aiohttp
from config import DISCORD_CLIENT_ID, DISCORD_CLIENT_SECRET, DISCORD_REDIRECT_URI

DISCORD_API = "https://discord.com/api/v10"


async def exchange_code(code: str) -> dict:
    data = {
        "client_id": DISCORD_CLIENT_ID,
        "client_secret": DISCORD_CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": DISCORD_REDIRECT_URI,
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{DISCORD_API}/oauth2/token", data=data) as resp:
            resp.raise_for_status()
            return await resp.json()


async def get_user_info(access_token: str) -> dict:
    headers = {"Authorization": f"Bearer {access_token}"}
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{DISCORD_API}/users/@me", headers=headers) as resp:
            resp.raise_for_status()
            return await resp.json()


async def get_user_guilds(access_token: str) -> list:
    headers = {"Authorization": f"Bearer {access_token}"}
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{DISCORD_API}/users/@me/guilds", headers=headers) as resp:
            resp.raise_for_status()
            return await resp.json()
