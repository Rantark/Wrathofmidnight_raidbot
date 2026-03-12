"""
Blizzard Battle.net API utility.

Handles OAuth2 client credentials flow and WoW retail profile lookups.
Tokens are cached per-region and refreshed automatically before expiry.
"""

from __future__ import annotations

import re
import time
import logging
from typing import Any, Optional

import aiohttp

log = logging.getLogger(__name__)

# ── Singleton client ──────────────────────────────────────────────────────────

_client: Optional[BlizzardClient] = None


def get_client() -> Optional[BlizzardClient]:
    """Return the module-level BlizzardClient, or None if not configured."""
    return _client


def init_client(client_id: str, client_secret: str) -> None:
    """Initialise the module-level singleton.  Call once at bot startup."""
    global _client
    _client = BlizzardClient(client_id, client_secret)
    log.info("Blizzard API client initialised")


# ── Helpers ───────────────────────────────────────────────────────────────────

def slugify(name: str) -> str:
    """
    Convert a realm or character name to a Battle.net API slug.

    Examples:
      "Kel'Thuzad"  → "kelthuzad"
      "Area 52"     → "area-52"
      "Thrall"      → "thrall"
    """
    name = name.lower().strip()
    name = name.replace("'", "")            # Kel'Thuzad → kelthuzad
    name = re.sub(r"[^a-z0-9 \-]", "", name)
    name = name.replace(" ", "-")
    return name


# ── Client ────────────────────────────────────────────────────────────────────

class BlizzardClient:
    """Async client for the Blizzard WoW Profile API."""

    # Supported regions
    REGIONS = ("us", "eu", "kr", "tw")

    def __init__(self, client_id: str, client_secret: str) -> None:
        self._client_id     = client_id
        self._client_secret = client_secret
        # region -> {"access_token": str, "expires_at": float}
        self._tokens: dict[str, dict] = {}

    # ── Auth ──────────────────────────────────────────────────────────────────

    async def _get_token(self, region: str) -> Optional[str]:
        """Return a valid access token, refreshing if within 60 s of expiry."""
        cached = self._tokens.get(region)
        if cached and time.time() < cached["expires_at"] - 60:
            return cached["access_token"]

        url = f"https://{region}.battle.net/oauth/token"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    auth=aiohttp.BasicAuth(self._client_id, self._client_secret),
                    data={"grant_type": "client_credentials"},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status != 200:
                        log.warning(
                            "Blizzard token request failed: HTTP %d (region=%s)",
                            resp.status, region,
                        )
                        return None
                    data = await resp.json()
                    self._tokens[region] = {
                        "access_token": data["access_token"],
                        "expires_at":   time.time() + data.get("expires_in", 86400),
                    }
                    log.debug("Blizzard token refreshed for region=%s", region)
                    return data["access_token"]
        except Exception as exc:
            log.warning("Blizzard token error (region=%s): %s", region, exc)
            return None

    # ── Profile endpoints ─────────────────────────────────────────────────────

    async def get_character(
        self, region: str, realm: str, name: str
    ) -> Optional[dict[str, Any]]:
        """
        Fetch a WoW retail character profile.

        Returns the JSON dict or None on 404 / network error / auth failure.

        Relevant response keys:
          character_class.name, race.name, active_spec.name,
          average_item_level, faction.name
        """
        token = await self._get_token(region)
        if not token:
            return None

        url = (
            f"https://{region}.api.blizzard.com"
            f"/profile/wow/character/{slugify(realm)}/{slugify(name)}"
        )
        params = {
            "namespace": f"profile-{region}",
            "locale":    "en_US",
            "access_token": token,
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, params=params, timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 404:
                        return None
                    if resp.status != 200:
                        log.warning(
                            "Blizzard character API HTTP %d (region=%s realm=%s name=%s)",
                            resp.status, region, realm, name,
                        )
                        return None
                    return await resp.json()
        except Exception as exc:
            log.warning("Blizzard get_character error: %s", exc)
            return None

    async def get_character_media(
        self, region: str, realm: str, name: str
    ) -> Optional[dict[str, Any]]:
        """
        Fetch character media (avatar / inset render URLs).

        Returns the JSON dict or None on error.

        Relevant response keys:
          assets -> list of {"key": "avatar"|"inset", "value": <url>}
        """
        token = await self._get_token(region)
        if not token:
            return None

        url = (
            f"https://{region}.api.blizzard.com"
            f"/profile/wow/character/{slugify(realm)}/{slugify(name)}/character-media"
        )
        params = {
            "namespace": f"profile-{region}",
            "locale":    "en_US",
            "access_token": token,
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, params=params, timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status != 200:
                        return None
                    return await resp.json()
        except Exception as exc:
            log.warning("Blizzard get_character_media error: %s", exc)
            return None

    def extract_avatar_url(self, media_data: dict[str, Any]) -> Optional[str]:
        """Pull the avatar URL out of a character-media response."""
        for asset in media_data.get("assets", []):
            if asset.get("key") == "avatar":
                return asset.get("value")
        return None
