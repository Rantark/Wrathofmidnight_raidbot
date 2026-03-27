from pydantic import BaseModel, field_validator
from typing import Optional, Literal


# ── Auth ─────────────────────────────────────────────────────────────────────

class TokenResponse(BaseModel):
    token: str
    user: dict


# ── Characters ────────────────────────────────────────────────────────────────

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


# ── Events ────────────────────────────────────────────────────────────────────

class EventCreate(BaseModel):
    event_name: str
    event_date: str   # YYYY-MM-DD
    event_time: str   # HH:MM
    event_type: str
    description: Optional[str] = None
    max_tanks: Optional[int] = None
    max_healers: Optional[int] = None
    max_dps: Optional[int] = None


class EventUpdate(BaseModel):
    event_name: Optional[str] = None
    event_date: Optional[str] = None
    event_time: Optional[str] = None
    event_type: Optional[str] = None
    description: Optional[str] = None
    max_tanks: Optional[int] = None
    max_healers: Optional[int] = None
    max_dps: Optional[int] = None


class EventCancel(BaseModel):
    reason: Optional[str] = None


# ── Templates ─────────────────────────────────────────────────────────────────

class TemplateSave(BaseModel):
    template_name: str
    event_id: int


class TemplateLoad(BaseModel):
    date: str   # YYYY-MM-DD


# ── Absences ──────────────────────────────────────────────────────────────────

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


# ── Admin / Permissions ───────────────────────────────────────────────────────

class PermissionGrant(BaseModel):
    discord_id: str
    username: str
    role: Literal["raid_leader", "officer"]


class GuildConfigUpdate(BaseModel):
    default_max_tanks: Optional[int] = None
    default_max_healers: Optional[int] = None
    default_max_dps: Optional[int] = None
    attendance_threshold: Optional[int] = None
    timezone: Optional[str] = None
