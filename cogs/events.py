"""
Event management cog.
Commands: /raid create, edit, cancel, list, info, lock, template save/load/list/delete
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

import config
from database import queries
from utils import embeds
from utils.constants import EVENT_TYPES, REMINDER_INTERVALS
from utils.validators import validate_date, validate_time, validate_event_type

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


async def _refresh_event_embed(bot: commands.Bot, event_id: int) -> None:
    """Fetch fresh signup data and edit the event message in place."""
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
    embed = embeds.build_event_embed(
        event, categorised,
        locked=bool(event["locked"]),
        last_updated=datetime.utcnow(),
    )
    await message.edit(embed=embed)


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

    @raid_group.command(name="create", description="Create a new raid event")
    @app_commands.describe(
        name="Event name (e.g. 'Heroic Vault')",
        date="Date: YYYY-MM-DD or MM/DD/YYYY",
        time="Start time: HH:MM (24h) or H:MM AM/PM",
        event_type="Type of event",
        description="Optional description",
        max_tanks="Max tanks (default 2)",
        max_healers="Max healers (default 5)",
        max_dps="Max DPS (default 13)",
    )
    async def raid_create(
        self,
        interaction: discord.Interaction,
        name: str,
        date: str,
        time: str,
        event_type: str,
        description: Optional[str] = None,
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

        settings = await queries.get_guild_settings(config.DATABASE_PATH, interaction.guild_id)
        channel_id = settings.get("event_channel_id") or interaction.channel_id

        event_id = await queries.create_event(
            config.DATABASE_PATH,
            interaction.guild_id,
            name,
            validated_type,
            parsed_date.strftime("%Y-%m-%d"),
            normalised_time,
            interaction.user.id,
            description or "",
            channel_id,
            max_tanks,
            max_healers,
            max_dps,
        )

        # Schedule reminders
        event_dt = datetime.strptime(
            f"{parsed_date.strftime('%Y-%m-%d')} {normalised_time}", "%Y-%m-%d %H:%M"
        )
        fire_times = []
        for label, seconds in REMINDER_INTERVALS.items():
            fire_dt = event_dt - timedelta(seconds=seconds)
            if fire_dt > datetime.utcnow():
                fire_times.append((fire_dt.isoformat(), label))
        if fire_times:
            await queries.schedule_reminders(config.DATABASE_PATH, event_id, fire_times)

        # Post the embed in the event channel
        channel = self.bot.get_channel(channel_id) or interaction.channel
        empty_signups: dict = {"tanks": [], "healers": [], "dps": [], "bench": [], "tentative": [], "declined": []}
        fake_event = {
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
        msg = await channel.send(embed=embed, view=view)
        await queries.set_event_message(config.DATABASE_PATH, event_id, msg.id, channel.id)

        confirm_embed = embeds.success_embed(
            "Event Created",
            f"**{name}** (ID: `{event_id}`) has been posted in {channel.mention}.",
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
    )
    async def template_load(
        self, interaction: discord.Interaction, template_name: str, date: str
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

        settings = await queries.get_guild_settings(config.DATABASE_PATH, interaction.guild_id)
        channel_id = settings.get("event_channel_id") or interaction.channel_id

        event_id = await queries.create_event(
            config.DATABASE_PATH,
            interaction.guild_id,
            tmpl["event_name"],
            tmpl["event_type"],
            parsed_date.strftime("%Y-%m-%d"),
            tmpl["event_time"],
            interaction.user.id,
            tmpl["description"] or "",
            channel_id,
            tmpl["max_tanks"],
            tmpl["max_healers"],
            tmpl["max_dps"],
        )

        channel = self.bot.get_channel(channel_id) or interaction.channel
        empty: dict = {"tanks": [], "healers": [], "dps": [], "bench": [], "tentative": [], "declined": []}
        fake_event = {
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
        msg = await channel.send(embed=embed, view=view)
        await queries.set_event_message(config.DATABASE_PATH, event_id, msg.id, channel.id)

        await interaction.followup.send(
            embed=embeds.success_embed(
                "Event Created from Template",
                f"**{tmpl['event_name']}** (ID: `{event_id}`) posted in {channel.mention}.",
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


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Events(bot))
