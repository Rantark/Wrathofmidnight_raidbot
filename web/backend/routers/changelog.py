import json
import pathlib
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/changelog", tags=["changelog"])

# Resolve to an absolute path so it works regardless of working directory
_CHANGELOG_PATH = (
    pathlib.Path(__file__).resolve().parent.parent.parent.parent / "changelog.json"
)


def _load() -> dict:
    try:
        return json.loads(_CHANGELOG_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise HTTPException(500, f"changelog.json not found (looked in {_CHANGELOG_PATH})")
    except json.JSONDecodeError as exc:
        raise HTTPException(500, f"changelog.json is malformed: {exc}")


@router.get("")
async def get_changelog():
    """Return all changelog entries, newest first."""
    return _load()


@router.get("/version")
async def get_version():
    """Return only the current version string."""
    data = _load()
    return {"version": data.get("current", "unknown")}
