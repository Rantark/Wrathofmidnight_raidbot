import os
from dotenv import load_dotenv
from urllib.parse import quote

load_dotenv()

DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID", "")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET", "")
DISCORD_REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI", "http://localhost:5173/auth/callback")
ALLOWED_GUILD_ID = os.getenv("ALLOWED_GUILD_ID", "")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "changeme")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_DAYS = 7
DATABASE_PATH = os.getenv("DATABASE_PATH", "../../data/raidbot.db")
API_HOST = os.getenv("API_HOST", "127.0.0.1")
API_PORT = int(os.getenv("API_PORT", "8001"))
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")]

_encoded_redirect = quote(DISCORD_REDIRECT_URI, safe='')

DISCORD_OAUTH_URL = (
    "https://discord.com/api/oauth2/authorize"
    f"?client_id={DISCORD_CLIENT_ID}"
    f"&redirect_uri={_encoded_redirect}"
    "&response_type=code"
    "&scope=identify+guilds"
)
