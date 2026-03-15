"""
World of Warcraft constants: classes, specs, colors, and emojis.
"""

from typing import Dict, List

# ── WoW Class Colors (Discord embed hex values) ───────────────────────────────
CLASS_COLORS: Dict[str, int] = {
    "Death Knight": 0xC41F3B,
    "Demon Hunter": 0xA330C9,
    "Druid":        0xFF7D0A,
    "Evoker":       0x33937F,
    "Hunter":       0xABD473,
    "Mage":         0x40C7EB,
    "Monk":         0x00FF96,
    "Paladin":      0xF58CBA,
    "Priest":       0xFFFFFF,
    "Rogue":        0xFFF569,
    "Shaman":       0x0070DE,
    "Warlock":      0x8788EE,
    "Warrior":      0xC79C6E,
}

# ── Valid Specs per Class ─────────────────────────────────────────────────────
# Structure: class -> role -> [spec names]
VALID_SPECS: Dict[str, Dict[str, List[str]]] = {
    "Death Knight": {
        "tank": ["Blood"],
        "dps":  ["Frost", "Unholy"],
    },
    "Demon Hunter": {
        "tank": ["Vengeance"],
        "dps":  ["Havoc"],
    },
    "Druid": {
        "tank":   ["Guardian"],
        "healer": ["Restoration"],
        "dps":    ["Balance", "Feral"],
    },
    "Evoker": {
        "healer": ["Preservation"],
        "dps":    ["Devastation", "Augmentation"],
    },
    "Hunter": {
        "dps": ["Beast Mastery", "Marksmanship", "Survival"],
    },
    "Mage": {
        "dps": ["Arcane", "Fire", "Frost"],
    },
    "Monk": {
        "tank":   ["Brewmaster"],
        "healer": ["Mistweaver"],
        "dps":    ["Windwalker"],
    },
    "Paladin": {
        "tank":   ["Protection"],
        "healer": ["Holy"],
        "dps":    ["Retribution"],
    },
    "Priest": {
        "healer": ["Discipline", "Holy"],
        "dps":    ["Shadow"],
    },
    "Rogue": {
        "dps": ["Assassination", "Outlaw", "Subtlety"],
    },
    "Shaman": {
        "healer": ["Restoration"],
        "dps":    ["Elemental", "Enhancement"],
    },
    "Warlock": {
        "dps": ["Affliction", "Demonology", "Destruction"],
    },
    "Warrior": {
        "tank": ["Protection"],
        "dps":  ["Arms", "Fury"],
    },
}

# ── Flattened spec list per class for easy validation ─────────────────────────
ALL_SPECS: Dict[str, List[str]] = {
    cls: [spec for specs in roles.values() for spec in specs]
    for cls, roles in VALID_SPECS.items()
}

# ── Role Emojis ───────────────────────────────────────────────────────────────
ROLE_EMOJIS: Dict[str, str] = {
    "tank":      "🛡️",
    "healer":    "💚",
    "dps":       "⚔️",
    "bench":     "🪑",
    "tentative": "❓",
    "declined":  "❌",
}

# ── Event Type Labels ─────────────────────────────────────────────────────────
EVENT_TYPES: List[str] = [
    "Normal Raid",
    "Heroic Raid",
    "Mythic Raid",
    "Mythic+ Night",
    "PvP - RBG",
    "PvP - Arena",
    "Achievement Run",
    "Alt Raid",
    "Social Event",
]

# Event types that use simple Attending/Decline signups instead of role-based
SOCIAL_EVENT_TYPES: set = {
    "Social Event",
    "Achievement Run",
    "PvP - RBG",
    "PvP - Arena",
    "Mythic+ Night",
}

# ── Attendance Status Labels ──────────────────────────────────────────────────
ATTENDANCE_STATUSES: List[str] = ["present", "absent", "late", "excused"]

# ── Signup Statuses ───────────────────────────────────────────────────────────
SIGNUP_STATUSES: List[str] = ["confirmed", "bench", "tentative", "declined"]

# ── Reminder intervals (seconds before event) ─────────────────────────────────
REMINDER_INTERVALS: Dict[str, int] = {
    "24h":  86400,
    "2h":   7200,
    "30m":  1800,
    "5m":   300,
}

# ── Default roster composition ────────────────────────────────────────────────
DEFAULT_MAX_TANKS:   int = 2
DEFAULT_MAX_HEALERS: int = 5
DEFAULT_MAX_DPS:     int = 13

# ── Bot embed colour (generic, non-class-specific) ────────────────────────────
BOT_COLOR: int = 0x3498DB   # Blizzard-ish blue
ERROR_COLOR: int = 0xE74C3C
SUCCESS_COLOR: int = 0x2ECC71
WARNING_COLOR: int = 0xF39C12


def get_spec_role(char_class: str, spec: str) -> str | None:
    """Return the role ('tank', 'healer', 'dps') for a given class/spec pair."""
    roles = VALID_SPECS.get(char_class, {})
    for role, specs in roles.items():
        if spec in specs:
            return role
    return None


def validate_class_spec(char_class: str, spec: str) -> bool:
    """Return True if the spec is valid for the given class."""
    return spec in ALL_SPECS.get(char_class, [])
