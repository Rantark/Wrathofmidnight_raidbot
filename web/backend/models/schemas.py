from pydantic import BaseModel, HttpUrl, field_validator
from typing import Optional, Literal


# ── Auth ────────────────────────────────────────────────────────────────────

class TokenResponse(BaseModel):
    token: str
    user: dict


# ── Characters ───────────────────────────────────────────────────────────────

class CharacterCreate(BaseModel):
    char_name: str
    char_class: str
    main_spec: str
    off_spec: Optional[str] = None
    ilvl: Optional[int] = None
    realm: Optional[str] = None
    region: Optional[str] = "us"
    professions: Optional[str] = None
    progression: Optional[str] = None
    raiderio_url: Optional[str] = None

    @field_validator("char_name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not (2 <= len(v) <= 24):
            raise ValueError("Character name must be 2–24 characters")
        return v.title()


class CharacterUpdate(BaseModel):
    main_spec: Optional[str] = None
    off_spec: Optional[str] = None
    ilvl: Optional[int] = None
    professions: Optional[str] = None
    progression: Optional[str] = None
    raiderio_url: Optional[str] = None


class CharacterAdminUpdate(CharacterUpdate):
    notes: Optional[str] = None
    realm: Optional[str] = None
    region: Optional[str] = None


# ── Absences ─────────────────────────────────────────────────────────────────

class AbsenceCreate(BaseModel):
    event_id: int
    reason: str


# ── Attendance ────────────────────────────────────────────────────────────────

AttendanceStatus = Literal["present", "absent", "late", "excused"]


class AttendanceRecord(BaseModel):
    discord_id: str
    status: AttendanceStatus


class AttendanceMarkRequest(BaseModel):
    event_id: int
    records: list[AttendanceRecord]
