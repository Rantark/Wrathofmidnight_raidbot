from datetime import datetime, timedelta, timezone
import jwt
from config import JWT_SECRET_KEY, JWT_ALGORITHM, JWT_EXPIRE_DAYS


def create_jwt(user_id: str, username: str, role: str, guild_id: str) -> str:
    payload = {
        "user_id": user_id,
        "username": username,
        "role": role,
        "guild_id": guild_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRE_DAYS),
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def verify_jwt(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise ValueError("Token expired")
    except jwt.InvalidTokenError:
        raise ValueError("Invalid token")
