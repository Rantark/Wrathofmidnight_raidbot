"""
Discord embed builders for events, rosters, attendance, and general messages.
"""

from __future__ import annotations

import discord
from datetime import datetime
from typing import Any

from utils.constants import SOCIAL_EVENT_TYPES

from utils.constants import (
    CLASS_COLORS, ROLE_EMOJIS,
    BOT_COLOR, ERROR_COLOR, SUCCESS_COLOR, WARNING_COLOR,
)


# ── Generic helpers ───────────────────────────────────────────────────────────

def success_embed(title: str, description: str = "") -> discord.Embed:
    return discord.Embed(title=f"✅  {title}", description=description, color=SUCCESS_COLOR)


def error_embed(title: str, description: str = "") -> discord.Embed:
    return discord.Embed(title=f"❌  {title}", description=description, color=ERROR_COLOR)


def warning_embed(title: str, description: str = "") -> discord.Embed:
    return discord.Embed(title=f"⚠️  {title}", description=description, color=WARNING_COLOR)


def info_embed(title: str, description: str = "") -> discord.Embed:
    return discord.Embed(title=title, description=description, color=BOT_COLOR)


# ── Event / Roster embed ──────────────────────────────────────────────────────

def build_event_embed(
    event: dict[str, Any],
    signups: dict[str, list[dict]],
    *,
    locked: bool = False,
    last_updated: datetime | None = None,
    bosses: list[dict] | None = None,
    tz_label: str = "",
) -> discord.Embed:
    """
    Build the main roster embed for an event.

    ``event``   – row dict from the events table
    ``signups`` – dict with keys: tanks, healers, dps, bench, tentative, declined
    """
    status_tag = " 🔒 LOCKED" if locked else ""
    embed = discord.Embed(
        title=f"📅  {event['event_name']}{status_tag}",
        color=BOT_COLOR,
    )

    # Date / time line
    tz_suffix = f"  {tz_label}" if tz_label else ""
    embed.add_field(
        name="🕐  Date & Time",
        value=f"{event['event_date']}  @  {event['event_time']}{tz_suffix}",
        inline=True,
    )
    embed.add_field(name="🗂️  Type", value=event["event_type"], inline=True)

    if event.get("description"):
        embed.add_field(name="📝  Description", value=event["description"], inline=False)

    # Separator
    embed.add_field(name="\u200b", value="─" * 36, inline=False)

    tanks    = signups.get("tanks", [])
    healers  = signups.get("healers", [])
    dps      = signups.get("dps", [])
    bench    = signups.get("bench", [])
    tentative= signups.get("tentative", [])
    declined = signups.get("declined", [])

    def _roster_block(players: list[dict]) -> str:
        if not players:
            return "_None_"
        lines = []
        for i, p in enumerate(players):
            prefix = "└─" if i == len(players) - 1 else "├─"
            lines.append(
                f"{prefix} **{p['char_name']}** ({p['char_class']} – {p['main_spec']})"
            )
        return "\n".join(lines)

    def _names_block(players: list[dict]) -> str:
        if not players:
            return "_None_"
        lines = []
        for i, p in enumerate(players):
            prefix = "└─" if i == len(players) - 1 else "├─"
            lines.append(f"{prefix} **{p['char_name']}**")
        return "\n".join(lines)

    is_social = event.get("event_type") in SOCIAL_EVENT_TYPES

    if is_social:
        # Simple attending / tentative / decline layout — no role caps
        attending = tanks + healers + dps  # all confirmed signups regardless of role bucket
        embed.add_field(
            name=f"✅ Attending ({len(attending)})",
            value=_names_block(attending),
            inline=False,
        )
        if tentative:
            embed.add_field(
                name=f"{ROLE_EMOJIS['tentative']} Tentative ({len(tentative)})",
                value=_names_block(tentative),
                inline=False,
            )
        if declined:
            names = ", ".join(p["char_name"] for p in declined)
            embed.add_field(
                name=f"{ROLE_EMOJIS['declined']} Declined ({len(declined)})",
                value=names,
                inline=False,
            )
    else:
        max_tanks   = event.get("max_tanks", 2)
        max_healers = event.get("max_healers", 5)
        max_dps     = event.get("max_dps", 13)

        def _full_tag(current: int, maximum: int) -> str:
            return " **– FULL**" if current >= maximum else ""

        embed.add_field(
            name=f"{ROLE_EMOJIS['tank']} Tanks ({len(tanks)}/{max_tanks}){_full_tag(len(tanks), max_tanks)}",
            value=_roster_block(tanks),
            inline=False,
        )
        embed.add_field(
            name=f"{ROLE_EMOJIS['healer']} Healers ({len(healers)}/{max_healers}){_full_tag(len(healers), max_healers)}",
            value=_roster_block(healers),
            inline=False,
        )
        embed.add_field(
            name=f"{ROLE_EMOJIS['dps']} DPS ({len(dps)}/{max_dps}){_full_tag(len(dps), max_dps)}",
            value=_roster_block(dps),
            inline=False,
        )

        if bench:
            embed.add_field(
                name=f"{ROLE_EMOJIS['bench']} Bench ({len(bench)})",
                value=_roster_block(bench),
                inline=False,
            )

        if tentative:
            embed.add_field(
                name=f"{ROLE_EMOJIS['tentative']} Tentative ({len(tentative)})",
                value=_roster_block(tentative),
                inline=False,
            )

        if declined:
            names = ", ".join(p["char_name"] for p in declined)
            embed.add_field(
                name=f"{ROLE_EMOJIS['declined']} Declined ({len(declined)})",
                value=names,
                inline=False,
            )

    # ── Boss progress section (if bosses are assigned) ────────────────────────
    if bosses:
        b_defeated = sum(1 for b in bosses if b["defeated"])
        b_total    = len(bosses)
        b_pct      = b_defeated / b_total * 100 if b_total else 0
        b_filled   = round(b_pct / 10)
        b_bar      = "█" * b_filled + "░" * (10 - b_filled)
        raid_name  = bosses[0]["raid_name"]

        embed.add_field(name="\u200b", value="─" * 36, inline=False)
        embed.add_field(
            name=f"⚔️  {raid_name}",
            value=f"Progress: **{b_defeated}/{b_total}**  `{b_bar}`  {b_pct:.0f}%",
            inline=False,
        )

        left_lines:  list[str] = []
        right_lines: list[str] = []
        for i, boss in enumerate(bosses):
            icon = "✅" if boss["defeated"] else "⚔️"
            line = f"{icon} {boss['boss_name']}"
            if i % 2 == 0:
                left_lines.append(line)
            else:
                right_lines.append(line)

        embed.add_field(name="\u200b", value="\n".join(left_lines)  or "\u200b", inline=True)
        embed.add_field(name="\u200b", value="\n".join(right_lines) or "\u200b", inline=True)

    total = len(tanks) + len(healers) + len(dps) + len(bench) + len(tentative) + len(declined)
    updated_str = f"  •  Last updated: {last_updated.strftime('%b %d %H:%M')}" if last_updated else ""
    embed.set_footer(
        text=f"Event ID: {event['event_id']}  •  Total signups: {total}{updated_str}"
    )
    return embed


# ── Attendance embed ──────────────────────────────────────────────────────────

def build_attendance_embed(
    member_name: str,
    stats: dict[str, Any],
    history: list[str],
) -> discord.Embed:
    """
    Build an attendance statistics embed for a single member.

    ``stats``   – dict with keys: attended, total, late, excused, unexcused,
                  pct_30d, pct_all_time
    ``history`` – list of emoji strings for last 10 events (✅/❌/⏰/🔵)
    """
    attended   = stats.get("attended", 0)
    total      = stats.get("total", 0)
    late       = stats.get("late", 0)
    excused    = stats.get("excused", 0)
    unexcused  = stats.get("unexcused", 0)
    pct_30d    = stats.get("pct_30d", 0.0)
    pct_all    = stats.get("pct_all_time", 0.0)

    color = SUCCESS_COLOR if pct_all >= 80 else (WARNING_COLOR if pct_all >= 60 else ERROR_COLOR)

    embed = discord.Embed(
        title=f"📊  Attendance Report – {member_name}",
        color=color,
    )
    embed.add_field(
        name="Events Attended",
        value=f"**{attended}/{total}**  ({pct_all:.1f}%)",
        inline=True,
    )
    embed.add_field(name="Late Arrivals",     value=str(late),     inline=True)
    embed.add_field(name="Excused Absences",  value=str(excused),  inline=True)
    embed.add_field(name="Unexcused Absences",value=str(unexcused),inline=True)
    embed.add_field(name="30-Day Attendance", value=f"{pct_30d:.1f}%", inline=True)
    embed.add_field(name="All-Time Attendance",value=f"{pct_all:.1f}%",inline=True)

    if history:
        embed.add_field(
            name="Last 10 Events",
            value=" ".join(history[-10:]),
            inline=False,
        )
    return embed


# ── Character embed ───────────────────────────────────────────────────────────

def build_character_list_embed(
    discord_name: str,
    characters: list[dict[str, Any]],
) -> discord.Embed:
    embed = discord.Embed(
        title=f"🧝  Characters – {discord_name}",
        color=BOT_COLOR,
    )
    if not characters:
        embed.description = "No characters registered yet.  Use `/character add` to get started."
        return embed

    for char in characters:
        main_tag = " ⭐ **Main**" if char.get("is_main") else ""
        ilvl_tag = f"  |  iLvl {char['ilvl']}" if char.get("ilvl") else ""
        off_tag  = f"  |  Off: {char['off_spec']}" if char.get("off_spec") else ""
        embed.add_field(
            name=f"{char['char_name']}{main_tag}",
            value=f"{char['char_class']} – {char['main_spec']}{off_tag}{ilvl_tag}",
            inline=False,
        )
    return embed


# ── Reminder embed ────────────────────────────────────────────────────────────

def build_reminder_embed(event: dict[str, Any], time_label: str, signed_up: int, tz_label: str = "") -> discord.Embed:
    embed = discord.Embed(
        title=f"🔔  Raid Reminder: {event['event_name']} – {time_label}",
        color=WARNING_COLOR,
    )
    tz_suffix = f" {tz_label}" if tz_label else ""
    embed.add_field(name="Start Time", value=f"{event['event_date']} @ {event['event_time']}{tz_suffix}", inline=True)
    embed.add_field(name="Signed Up",  value=str(signed_up), inline=True)
    embed.description = (
        "Not signed up yet? Click the buttons on the event message!\n"
        "Need to report an absence? Use `/absence request`."
    )
    return embed


# ── Boss Control Panel embed (admin channel) ──────────────────────────────────

def build_boss_control_embed(
    event: dict[str, Any],
    bosses: list[dict[str, Any]],
) -> discord.Embed:
    """
    Embed displayed in the admin/log channel alongside the boss toggle buttons.
    Raid leaders click buttons below this embed to toggle bosses alive/defeated.
    """
    if not bosses:
        return info_embed("No Bosses Set", "Use `/raid bosses set` to assign a raid first.")

    raid_name  = bosses[0]["raid_name"]
    defeated   = sum(1 for b in bosses if b["defeated"])
    total      = len(bosses)
    pct        = defeated / total * 100 if total else 0
    filled     = round(pct / 10)
    bar        = "█" * filled + "░" * (10 - filled)
    color      = SUCCESS_COLOR if defeated == total else (WARNING_COLOR if defeated > 0 else BOT_COLOR)

    embed = discord.Embed(
        title=f"🎛️  Boss Control Panel — {event['event_name']}",
        description=(
            f"**{raid_name}**  •  {event.get('event_date', '?')}\n"
            f"Progress: **{defeated}/{total}**  `{bar}`  {pct:.0f}%\n\n"
            "Click a button below to toggle **✅ Defeated** / **⚔️ Alive**.\n"
            "*Changes reflect immediately in the raid channel.*"
        ),
        color=color,
    )
    embed.set_footer(
        text=(
            f"Event ID: {event['event_id']}  •  "
            f"Only raid leaders & officers can use these buttons"
            + ("  •  🏆 All clear!" if defeated == total else "")
        )
    )
    return embed


# ── Boss Progress embed ───────────────────────────────────────────────────────

def build_boss_progress_embed(
    event: dict[str, Any],
    bosses: list[dict[str, Any]],
) -> discord.Embed:
    """
    Build the live boss-progress embed for an event.

    ``bosses`` – ordered list of rows from event_bosses table.
    """
    if not bosses:
        return info_embed("No Bosses Set", "No boss list has been assigned to this event yet.")

    raid_name = bosses[0]["raid_name"]
    total     = len(bosses)
    defeated  = sum(1 for b in bosses if b["defeated"])
    pct       = defeated / total * 100 if total else 0

    # Progress bar (10 chars wide)
    filled  = round(pct / 10)
    bar     = "█" * filled + "░" * (10 - filled)

    color = SUCCESS_COLOR if defeated == total else (WARNING_COLOR if defeated > 0 else BOT_COLOR)

    embed = discord.Embed(
        title=f"⚔️  Boss Progress: {event['event_name']}",
        color=color,
    )
    embed.add_field(name="Raid",     value=raid_name,                            inline=True)
    embed.add_field(name="Date",     value=event.get("event_date", "?"),         inline=True)
    embed.add_field(name="Progress", value=f"{defeated}/{total}  `{bar}`  {pct:.0f}%", inline=False)

    # Boss list – two columns
    left_lines:  list[str] = []
    right_lines: list[str] = []
    for i, boss in enumerate(bosses):
        icon = "✅" if boss["defeated"] else "❌"
        line = f"{icon} {boss['boss_name']}"
        if i % 2 == 0:
            left_lines.append(line)
        else:
            right_lines.append(line)

    embed.add_field(name="\u200b", value="\n".join(left_lines)  or "\u200b", inline=True)
    embed.add_field(name="\u200b", value="\n".join(right_lines) or "\u200b", inline=True)

    if defeated == total:
        embed.set_footer(text="🏆  All bosses defeated!  Raid clear!")
    else:
        remaining = total - defeated
        embed.set_footer(text=f"{remaining} boss{'es' if remaining != 1 else ''} remaining")

    return embed
