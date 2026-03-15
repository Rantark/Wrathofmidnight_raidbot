"""
Input validation helpers for commands.
"""

import re
from datetime import datetime
from typing import Optional

from utils.constants import VALID_SPECS, ALL_SPECS, EVENT_TYPES


def validate_date(date_str: str) -> Optional[datetime]:
    """
    Parse a date string.  Accepts YYYY-MM-DD or MM/DD/YYYY.
    Returns a datetime object or None if invalid.
    """
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None


def validate_time(time_str: str) -> Optional[str]:
    """
    Validate a time string.  Accepts HH:MM (24-h) or H:MM AM/PM.
    Returns normalised HH:MM string or None if invalid.
    """
    for fmt in ("%H:%M", "%I:%M %p", "%I:%M%p", "%I %p", "%I%p"):
        try:
            t = datetime.strptime(time_str.strip().upper(), fmt.upper())
            return t.strftime("%H:%M")
        except ValueError:
            continue
    return None


def validate_class(char_class: str) -> Optional[str]:
    """
    Return the properly-cased class name or None if not found.
    Case-insensitive comparison.
    """
    for cls in VALID_SPECS:
        if cls.lower() == char_class.lower():
            return cls
    return None


def validate_spec(char_class: str, spec: str) -> Optional[str]:
    """
    Return the properly-cased spec name for the given class, or None.
    Case-insensitive comparison.
    """
    for valid_spec in ALL_SPECS.get(char_class, []):
        if valid_spec.lower() == spec.lower():
            return valid_spec
    return None


def validate_event_type(event_type: str) -> Optional[str]:
    """Return the matching event type string (case-insensitive) or None."""
    for et in EVENT_TYPES:
        if et.lower() == event_type.lower():
            return et
    return None


def validate_ilvl(ilvl: int) -> bool:
    """Item level must be in a sane WoW range."""
    return 1 <= ilvl <= 700


def validate_char_name(name: str) -> bool:
    """WoW character names are 2-12 letters; allows accented/special Latin characters."""
    return bool(re.match(r"^[^\W\d_]{2,12}$", name, re.UNICODE))


def validate_percentage(value: int) -> bool:
    return 0 <= value <= 100
