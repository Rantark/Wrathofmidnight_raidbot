"""
Raider.IO API utility.

Provides character profile lookups via the public Raider.IO API.
No authentication or API key is required.
"""

from __future__ import annotations

import re
import logging
from typing import Any, Optional
from urllib.parse import quote, unquote

import aiohttp

log = logging.getLogger(__name__)

_BASE = "https://raider.io/api/v1"
_FIELDS = "gear,spec,raid_progression"


def _slugify_realm(name: str) -> str:
    """Convert a realm name to a Raider.IO-compatible slug."""
    name = name.lower().strip()
    # Strip any trailing region suffix (e.g. "Anvilmar-US" → "Anvilmar")
    name = re.sub(r"-(us|eu|kr|tw)$", "", name)
    name = name.replace("'", "")
    name = re.sub(r"[^a-z0-9 \-]", "", name)
    name = name.replace(" ", "-")
    return name


class RaiderIO:
    """Async client for the public Raider.IO character profile API."""

    async def get_character(
        self, region: str, realm: str, name: str
    ) -> Optional[dict[str, Any]]:
        """
        Fetch a character profile from Raider.IO.

        Returns the full JSON dict on success, or None on any non-200 response
        or network error.

        Useful response keys:
          name, realm, region, class, race, active_spec_name,
          gear.item_level_equipped, thumbnail_url
        """
        realm_slug = _slugify_realm(realm)
        # Use params= so aiohttp handles percent-encoding of special chars
        params = {
            "region": region,
            "realm": realm_slug,
            "name": name.lower(),
            "fields": _FIELDS,
        }
        print(f"[RaiderIO DEBUG] GET {_BASE}/characters/profile params={params}", flush=True)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{_BASE}/characters/profile",
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    body = await resp.text()
                    print(f"[RaiderIO DEBUG] HTTP {resp.status} body: {body[:500]}", flush=True)
                    if resp.status != 200:
                        log.warning(
                            "Raider.IO character lookup failed: HTTP %d (region=%s realm=%s name=%s)",
                            resp.status, region, realm, name,
                        )
                        return None
                    import json as _json
                    return _json.loads(body)
        except Exception as exc:
            log.warning("Raider.IO get_character error: %s", exc)
            print(f"[RaiderIO DEBUG] get_character: exception: {exc}", flush=True)
            return None


def parse_url(url: str) -> Optional[tuple[str, str, str]]:
    """
    Parse a Raider.IO character profile URL into (region, realm_slug, name).

    Accepts URLs like:
      https://raider.io/characters/us/stormrage/thrall
      raider.io/characters/eu/silvermoon/arthas
      https://raider.io/characters/eu/kazzak/%C3%91ight   (percent-encoded names)

    Returns None if the URL doesn't match the expected format or has an
    invalid region. The returned name is Unicode (percent-encoding decoded).
    """
    # Allow percent-encoded characters (%XX) and hyphens in the name segment
    match = re.search(
        r"raider\.io/characters/([a-z]{2})/([a-z0-9\-]+)/([\w%\-]+)",
        url.strip(),
        re.IGNORECASE,
    )
    if not match:
        return None
    region = match.group(1).lower()
    realm  = match.group(2).lower()
    name   = unquote(match.group(3).lower())   # decode %C3%91 → ñ etc.
    if region not in ("us", "eu", "kr", "tw"):
        return None
    return region, realm, name


# Module-level singleton
client = RaiderIO()
