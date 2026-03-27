from fastapi import Depends, HTTPException, Header
from typing import Optional
from auth.jwt_handler import verify_jwt


def _extract_token(authorization: Optional[str]) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = authorization.split(" ", 1)[1]
    try:
        return verify_jwt(token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


async def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    return _extract_token(authorization)


async def require_raid_leader(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") not in ("raid_leader", "officer"):
        raise HTTPException(status_code=403, detail="Raid leader or officer role required")
    return user


async def require_officer(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "officer":
        raise HTTPException(status_code=403, detail="Officer role required")
    return user
