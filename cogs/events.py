"""
Event management cog.
Commands: /raid create, edit, cancel, list, info, lock,
          template save/load/list/delete,
          bosses set/show/mark/reset/clear
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

import config
from database import queries
from utils import embeds
from utils.constants import EVENT_TYPES, REMINDER_INTERVALS
from utils.validators import validate_date, validate_time, validate_event_type
from utils.raids import find_raid, get_bosses, RAID_EXPANSION

log = logging.getLogger(__name__)


# ── Permission helper ─────────────────────────────────────────────────────────

async def is_raid_leader(interaction: discord.Interaction) -> bool:
    """Return True if the user is an officer, raid leader, or server admin."""
    if interaction.user.guild_permissions.administrator:
        return True
    role = await queries.get_permission(
        config.DATABASE_PATH, interaction.guild_id, interaction.user.id
    )
    return role in ("officer", "raid_leader")


# ── Sign-up view (buttons attached to event embeds) ──────────────────────────

class SignupView(discord.ui.View):
    """Persistent button view for raid event signups."""

    def __init__(self, event_id: int, bot: commands.Bot) -> None:
        super().__init__(timeout=None)
        self.event_id = event_id
        self.bot = bot
        self.custom_id_prefix = f"signup_{event_id}"

    async def _handle_signup(
        self,
        interaction: discord.Interaction,
        role: str,
        signup_status: str,
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        event = await queries.get_event(config.DATABASE_PATH, self.event_id)
        if not event or event["status"] != "active":
            await interaction.followup.send(
                embed=embeds.error_embed("Event Unavailable", "This event is no longer active."),
                ephemeral=True,
            )
            return

        if event["locked"] and signup_status not in ("declined",):
            await interaction.followup.send(
                embed=embeds.warning_embed(
                    "Roster Locked",
                    "The roster for this event is locked.  Contact a raid leader to make changes.",
                ),
                ephemeral=True,
            )
            return

        # Get the user's main character
        char = await queries.get_main_character(
            config.DATABASE_PATH, interaction.user.id, interaction.guild_id
        )
        if not char and signup_status not in ("declined",):
            await interaction.followup.send(
                embed=embeds.error_embed(
                    "No Character",
                    "You haven't registered a character yet.  Use `/character add` first.",
                ),
                ephemeral=True,
            )
            return

        if signup_status == "declined":
            existing = await queries.get_signup(
                config.DATABASE_PATH, self.event_id, interaction.user.id
            )
            if existing:
                await queries.update_signup_status(
                    config.DATABASE_PATH, self.event_id, interaction.user.id, "declined"
                )
            else:
                char = char or {"char_name": "Unknown", "char_class": "Unknown", "main_spec": "Unknown"}
                await queries.add_signup(
                    config.DATABASE_PATH,
                    self.event_id,
                    interaction.user.id,
                    char["char_name"],
                    char["char_class"],
                    char["main_spec"],
                    role or "dps",
                    "declined",
                )
        elif signup_status == "tentative":
            await queries.add_signup(
                config.DATABASE_PATH,
                self.event_id,
                interaction.user.id,
                char["char_name"],
                char["char_class"],
                char["main_spec"],
                role,
                "tentative",
            )
        else:
            # Check if role is full → bench
            all_signups = await queries.get_event_signups(config.DATABASE_PATH, self.event_id)
            categorised = queries.categorise_signups(
                all_signups, event["max_tanks"], event["max_healers"], event["max_dps"]
            )
            role_full = (
                (role == "tank"   and len(categorised["tanks"])   >= event["max_tanks"]) or
                (role == "healer" and len(categorised["healers"]) >= event["max_healers"]) or
                (role == "dps"    and len(categorised["dps"])     >= event["max_dps"])
            )
            final_status = "bench" if role_full else "confirmed"
            await queries.add_signup(
                config.DATABASE_PATH,
                self.event_id,
                interaction.user.id,
                char["char_name"],
                char["char_class"],
                char["main_spec"],
                role,
                final_status,
            )

        # Refresh the embed
        await _refresh_event_embed(self.bot, self.event_id)

        status_msg = {
            "confirmed": "✅ You are signed up!",
            "bench":     "🪑 Role is full – added to bench.",
            "tentative": "❓ Marked as tentative.",
            "declined":  "❌ Marked as declined.",
        }.get(signup_status, "Updated.")
        await interaction.followup.send(
            embed=embeds.success_embed("Signup Updated", status_msg),
            ephemeral=True,
        )

    @discord.ui.button(label="Tank 🛡️",      style=discord.ButtonStyle.primary,  custom_id="signup_tank")
    async def tank(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self._handle_signup(interaction, "tank", "confirmed")

    @discord.ui.button(label="Healer 💚",    style=discord.ButtonStyle.success,  custom_id="signup_healer")
    async def healer(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self._handle_signup(interaction, "healer", "confirmed")

    @discord.ui.button(label="DPS ⚔️",       style=discord.ButtonStyle.secondary, custom_id="signup_dps")
    async def dps(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self._handle_signup(interaction, "dps", "confirmed")

    @discord.ui.button(label="Tentative ❓", style=discord.ButtonStyle.secondary, custom_id="signup_tentative")
    async def tentative(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self._handle_signup(interaction, "dps", "tentative")

    @discord.ui.button(label="Decline ❌",   style=discord.ButtonStyle.danger,    custom_id="signup_decline")
    async def decline(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self._handle_signup(interaction, "dps", "declined")


# ── Boss control panel (buttons for admin/log channel) ───────────────────────

class BossButton(discord.ui.Button):
    """Toggle button for a single boss on the admin control panel."""

    def __init__(self, boss: dict, event_id: int) -> None:
        defeated = bool(boss["defeated"])
        super().__init__(
            label=f"{'✅' if defeated else '⚔️'}  {boss['boss_name']}"[:80],
            style=discord.ButtonStyle.success if defeated else discord.ButtonStyle.secondary,
            custom_id=f"boss_{event_id}_{boss['sort_order']}",
        )
        self.boss_name = boss["boss_name"]
        self.event_id  = event_id

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()

        if not await is_raid_leader(interaction):
            await interaction.followup.send(
                embed=embeds.error_embed("Permission Denied", "Only raid leaders can toggle bosses."),
                ephemeral=True,
            )
            return

        boss_rows = await queries.get_event_bosses(config.DATABASE_PATH, self.event_id)
        current = next((b for b in boss_rows if b["boss_name"] == self.boss_name), None)
        if not current:
            return

        new_state = not bool(current["defeated"])
        await queries.mark_boss(
            config.DATABASE_PATH, self.event_id, self.boss_name, new_state, interaction.user.id
        )

        # Refresh the public event embed to reflect new boss state
        await _refresh_event_embed(self.view.bot, self.event_id)

        # Rebuild this control panel in place
        event        = await queries.get_event(config.DATABASE_PATH, self.event_id)
        updated_rows = await queries.get_event_bosses(config.DATABASE_PATH, self.event_id)
        new_embed    = embeds.build_boss_control_embed(event, updated_rows)
        new_view     = BossControlView(self.event_id, updated_rows, self.view.bot)
        await interaction.message.edit(embed=new_embed, view=new_view)


class BossControlView(discord.ui.View):
    """Persistent view of boss toggle buttons posted in the admin/log channel."""

    def __init__(self, event_id: int, boss_rows: list[dict], bot: commands.Bot) -> None:
        super().__init__(timeout=None)
        self.event_id = event_id
        self.bot      = bot
        # Discord allows max 25 buttons per message (5 rows × 5)
        for boss in boss_rows[:25]:
            self.add_item(BossButton(boss, event_id))


async def _refresh_event_embed(bot: commands.Bot, event_id: int) -> None:
    """Fetch fresh signup + boss data and edit the event message in place."""
    event = await queries.get_event(config.DATABASE_PATH, event_id)
    if not event or not event.get("message_id") or not event.get("channel_id"):
        return

    channel = bot.get_channel(event["channel_id"])
    if not channel:
        return

    try:
        message = await channel.fetch_message(event["message_id"])
    except discord.NotFound:
        return

    all_signups = await queries.get_event_signups(config.DATABASE_PATH, event_id)
    categorised = queries.categorise_signups(
        all_signups, event["max_tanks"], event["max_healers"], event["max_dps"]
    )
    boss_rows = await queries.get_event_bosses(config.DATABASE_PATH, event_id)
    embed = embeds.build_event_embed(
        event, categorised,
        locked=bool(event["locked"]),
        last_updated=datetime.now(timezone.utc),
        bosses=boss_rows if boss_rows else None,
    )
    await message.edit(embed=embed)


# ── Autocomplete helpers ──────────────────────────────────────────────────────

async def _event_channel_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    """Return registered event channels as autocomplete choices."""
    channels = await queries.get_event_channels(config.DATABASE_PATH, interaction.guild_id)
    choices = []
    for ch in channels:
        label = ch["label"] or str(ch["channel_id"])
        # filter by what the user has typed so far
        if current.lower() in label.lower() or current in str(ch["channel_id"]):
            choices.append(app_commands.Choice(name=label, value=str(ch["channel_id"])))
    # Also allow typing a raw channel ID not in the list
    if not choices and current.isdigit():
        choices.append(app_commands.Choice(name=f"Channel {current}", value=current))
    return choices[:25]


async def _resolve_event_channel(
    bot: commands.Bot,
    interaction: discord.Interaction,
    channel_value: Optional[str],
) -> discord.TextChannel:
    """
    Resolve the target channel for an event.
    Priority: explicit channel arg → guild default → current channel.
    """
    if channel_value:
        ch = bot.get_channel(int(channel_value))
        if ch:
            return ch

    settings = await queries.get_guild_settings(config.DATABASE_PATH, interaction.guild_id)
    default_id = settings.get("event_channel_id")
    if default_id:
        ch = bot.get_channel(default_id)
        if ch:
            return ch

    return interaction.channel


# ══════════════════════════════════════════════════════════════════════════════
# Events Cog
# ══════════════════════════════════════════════════════════════════════════════

class Events(commands.Cog):
    """Commands for creating and managing raid/event listings."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ── /raid ─────────────────────────────────────────────────────────────────
    raid_group = app_commands.Group(name="raid", description="Raid and event management")
    template_group = app_commands.Group(
        name="template", description="Event templates", parent=raid_group
    )
    bosses_group = app_commands.Group(
        name="bosses", description="Boss progress tracking", parent=raid_group
    )

    @raid_group.command(name="create", description="Create a new raid event")
    @app_commands.describe(
        name="Event name (e.g. 'Heroic Vault')",
        date="Date: YYYY-MM-DD or MM/DD/YYYY",
        time="Start time: HH:MM (24h) or H:MM AM/PM",
        event_type="Type of event",
        description="Optional description",
        channel="Channel to post the event in (uses default if omitted)",
        max_tanks="Max tanks (default 2)",
        max_healers="Max healers (default 5)",
        max_dps="Max DPS (default 13)",
    )
    @app_commands.autocomplete(channel=_event_channel_autocomplete)
    async def raid_create(
        self,
        interaction: discord.Interaction,
        name: str,
        date: str,
        time: str,
        event_type: str,
        description: Optional[str] = None,
        channel: Optional[str] = None,
        max_tanks: int = 2,
        max_healers: int = 5,
        max_dps: int = 13,
    ) -> None:
        await interaction.response.defer()

        if not await is_raid_leader(interaction):
            await interaction.followup.send(
                embed=embeds.error_embed("Permission Denied", "Only raid leaders can create events."),
                ephemeral=True,
            )
            return

        parsed_date = validate_date(date)
        if not parsed_date:
            await interaction.followup.send(
                embed=embeds.error_embed("Invalid Date", "Use format YYYY-MM-DD or MM/DD/YYYY."),
                ephemeral=True,
            )
            return

        normalised_time = validate_time(time)
        if not normalised_time:
            await interaction.followup.send(
                embed=embeds.error_embed("Invalid Time", "Use HH:MM (24h) or H:MM AM/PM."),
                ephemeral=True,
            )
            return

        validated_type = validate_event_type(event_type)
        if not validated_type:
            type_list = "\n".join(f"• {t}" for t in EVENT_TYPES)
            await interaction.followup.send(
                embed=embeds.error_embed("Invalid Event Type", f"Valid types:\n{type_list}"),
                ephemeral=True,
            )
            return

        target_channel = await _resolve_event_channel(self.bot, interaction, channel)

        event_id = await queries.create_event(
            config.DATABASE_PATH,
            interaction.guild_id,
            name,
            validated_type,
            parsed_date.strftime("%Y-%m-%d"),
            normalised_time,
            interaction.user.id,
            description or "",
            target_channel.id,
            max_tanks,
            max_healers,
            max_dps,
        )

        # Schedule reminders
        event_dt = datetime.strptime(
            f"{parsed_date.strftime('%Y-%m-%d')} {normalised_time}", "%Y-%m-%d %H:%M"
        ).replace(tzinfo=timezone.utc)
        fire_times = []
        for label, seconds in REMINDER_INTERVALS.items():
            fire_dt = event_dt - timedelta(seconds=seconds)
            if fire_dt > datetime.now(timezone.utc):
                fire_times.append((fire_dt.isoformat(), label))
        if fire_times:
            await queries.schedule_reminders(config.DATABASE_PATH, event_id, fire_times)

        # Post the embed in the event channel
        empty_signups: dict = {"tanks": [], "healers": [], "dps": [], "bench": [], "tentative": [], "declined": []}
        fake_event = {
            "event_id": event_id,
            "event_name": name,
            "event_type": validated_type,
            "event_date": parsed_date.strftime("%Y-%m-%d"),
            "event_time": normalised_time,
            "description": description or "",
            "max_tanks": max_tanks,
            "max_healers": max_healers,
            "max_dps": max_dps,
        }
        embed = embeds.build_event_embed(fake_event, empty_signups)
        view = SignupView(event_id, self.bot)
        msg = await target_channel.send(embed=embed, view=view)
        await queries.set_event_message(config.DATABASE_PATH, event_id, msg.id, target_channel.id)

        confirm_embed = embeds.success_embed(
            "Event Created",
            f"**{name}** (ID: `{event_id}`) has been posted in {target_channel.mention}.",
        )
        await interaction.followup.send(embed=confirm_embed, ephemeral=True)

    @raid_group.command(name="list", description="Show upcoming events")
    async def raid_list(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        events = await queries.get_upcoming_events(config.DATABASE_PATH, interaction.guild_id)
        if not events:
            await interaction.followup.send(
                embed=embeds.info_embed("No Upcoming Events", "There are no active events scheduled.")
            )
            return

        embed = discord.Embed(title="📅  Upcoming Events", color=0x3498DB)
        for e in events:
            all_signups = await queries.get_event_signups(config.DATABASE_PATH, e["event_id"])
            confirmed = sum(1 for s in all_signups if s["signup_status"] == "confirmed")
            max_total = e["max_tanks"] + e["max_healers"] + e["max_dps"]
            embed.add_field(
                name=f"[{e['event_id']}]  {e['event_name']}",
                value=(
                    f"📅 {e['event_date']}  🕐 {e['event_time']}\n"
                    f"🗂️ {e['event_type']}  |  👥 {confirmed}/{max_total} signed up"
                    + ("  🔒" if e["locked"] else "")
                ),
                inline=False,
            )
        await interaction.followup.send(embed=embed)

    @raid_group.command(name="info", description="Detailed event information")
    @app_commands.describe(event_id="Event ID number")
    async def raid_info(self, interaction: discord.Interaction, event_id: int) -> None:
        await interaction.response.defer()
        event = await queries.get_event(config.DATABASE_PATH, event_id)
        if not event or event["guild_id"] != interaction.guild_id:
            await interaction.followup.send(
                embed=embeds.error_embed("Not Found", f"No event with ID `{event_id}` found."),
                ephemeral=True,
            )
            return

        all_signups = await queries.get_event_signups(config.DATABASE_PATH, event_id)
        categorised = queries.categorise_signups(
            all_signups, event["max_tanks"], event["max_healers"], event["max_dps"]
        )
        embed = embeds.build_event_embed(
            event, categorised, locked=bool(event["locked"])
        )
        await interaction.followup.send(embed=embed)

    @raid_group.command(name="edit", description="Edit an event's details")
    @app_commands.describe(
        event_id="Event ID to edit",
        name="New event name",
        date="New date (YYYY-MM-DD)",
        time="New time (HH:MM)",
        event_type="New event type",
        description="New description",
        max_tanks="New max tanks",
        max_healers="New max healers",
        max_dps="New max DPS",
    )
    async def raid_edit(
        self,
        interaction: discord.Interaction,
        event_id: int,
        name: Optional[str] = None,
        date: Optional[str] = None,
        time: Optional[str] = None,
        event_type: Optional[str] = None,
        description: Optional[str] = None,
        max_tanks: Optional[int] = None,
        max_healers: Optional[int] = None,
        max_dps: Optional[int] = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        if not await is_raid_leader(interaction):
            await interaction.followup.send(
                embed=embeds.error_embed("Permission Denied", "Only raid leaders can edit events."),
                ephemeral=True,
            )
            return

        event = await queries.get_event(config.DATABASE_PATH, event_id)
        if not event or event["guild_id"] != interaction.guild_id:
            await interaction.followup.send(
                embed=embeds.error_embed("Not Found", f"No event with ID `{event_id}`."),
                ephemeral=True,
            )
            return

        updates: dict = {}
        if name:
            updates["event_name"] = name
        if date:
            parsed = validate_date(date)
            if not parsed:
                await interaction.followup.send(
                    embed=embeds.error_embed("Invalid Date", "Use YYYY-MM-DD or MM/DD/YYYY."),
                    ephemeral=True,
                )
                return
            updates["event_date"] = parsed.strftime("%Y-%m-%d")
        if time:
            nt = validate_time(time)
            if not nt:
                await interaction.followup.send(
                    embed=embeds.error_embed("Invalid Time", "Use HH:MM or H:MM AM/PM."),
                    ephemeral=True,
                )
                return
            updates["event_time"] = nt
        if event_type:
            vt = validate_event_type(event_type)
            if not vt:
                await interaction.followup.send(
                    embed=embeds.error_embed("Invalid Type", "See `/raid create` for valid types."),
                    ephemeral=True,
                )
                return
            updates["event_type"] = vt
        if description is not None:
            updates["description"] = description
        if max_tanks is not None:
            updates["max_tanks"] = max_tanks
        if max_healers is not None:
            updates["max_healers"] = max_healers
        if max_dps is not None:
            updates["max_dps"] = max_dps

        if not updates:
            await interaction.followup.send(
                embed=embeds.warning_embed("Nothing to Change", "Provide at least one field to update."),
                ephemeral=True,
            )
            return

        await queries.update_event(config.DATABASE_PATH, event_id, **updates)
        await _refresh_event_embed(self.bot, event_id)
        await interaction.followup.send(
            embed=embeds.success_embed("Event Updated", f"Event `{event_id}` has been updated."),
            ephemeral=True,
        )

    @raid_group.command(name="cancel", description="Cancel an event")
    @app_commands.describe(event_id="Event ID to cancel", reason="Optional reason")
    async def raid_cancel(
        self,
        interaction: discord.Interaction,
        event_id: int,
        reason: Optional[str] = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        if not await is_raid_leader(interaction):
            await interaction.followup.send(
                embed=embeds.error_embed("Permission Denied", "Only raid leaders can cancel events."),
                ephemeral=True,
            )
            return

        event = await queries.get_event(config.DATABASE_PATH, event_id)
        if not event or event["guild_id"] != interaction.guild_id:
            await interaction.followup.send(
                embed=embeds.error_embed("Not Found", f"No event with ID `{event_id}`."),
                ephemeral=True,
            )
            return

        await queries.cancel_event(config.DATABASE_PATH, event_id)

        # Edit the embed to show cancelled
        if event.get("message_id") and event.get("channel_id"):
            channel = self.bot.get_channel(event["channel_id"])
            if channel:
                try:
                    msg = await channel.fetch_message(event["message_id"])
                    cancelled_embed = discord.Embed(
                        title=f"❌  CANCELLED: {event['event_name']}",
                        description=f"This event has been cancelled." + (f"\n\n**Reason:** {reason}" if reason else ""),
                        color=0xE74C3C,
                    )
                    await msg.edit(embed=cancelled_embed, view=None)
                except discord.NotFound:
                    pass

        await interaction.followup.send(
            embed=embeds.success_embed("Event Cancelled", f"Event `{event_id}` has been cancelled."),
            ephemeral=True,
        )

    @raid_group.command(name="lock", description="Lock/unlock a roster (prevent new signups)")
    @app_commands.describe(event_id="Event ID to lock or unlock")
    async def raid_lock(self, interaction: discord.Interaction, event_id: int) -> None:
        await interaction.response.defer(ephemeral=True)

        if not await is_raid_leader(interaction):
            await interaction.followup.send(
                embed=embeds.error_embed("Permission Denied", "Only raid leaders can lock events."),
                ephemeral=True,
            )
            return

        event = await queries.get_event(config.DATABASE_PATH, event_id)
        if not event or event["guild_id"] != interaction.guild_id:
            await interaction.followup.send(
                embed=embeds.error_embed("Not Found", f"No event with ID `{event_id}`."),
                ephemeral=True,
            )
            return

        new_locked = 0 if event["locked"] else 1
        await queries.update_event(config.DATABASE_PATH, event_id, locked=new_locked)
        await _refresh_event_embed(self.bot, event_id)
        state = "locked 🔒" if new_locked else "unlocked 🔓"
        await interaction.followup.send(
            embed=embeds.success_embed("Roster Updated", f"Event `{event_id}` is now {state}."),
            ephemeral=True,
        )

    # ── Templates ─────────────────────────────────────────────────────────────

    @template_group.command(name="save", description="Save current event as a template")
    @app_commands.describe(event_id="Event ID to save as template", template_name="Name for the template")
    async def template_save(
        self, interaction: discord.Interaction, event_id: int, template_name: str
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        if not await is_raid_leader(interaction):
            await interaction.followup.send(
                embed=embeds.error_embed("Permission Denied", "Only raid leaders can manage templates."),
                ephemeral=True,
            )
            return

        event = await queries.get_event(config.DATABASE_PATH, event_id)
        if not event or event["guild_id"] != interaction.guild_id:
            await interaction.followup.send(
                embed=embeds.error_embed("Not Found", f"No event with ID `{event_id}`."),
                ephemeral=True,
            )
            return

        await queries.save_template(
            config.DATABASE_PATH,
            interaction.guild_id,
            template_name,
            event["event_name"],
            event["event_type"],
            event["event_time"],
            event["description"] or "",
            interaction.user.id,
            event["max_tanks"],
            event["max_healers"],
            event["max_dps"],
        )
        await interaction.followup.send(
            embed=embeds.success_embed("Template Saved", f"Template **{template_name}** saved."),
            ephemeral=True,
        )

    @template_group.command(name="load", description="Create a new event from a template")
    @app_commands.describe(
        template_name="Name of the template to load",
        date="Date for the new event (YYYY-MM-DD)",
        channel="Channel to post the event in (uses default if omitted)",
    )
    @app_commands.autocomplete(channel=_event_channel_autocomplete)
    async def template_load(
        self,
        interaction: discord.Interaction,
        template_name: str,
        date: str,
        channel: Optional[str] = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        if not await is_raid_leader(interaction):
            await interaction.followup.send(
                embed=embeds.error_embed("Permission Denied", "Only raid leaders can create events."),
                ephemeral=True,
            )
            return

        tmpl = await queries.get_template(config.DATABASE_PATH, interaction.guild_id, template_name)
        if not tmpl:
            await interaction.followup.send(
                embed=embeds.error_embed("Not Found", f"No template named **{template_name}**."),
                ephemeral=True,
            )
            return

        parsed_date = validate_date(date)
        if not parsed_date:
            await interaction.followup.send(
                embed=embeds.error_embed("Invalid Date", "Use YYYY-MM-DD."),
                ephemeral=True,
            )
            return

        target_channel = await _resolve_event_channel(self.bot, interaction, channel)

        event_id = await queries.create_event(
            config.DATABASE_PATH,
            interaction.guild_id,
            tmpl["event_name"],
            tmpl["event_type"],
            parsed_date.strftime("%Y-%m-%d"),
            tmpl["event_time"],
            interaction.user.id,
            tmpl["description"] or "",
            target_channel.id,
            tmpl["max_tanks"],
            tmpl["max_healers"],
            tmpl["max_dps"],
        )

        empty: dict = {"tanks": [], "healers": [], "dps": [], "bench": [], "tentative": [], "declined": []}
        fake_event = {
            "event_id": event_id,
            "event_name": tmpl["event_name"],
            "event_type": tmpl["event_type"],
            "event_date": parsed_date.strftime("%Y-%m-%d"),
            "event_time": tmpl["event_time"],
            "description": tmpl["description"] or "",
            "max_tanks": tmpl["max_tanks"],
            "max_healers": tmpl["max_healers"],
            "max_dps": tmpl["max_dps"],
        }
        embed = embeds.build_event_embed(fake_event, empty)
        view = SignupView(event_id, self.bot)
        msg = await target_channel.send(embed=embed, view=view)
        await queries.set_event_message(config.DATABASE_PATH, event_id, msg.id, target_channel.id)

        await interaction.followup.send(
            embed=embeds.success_embed(
                "Event Created from Template",
                f"**{tmpl['event_name']}** (ID: `{event_id}`) posted in {target_channel.mention}.",
            ),
            ephemeral=True,
        )

    @template_group.command(name="list", description="List saved templates")
    async def template_list(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        templates = await queries.list_templates(config.DATABASE_PATH, interaction.guild_id)
        if not templates:
            await interaction.followup.send(
                embed=embeds.info_embed("No Templates", "No templates saved yet.  Create one with `/raid template save`."),
                ephemeral=True,
            )
            return
        embed = discord.Embed(title="📋  Event Templates", color=0x3498DB)
        for t in templates:
            embed.add_field(
                name=t["template_name"],
                value=f"{t['event_name']}  |  {t['event_type']}  @  {t['event_time']}",
                inline=False,
            )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @template_group.command(name="delete", description="Delete a saved template")
    @app_commands.describe(template_name="Template to delete")
    async def template_delete(
        self, interaction: discord.Interaction, template_name: str
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        if not await is_raid_leader(interaction):
            await interaction.followup.send(
                embed=embeds.error_embed("Permission Denied", "Only raid leaders can delete templates."),
                ephemeral=True,
            )
            return

        tmpl = await queries.get_template(config.DATABASE_PATH, interaction.guild_id, template_name)
        if not tmpl:
            await interaction.followup.send(
                embed=embeds.error_embed("Not Found", f"No template named **{template_name}**."),
                ephemeral=True,
            )
            return

        await queries.delete_template(config.DATABASE_PATH, interaction.guild_id, template_name)
        await interaction.followup.send(
            embed=embeds.success_embed("Template Deleted", f"Template **{template_name}** deleted."),
            ephemeral=True,
        )


    # ── /raid bosses autocomplete ──────────────────────────────────────────────

    async def _raid_name_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        matches = find_raid(current)
        return [app_commands.Choice(name=r, value=r) for r in matches]

    async def _boss_name_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        """Autocomplete boss names from the bosses already assigned to the event."""
        # Pull event_id from the interaction namespace if available
        event_id: Optional[int] = None
        try:
            event_id = int(interaction.namespace.event_id)
        except (AttributeError, TypeError, ValueError):
            return []

        boss_rows = await queries.get_event_bosses(config.DATABASE_PATH, event_id)
        q = current.lower()
        return [
            app_commands.Choice(name=b["boss_name"], value=b["boss_name"])
            for b in boss_rows
            if q in b["boss_name"].lower()
        ][:25]

    # ── Boss progress interactive view ────────────────────────────────────────

    async def _refresh_boss_control_panel(self, event_id: int) -> None:
        """Re-fetch boss data and edit the admin control panel message in place."""
        event = await queries.get_event(config.DATABASE_PATH, event_id)
        if not event or not event.get("boss_message_id") or not event.get("boss_channel_id"):
            return
        channel = self.bot.get_channel(event["boss_channel_id"])
        if not channel:
            return
        try:
            msg = await channel.fetch_message(event["boss_message_id"])
        except discord.NotFound:
            return
        boss_rows = await queries.get_event_bosses(config.DATABASE_PATH, event_id)
        embed = embeds.build_boss_control_embed(event, boss_rows)
        view  = BossControlView(event_id, boss_rows, self.bot)
        await msg.edit(embed=embed, view=view)

    # ── /raid bosses set ───────────────────────────────────────────────────────

    @bosses_group.command(name="set", description="Assign a raid's boss list to this event")
    @app_commands.describe(
        event_id="Event ID",
        raid_name="Name of the WoW raid (autocomplete available)",
    )
    @app_commands.autocomplete(raid_name=_raid_name_autocomplete)
    async def bosses_set(
        self,
        interaction: discord.Interaction,
        event_id: int,
        raid_name: str,
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        if not await is_raid_leader(interaction):
            await interaction.followup.send(
                embed=embeds.error_embed("Permission Denied", "Only raid leaders can configure boss tracking."),
                ephemeral=True,
            )
            return

        event = await queries.get_event(config.DATABASE_PATH, event_id)
        if not event or event["guild_id"] != interaction.guild_id:
            await interaction.followup.send(
                embed=embeds.error_embed("Not Found", f"No event with ID `{event_id}`."),
                ephemeral=True,
            )
            return

        boss_list = get_bosses(raid_name)
        if not boss_list:
            # Try partial match
            matches = find_raid(raid_name)
            if matches:
                hint = "\n".join(f"• {m}" for m in matches[:5])
                await interaction.followup.send(
                    embed=embeds.error_embed(
                        "Raid Not Found",
                        f"**{raid_name}** not found.  Did you mean:\n{hint}",
                    ),
                    ephemeral=True,
                )
            else:
                await interaction.followup.send(
                    embed=embeds.error_embed(
                        "Raid Not Found",
                        f"**{raid_name}** is not in the raid database.  "
                        f"Start typing to see autocomplete suggestions.",
                    ),
                    ephemeral=True,
                )
            return

        expansion = RAID_EXPANSION.get(raid_name, "")
        await queries.set_event_bosses(config.DATABASE_PATH, event_id, raid_name, boss_list)

        # Refresh the public event embed so the boss list appears immediately
        await _refresh_event_embed(self.bot, event_id)

        # Post (or update) the boss control panel in the log/admin channel
        settings  = await queries.get_guild_settings(config.DATABASE_PATH, interaction.guild_id)
        log_ch_id = settings.get("log_channel_id")
        ctrl_ch   = self.bot.get_channel(log_ch_id) if log_ch_id else interaction.channel

        boss_rows    = await queries.get_event_bosses(config.DATABASE_PATH, event_id)
        ctrl_embed   = embeds.build_boss_control_embed(event, boss_rows)
        ctrl_view    = BossControlView(event_id, boss_rows, self.bot)

        # If a control panel already exists, edit it; otherwise post a new one
        posted_to = ctrl_ch
        if event.get("boss_message_id") and event.get("boss_channel_id"):
            existing_ch = self.bot.get_channel(event["boss_channel_id"])
            if existing_ch:
                try:
                    existing_msg = await existing_ch.fetch_message(event["boss_message_id"])
                    await existing_msg.edit(embed=ctrl_embed, view=ctrl_view)
                    posted_to = existing_ch
                    existing_msg = None  # sentinel: already updated
                except discord.NotFound:
                    existing_msg = None  # will post new below
            else:
                existing_msg = None
        else:
            existing_msg = "new"  # trigger posting new

        if existing_msg == "new" or (not event.get("boss_message_id") and ctrl_ch):
            ctrl_msg = await ctrl_ch.send(embed=ctrl_embed, view=ctrl_view)
            await queries.set_boss_embed(config.DATABASE_PATH, event_id, ctrl_msg.id, ctrl_ch.id)
            posted_to = ctrl_ch

        await interaction.followup.send(
            embed=embeds.success_embed(
                "Boss List Set",
                f"**{raid_name}** ({expansion}) — **{len(boss_list)} bosses** assigned to "
                f"event `{event_id}`.\n\n"
                f"Boss list is now visible in the event embed.\n"
                f"Control panel posted in {posted_to.mention if posted_to else 'the admin channel'} "
                f"— click buttons there to toggle boss status.",
            ),
            ephemeral=True,
        )

    # ── /raid bosses show ──────────────────────────────────────────────────────

    @bosses_group.command(name="show", description="(Re)post the boss control panel to the admin/log channel")
    @app_commands.describe(event_id="Event ID")
    async def bosses_show(self, interaction: discord.Interaction, event_id: int) -> None:
        await interaction.response.defer(ephemeral=True)

        if not await is_raid_leader(interaction):
            await interaction.followup.send(
                embed=embeds.error_embed("Permission Denied", "Only raid leaders can post the control panel."),
                ephemeral=True,
            )
            return

        event = await queries.get_event(config.DATABASE_PATH, event_id)
        if not event or event["guild_id"] != interaction.guild_id:
            await interaction.followup.send(
                embed=embeds.error_embed("Not Found", f"No event with ID `{event_id}`."),
                ephemeral=True,
            )
            return

        boss_rows = await queries.get_event_bosses(config.DATABASE_PATH, event_id)
        if not boss_rows:
            await interaction.followup.send(
                embed=embeds.error_embed("No Bosses", f"No boss list set for event `{event_id}`. Use `/raid bosses set` first."),
                ephemeral=True,
            )
            return

        ctrl_embed = embeds.build_boss_control_embed(event, boss_rows)
        ctrl_view  = BossControlView(event_id, boss_rows, self.bot)

        settings  = await queries.get_guild_settings(config.DATABASE_PATH, interaction.guild_id)
        log_ch_id = settings.get("log_channel_id")
        ctrl_ch   = self.bot.get_channel(log_ch_id) if log_ch_id else interaction.channel

        ctrl_msg = await ctrl_ch.send(embed=ctrl_embed, view=ctrl_view)
        await queries.set_boss_embed(config.DATABASE_PATH, event_id, ctrl_msg.id, ctrl_ch.id)
        await interaction.followup.send(
            embed=embeds.success_embed("Control Panel Posted", f"Boss control panel posted in {ctrl_ch.mention}."),
            ephemeral=True,
        )

    # ── /raid bosses mark ──────────────────────────────────────────────────────

    @bosses_group.command(name="mark", description="Mark a boss as defeated or alive")
    @app_commands.describe(
        event_id="Event ID",
        boss_name="Boss name (autocomplete from assigned bosses)",
        defeated="True = defeated, False = alive",
    )
    @app_commands.autocomplete(boss_name=_boss_name_autocomplete)
    async def bosses_mark(
        self,
        interaction: discord.Interaction,
        event_id: int,
        boss_name: str,
        defeated: bool,
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        if not await is_raid_leader(interaction):
            await interaction.followup.send(
                embed=embeds.error_embed("Permission Denied", "Only raid leaders can mark bosses."),
                ephemeral=True,
            )
            return

        event = await queries.get_event(config.DATABASE_PATH, event_id)
        if not event or event["guild_id"] != interaction.guild_id:
            await interaction.followup.send(
                embed=embeds.error_embed("Not Found", f"No event with ID `{event_id}`."),
                ephemeral=True,
            )
            return

        boss_rows = await queries.get_event_bosses(config.DATABASE_PATH, event_id)
        if not boss_rows:
            await interaction.followup.send(
                embed=embeds.error_embed(
                    "No Bosses", f"No boss list set for event `{event_id}`. Use `/raid bosses set` first."
                ),
                ephemeral=True,
            )
            return

        # Match boss name case-insensitively
        match = next((b for b in boss_rows if b["boss_name"].lower() == boss_name.lower()), None)
        if not match:
            available = "\n".join(f"• {b['boss_name']}" for b in boss_rows)
            await interaction.followup.send(
                embed=embeds.error_embed(
                    "Boss Not Found",
                    f"**{boss_name}** not found in this event's boss list.\n\n{available}",
                ),
                ephemeral=True,
            )
            return

        await queries.mark_boss(
            config.DATABASE_PATH, event_id, boss_name, defeated, interaction.user.id
        )

        status_str = "✅ **Defeated**" if defeated else "⚔️ **Alive**"
        await interaction.followup.send(
            embed=embeds.success_embed(
                "Boss Updated",
                f"**{match['boss_name']}** → {status_str}",
            ),
            ephemeral=True,
        )
        await _refresh_event_embed(self.bot, event_id)
        await self._refresh_boss_control_panel(event_id)

    # ── /raid bosses reset ─────────────────────────────────────────────────────

    @bosses_group.command(name="reset", description="Reset all bosses to alive (keep the list)")
    @app_commands.describe(event_id="Event ID")
    async def bosses_reset(self, interaction: discord.Interaction, event_id: int) -> None:
        await interaction.response.defer(ephemeral=True)

        if not await is_raid_leader(interaction):
            await interaction.followup.send(
                embed=embeds.error_embed("Permission Denied", "Only raid leaders can reset boss progress."),
                ephemeral=True,
            )
            return

        event = await queries.get_event(config.DATABASE_PATH, event_id)
        if not event or event["guild_id"] != interaction.guild_id:
            await interaction.followup.send(
                embed=embeds.error_embed("Not Found", f"No event with ID `{event_id}`."),
                ephemeral=True,
            )
            return

        await queries.clear_boss_progress(config.DATABASE_PATH, event_id)
        await interaction.followup.send(
            embed=embeds.success_embed(
                "Progress Reset",
                f"All bosses for event `{event_id}` have been reset to ⚔️ Alive.",
            ),
            ephemeral=True,
        )
        await _refresh_event_embed(self.bot, event_id)
        await self._refresh_boss_control_panel(event_id)

    # ── /raid bosses list ──────────────────────────────────────────────────────

    @bosses_group.command(name="list", description="Show boss progress for an event (ephemeral)")
    @app_commands.describe(event_id="Event ID")
    async def bosses_list(self, interaction: discord.Interaction, event_id: int) -> None:
        await interaction.response.defer(ephemeral=True)

        event = await queries.get_event(config.DATABASE_PATH, event_id)
        if not event or event["guild_id"] != interaction.guild_id:
            await interaction.followup.send(
                embed=embeds.error_embed("Not Found", f"No event with ID `{event_id}`."),
                ephemeral=True,
            )
            return

        boss_rows = await queries.get_event_bosses(config.DATABASE_PATH, event_id)
        embed = embeds.build_boss_control_embed(event, boss_rows)
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ── /raid bosses raids ─────────────────────────────────────────────────────

    @bosses_group.command(name="raids", description="Browse all available raids in the database")
    @app_commands.describe(expansion="Filter by expansion (optional)")
    @app_commands.choices(expansion=[
        app_commands.Choice(name="Classic",                    value="Classic"),
        app_commands.Choice(name="The Burning Crusade",        value="The Burning Crusade"),
        app_commands.Choice(name="Wrath of the Lich King",     value="Wrath of the Lich King"),
        app_commands.Choice(name="Cataclysm",                  value="Cataclysm"),
        app_commands.Choice(name="Mists of Pandaria",          value="Mists of Pandaria"),
        app_commands.Choice(name="Warlords of Draenor",        value="Warlords of Draenor"),
        app_commands.Choice(name="Legion",                     value="Legion"),
        app_commands.Choice(name="Battle for Azeroth",         value="Battle for Azeroth"),
        app_commands.Choice(name="Shadowlands",                value="Shadowlands"),
        app_commands.Choice(name="Dragonflight",               value="Dragonflight"),
        app_commands.Choice(name="The War Within",             value="The War Within"),
    ])
    async def bosses_raids(
        self,
        interaction: discord.Interaction,
        expansion: Optional[str] = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        from utils.raids import RAID_DATABASE
        embed = discord.Embed(
            title="📚  WoW Raid Database",
            color=0x3498DB,
        )

        expansions = {expansion: RAID_DATABASE[expansion]} if expansion and expansion in RAID_DATABASE \
                     else RAID_DATABASE

        for exp_name, raids in expansions.items():
            raid_lines = [f"• {raid} ({len(bosses)} bosses)" for raid, bosses in raids.items()]
            embed.add_field(
                name=exp_name,
                value="\n".join(raid_lines),
                inline=False,
            )

        embed.set_footer(text="Use /raid bosses set to assign any raid to an event")
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Events(bot))
