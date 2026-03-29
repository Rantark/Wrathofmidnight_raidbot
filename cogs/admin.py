"""
Admin and configuration cog.
Commands: /admin set_raid_leader, remove_raid_leader, set_event_channel,
           add_event_channel, remove_event_channel, list_event_channels,
           roster_config, attendance_threshold, status, export_data,
           restart, update
"""

from __future__ import annotations

import json
import io
import logging
from datetime import datetime, timedelta, timezone as dt_timezone
from typing import Optional

import discord
import pytz
from discord import app_commands
from discord.ext import commands

import config
from database import queries
from utils import embeds
from utils.validators import validate_percentage, validate_spec, validate_ilvl
from utils.constants import CLASS_COLORS, VALID_SPECS, ALL_SPECS

log = logging.getLogger(__name__)


async def is_admin(interaction: discord.Interaction) -> bool:
    """Return True if the user is a server administrator or has the Officer bot role."""
    if interaction.user.guild_permissions.administrator:
        return True
    role = await queries.get_permission(config.DATABASE_PATH, interaction.guild_id, interaction.user.id)
    return role == "officer"


class Admin(commands.Cog):
    """Guild administration and bot configuration commands."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        self.bot.loop.create_task(self._sync_members())

    async def _sync_members(self) -> None:
        await self.bot.wait_until_ready()
        for guild in self.bot.guilds:
            try:
                async for member in guild.fetch_members(limit=None):
                    await queries.upsert_guild_member(
                        config.DATABASE_PATH,
                        guild.id,
                        member.id,
                        str(member) if hasattr(member, "discriminator") and member.discriminator != "0" else member.name,
                    )
            except Exception as e:
                log.warning("Failed to sync members for guild %s: %s", guild.id, e)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        await queries.upsert_guild_member(
            config.DATABASE_PATH,
            member.guild.id,
            member.id,
            str(member) if hasattr(member, "discriminator") and member.discriminator != "0" else member.name,
            member.display_name,
            member.bot,
        )

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        await queries.remove_guild_member(config.DATABASE_PATH, member.guild.id, member.id)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member) -> None:
        if before.display_name != after.display_name or before.name != after.name:
            await queries.upsert_guild_member(
                config.DATABASE_PATH,
                after.guild.id,
                after.id,
                str(after) if hasattr(after, "discriminator") and after.discriminator != "0" else after.name,
                after.display_name,
                after.bot,
            )

    admin_group = app_commands.Group(name="admin", description="Bot administration commands")

    # ── Permissions ────────────────────────────────────────────────────────────

    @admin_group.command(name="set_raid_leader", description="Grant Raid Leader permissions to a member")
    @app_commands.describe(member="Member to promote", role="Role to assign")
    @app_commands.choices(role=[
        app_commands.Choice(name="Raid Leader", value="raid_leader"),
        app_commands.Choice(name="Officer",     value="officer"),
    ])
    async def set_raid_leader(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        role: str = "raid_leader",
    ) -> None:
        if not await is_admin(interaction):
            await interaction.response.send_message(
                embed=embeds.error_embed("Permission Denied", "Only server admins can manage bot permissions."),
                ephemeral=True,
            )
            return

        await queries.set_permission(config.DATABASE_PATH, interaction.guild_id, member.id, role)
        await interaction.response.send_message(
            embed=embeds.success_embed(
                "Permission Granted",
                f"{member.mention} has been given the **{role.replace('_', ' ').title()}** role.",
            ),
            ephemeral=True,
        )

    @admin_group.command(name="remove_raid_leader", description="Remove Raid Leader / Officer permissions")
    @app_commands.describe(member="Member to demote")
    async def remove_raid_leader(
        self, interaction: discord.Interaction, member: discord.Member
    ) -> None:
        if not await is_admin(interaction):
            await interaction.response.send_message(
                embed=embeds.error_embed("Permission Denied", "Only server admins can manage bot permissions."),
                ephemeral=True,
            )
            return

        await queries.remove_permission(config.DATABASE_PATH, interaction.guild_id, member.id)
        await interaction.response.send_message(
            embed=embeds.success_embed("Permission Removed", f"{member.mention}'s bot role has been removed."),
            ephemeral=True,
        )

    # ── Public Guild Roster ────────────────────────────────────────────────────

    @admin_group.command(
        name="roster_post",
        description="Post a live guild roster embed that auto-updates when members register",
    )
    @app_commands.describe(channel="Channel where the roster will be posted")
    async def roster_post(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ) -> None:
        if not await is_admin(interaction):
            await interaction.response.send_message(
                embed=embeds.error_embed("Permission Denied", "Only server admins can post the guild roster."),
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        all_chars = await queries.get_all_guild_characters(config.DATABASE_PATH, interaction.guild_id)
        embed = embeds.build_guild_roster_embed(all_chars, interaction.guild.name)
        msg = await channel.send(embed=embed)
        await queries.update_guild_setting(config.DATABASE_PATH, interaction.guild_id, "roster_channel_id", channel.id)
        await queries.update_guild_setting(config.DATABASE_PATH, interaction.guild_id, "roster_message_id", msg.id)
        await interaction.followup.send(
            embed=embeds.success_embed(
                "Roster Posted",
                f"Guild roster posted in {channel.mention}.\n"
                "It will automatically update whenever members register, update, or remove characters.\n\n"
                "Pin the message so members can always find it!",
            ),
            ephemeral=True,
        )

    # ── Channel configuration ──────────────────────────────────────────────────

    @admin_group.command(name="set_event_channel", description="Set the default channel for event postings")
    @app_commands.describe(channel="Channel where events will be posted by default")
    async def set_event_channel(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ) -> None:
        if not await is_admin(interaction):
            await interaction.response.send_message(
                embed=embeds.error_embed("Permission Denied", "Only server admins can configure the bot."),
                ephemeral=True,
            )
            return

        await queries.get_guild_settings(config.DATABASE_PATH, interaction.guild_id)  # ensure row exists
        await queries.update_guild_setting(
            config.DATABASE_PATH, interaction.guild_id, "event_channel_id", channel.id
        )
        # Also register it in the multi-channel list if not already there
        await queries.add_event_channel(config.DATABASE_PATH, interaction.guild_id, channel.id, channel.name)
        await interaction.response.send_message(
            embed=embeds.success_embed(
                "Default Channel Set",
                f"Events will now be posted in {channel.mention} by default.\n"
                f"It has also been added to your event channel list.",
            ),
            ephemeral=True,
        )

    # ── Multi-channel management ───────────────────────────────────────────────

    @admin_group.command(name="add_event_channel", description="Add a channel to the event channel list")
    @app_commands.describe(channel="Channel to add", label="Optional friendly label (e.g. 'Heroic Raids')")
    async def add_event_channel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        label: Optional[str] = None,
    ) -> None:
        if not await is_admin(interaction):
            await interaction.response.send_message(
                embed=embeds.error_embed("Permission Denied", "Only server admins can configure the bot."),
                ephemeral=True,
            )
            return

        friendly = label or channel.name
        await queries.add_event_channel(config.DATABASE_PATH, interaction.guild_id, channel.id, friendly)
        await interaction.response.send_message(
            embed=embeds.success_embed(
                "Channel Added",
                f"{channel.mention} has been added to the event channel list as **{friendly}**.\n"
                f"Raid leaders can now post events to this channel with `/raid create`.",
            ),
            ephemeral=True,
        )

    @admin_group.command(name="remove_event_channel", description="Remove a channel from the event channel list")
    @app_commands.describe(channel="Channel to remove")
    async def remove_event_channel(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ) -> None:
        if not await is_admin(interaction):
            await interaction.response.send_message(
                embed=embeds.error_embed("Permission Denied", "Only server admins can configure the bot."),
                ephemeral=True,
            )
            return

        await queries.remove_event_channel(config.DATABASE_PATH, interaction.guild_id, channel.id)
        await interaction.response.send_message(
            embed=embeds.success_embed(
                "Channel Removed",
                f"{channel.mention} has been removed from the event channel list.",
            ),
            ephemeral=True,
        )

    @admin_group.command(name="list_event_channels", description="Show all registered event channels")
    async def list_event_channels(self, interaction: discord.Interaction) -> None:
        if not await is_admin(interaction):
            await interaction.response.send_message(
                embed=embeds.error_embed("Permission Denied", "Only server admins can view configuration."),
                ephemeral=True,
            )
            return

        channels = await queries.get_event_channels(config.DATABASE_PATH, interaction.guild_id)
        settings = await queries.get_guild_settings(config.DATABASE_PATH, interaction.guild_id)
        default_id = settings.get("event_channel_id")

        embed = discord.Embed(title="📢  Event Channels", color=0x3498DB)
        if not channels:
            embed.description = (
                "No event channels configured yet.\n"
                "Use `/admin add_event_channel` or `/admin set_event_channel` to add one."
            )
        else:
            lines = []
            for ch in channels:
                tag = " ⭐ **default**" if ch["channel_id"] == default_id else ""
                lines.append(f"<#{ch['channel_id']}> — {ch['label']}{tag}")
            embed.description = "\n".join(lines)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @admin_group.command(name="set_log_channel", description="Set the bot audit log channel")
    @app_commands.describe(channel="Channel for bot logs/audit messages")
    async def set_log_channel(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ) -> None:
        if not await is_admin(interaction):
            await interaction.response.send_message(
                embed=embeds.error_embed("Permission Denied", "Only server admins can configure the bot."),
                ephemeral=True,
            )
            return

        await queries.get_guild_settings(config.DATABASE_PATH, interaction.guild_id)
        await queries.update_guild_setting(
            config.DATABASE_PATH, interaction.guild_id, "log_channel_id", channel.id
        )
        await interaction.response.send_message(
            embed=embeds.success_embed("Log Channel Set", f"Bot logs will go to {channel.mention}."),
            ephemeral=True,
        )

    # ── Roster configuration ───────────────────────────────────────────────────

    @admin_group.command(name="roster_config", description="Set default roster slot counts")
    @app_commands.describe(tanks="Default max tanks", healers="Default max healers", dps="Default max DPS")
    async def roster_config(
        self,
        interaction: discord.Interaction,
        tanks: int,
        healers: int,
        dps: int,
    ) -> None:
        if not await is_admin(interaction):
            await interaction.response.send_message(
                embed=embeds.error_embed("Permission Denied", "Only server admins can configure the bot."),
                ephemeral=True,
            )
            return

        if any(v < 0 or v > 40 for v in (tanks, healers, dps)):
            await interaction.response.send_message(
                embed=embeds.error_embed("Invalid Values", "Each value must be between 0 and 40."),
                ephemeral=True,
            )
            return

        await queries.get_guild_settings(config.DATABASE_PATH, interaction.guild_id)
        await queries.update_guild_setting(config.DATABASE_PATH, interaction.guild_id, "default_max_tanks",   tanks)
        await queries.update_guild_setting(config.DATABASE_PATH, interaction.guild_id, "default_max_healers", healers)
        await queries.update_guild_setting(config.DATABASE_PATH, interaction.guild_id, "default_max_dps",     dps)

        await interaction.response.send_message(
            embed=embeds.success_embed(
                "Roster Defaults Updated",
                f"🛡️ Tanks: **{tanks}**  |  💚 Healers: **{healers}**  |  ⚔️ DPS: **{dps}**",
            ),
            ephemeral=True,
        )

    # ── Attendance threshold ───────────────────────────────────────────────────

    @admin_group.command(name="attendance_threshold", description="Set the attendance warning threshold")
    @app_commands.describe(percentage="Percentage (0-100) below which members receive warnings")
    async def attendance_threshold(self, interaction: discord.Interaction, percentage: int) -> None:
        if not await is_admin(interaction):
            await interaction.response.send_message(
                embed=embeds.error_embed("Permission Denied", "Only server admins can configure the bot."),
                ephemeral=True,
            )
            return

        if not validate_percentage(percentage):
            await interaction.response.send_message(
                embed=embeds.error_embed("Invalid Value", "Percentage must be between 0 and 100."),
                ephemeral=True,
            )
            return

        await queries.get_guild_settings(config.DATABASE_PATH, interaction.guild_id)
        await queries.update_guild_setting(
            config.DATABASE_PATH, interaction.guild_id, "attendance_threshold", percentage
        )
        await interaction.response.send_message(
            embed=embeds.success_embed(
                "Threshold Updated",
                f"Members with attendance below **{percentage}%** will be flagged in reports.",
            ),
            ephemeral=True,
        )

    # ── Timezone ───────────────────────────────────────────────────────────────

    @admin_group.command(name="timezone", description="Set the timezone used for event times")
    @app_commands.describe(timezone="IANA timezone name (e.g. America/New_York, America/Chicago, Europe/London)")
    async def set_timezone(self, interaction: discord.Interaction, timezone: str) -> None:
        if not await is_admin(interaction):
            await interaction.response.send_message(
                embed=embeds.error_embed("Permission Denied", "Only server admins can configure the bot."),
                ephemeral=True,
            )
            return

        try:
            guild_tz = pytz.timezone(timezone)
        except pytz.exceptions.UnknownTimeZoneError:
            await interaction.response.send_message(
                embed=embeds.error_embed(
                    "Invalid Timezone",
                    f"**{timezone}** is not a recognised IANA timezone.\n\n"
                    "Common examples:\n"
                    "`America/New_York` · `America/Chicago` · `America/Denver`\n"
                    "`America/Los_Angeles` · `Europe/London` · `Europe/Paris`\n"
                    "`Asia/Tokyo` · `Australia/Sydney`",
                ),
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        await queries.get_guild_settings(config.DATABASE_PATH, interaction.guild_id)
        await queries.update_guild_setting(config.DATABASE_PATH, interaction.guild_id, "timezone", timezone)

        # Reschedule reminders and refresh embeds for all upcoming active events
        from utils.constants import REMINDER_INTERVALS
        from cogs.events import _refresh_event_embed

        upcoming = await queries.get_upcoming_events(config.DATABASE_PATH, interaction.guild_id)
        refreshed = 0
        for event in upcoming:
            # Replace unsent reminders with correctly-offset times
            await queries.delete_unsent_reminders(config.DATABASE_PATH, event["event_id"])
            try:
                event_dt = guild_tz.localize(
                    datetime.strptime(f"{event['event_date']} {event['event_time']}", "%Y-%m-%d %H:%M")
                )
                fire_times = []
                for label, seconds in REMINDER_INTERVALS.items():
                    fire_dt = event_dt - timedelta(seconds=seconds)
                    if fire_dt > datetime.now(dt_timezone.utc):
                        # Always store as UTC so SQLite string comparison works correctly
                        fire_times.append((fire_dt.astimezone(dt_timezone.utc).isoformat(), label))
                if fire_times:
                    await queries.schedule_reminders(config.DATABASE_PATH, event["event_id"], fire_times)
            except Exception:
                pass

            # Refresh the Discord embed so it shows the new timezone abbreviation
            await _refresh_event_embed(self.bot, event["event_id"])
            refreshed += 1

        detail = f"Updated **{refreshed}** active event(s) — reminders rescheduled and embeds refreshed." if refreshed else "No active events to update."
        await interaction.followup.send(
            embed=embeds.success_embed(
                "Timezone Updated",
                f"Server timezone is now **{timezone}**.\n\n{detail}",
            ),
            ephemeral=True,
        )

    # ── Status overview ────────────────────────────────────────────────────────

    @admin_group.command(name="status", description="View bot configuration for this server")
    async def status(self, interaction: discord.Interaction) -> None:
        if not await is_admin(interaction):
            await interaction.response.send_message(
                embed=embeds.error_embed("Permission Denied", "Only server admins can view configuration."),
                ephemeral=True,
            )
            return

        settings = await queries.get_guild_settings(config.DATABASE_PATH, interaction.guild_id)
        channels = await queries.get_event_channels(config.DATABASE_PATH, interaction.guild_id)
        embed = discord.Embed(title="⚙️  Bot Configuration", color=0x3498DB)

        default_id = settings.get("event_channel_id")
        evt_ch = f"<#{default_id}>" if default_id else "_Not set_"
        log_ch = f"<#{settings['log_channel_id']}>" if settings.get("log_channel_id") else "_Not set_"

        embed.add_field(name="Default Event Channel", value=evt_ch, inline=True)
        embed.add_field(name="Log Channel",           value=log_ch, inline=True)
        embed.add_field(name="Attendance Threshold",  value=f"{settings.get('attendance_threshold', 75)}%", inline=True)
        embed.add_field(name="Default Tanks",         value=str(settings.get("default_max_tanks",   2)),  inline=True)
        embed.add_field(name="Default Healers",       value=str(settings.get("default_max_healers", 5)),  inline=True)
        embed.add_field(name="Default DPS",           value=str(settings.get("default_max_dps",    13)), inline=True)
        embed.add_field(name="Timezone",              value=settings.get("timezone", "America/New_York"),  inline=True)
        embed.add_field(name="Database",              value=f"`{config.DATABASE_PATH}`", inline=True)
        embed.add_field(name="Bot Version",           value=f"`v{config.VERSION}`", inline=True)

        if channels:
            ch_lines = []
            for ch in channels:
                tag = " ⭐" if ch["channel_id"] == default_id else ""
                ch_lines.append(f"<#{ch['channel_id']}> {ch['label']}{tag}")
            embed.add_field(
                name=f"Event Channels ({len(channels)})",
                value="\n".join(ch_lines),
                inline=False,
            )
        else:
            embed.add_field(
                name="Event Channels",
                value="_None configured – use `/admin add_event_channel`_",
                inline=False,
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── Permissions list ───────────────────────────────────────────────────────

    @admin_group.command(name="list_permissions", description="Show members with bot permissions")
    async def list_permissions(self, interaction: discord.Interaction) -> None:
        if not await is_admin(interaction):
            await interaction.response.send_message(
                embed=embeds.error_embed("Permission Denied", "Only server admins can view permissions."),
                ephemeral=True,
            )
            return

        from database.queries import _fetchall
        rows = await _fetchall(
            config.DATABASE_PATH,
            "SELECT discord_id, role FROM permissions WHERE guild_id=? ORDER BY role",
            (interaction.guild_id,),
        )

        embed = discord.Embed(title="🔐  Bot Permissions", color=0x3498DB)
        if not rows:
            embed.description = "No bot-level permissions set.  Server administrators have full access."
        else:
            for row in rows:
                member = interaction.guild.get_member(row["discord_id"])
                name = member.mention if member else f"<@{row['discord_id']}>"
                embed.add_field(
                    name=name,
                    value=row["role"].replace("_", " ").title(),
                    inline=True,
                )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── Data export ────────────────────────────────────────────────────────────

    @admin_group.command(name="export_data", description="Export all guild data as JSON")
    async def export_data(self, interaction: discord.Interaction) -> None:
        if not await is_admin(interaction):
            await interaction.response.send_message(
                embed=embeds.error_embed("Permission Denied", "Only server admins can export data."),
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        from database.queries import _fetchall
        guild_id = interaction.guild_id

        data = {
            "guild_id": guild_id,
            "exported_at": __import__("datetime").datetime.utcnow().isoformat(),
            "settings":   await _fetchall(config.DATABASE_PATH,
                              "SELECT * FROM guild_settings WHERE guild_id=?", (guild_id,)),
            "characters": await _fetchall(config.DATABASE_PATH,
                              "SELECT * FROM characters WHERE guild_id=?", (guild_id,)),
            "events":     await _fetchall(config.DATABASE_PATH,
                              "SELECT * FROM events WHERE guild_id=?", (guild_id,)),
            "signups":    await _fetchall(config.DATABASE_PATH,
                              "SELECT s.* FROM signups s JOIN events e ON s.event_id=e.event_id WHERE e.guild_id=?",
                              (guild_id,)),
            "attendance": await _fetchall(config.DATABASE_PATH,
                              "SELECT a.* FROM attendance a JOIN events e ON a.event_id=e.event_id WHERE e.guild_id=?",
                              (guild_id,)),
            "absences":   await _fetchall(config.DATABASE_PATH,
                              "SELECT * FROM absences WHERE guild_id=?", (guild_id,)),
        }

        json_bytes = json.dumps(data, indent=2, default=str).encode()
        file = discord.File(io.BytesIO(json_bytes), filename=f"raidbot_export_{guild_id}.json")
        await interaction.followup.send(
            embed=embeds.success_embed("Data Exported", "Your guild data export is attached."),
            file=file,
            ephemeral=True,
        )

    # ── Sync commands (dev utility) ────────────────────────────────────────────

    @admin_group.command(name="sync", description="Sync slash commands to this server (admin only)")
    async def sync_commands(self, interaction: discord.Interaction) -> None:
        if not await is_admin(interaction):
            await interaction.response.send_message(
                embed=embeds.error_embed("Permission Denied", "Only server admins can sync commands."),
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        guild = discord.Object(id=interaction.guild_id)
        self.bot.tree.copy_global_to(guild=guild)
        synced = await self.bot.tree.sync(guild=guild)
        await interaction.followup.send(
            embed=embeds.success_embed("Commands Synced", f"Synced **{len(synced)}** commands to this server."),
            ephemeral=True,
        )

    # ── Restart ────────────────────────────────────────────────────────────────

    @admin_group.command(name="restart", description="Restart the bot process (admin only)")
    async def restart(self, interaction: discord.Interaction) -> None:
        if not await is_admin(interaction):
            await interaction.response.send_message(
                embed=embeds.error_embed("Permission Denied", "Only server admins can restart the bot."),
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            embed=embeds.warning_embed("Restarting…", "The bot is restarting.  It will be back online in a few seconds."),
            ephemeral=False,   # Visible so the guild knows what's happening
        )
        log.info("Restart requested by %s (%d)", interaction.user, interaction.user.id)
        # Small delay so the message is sent before the process dies
        import asyncio
        await asyncio.sleep(1)
        await self.bot.do_restart()

    # ── Update & Restart ───────────────────────────────────────────────────────

    @admin_group.command(name="update", description="Pull latest code from git and restart (admin only)")
    async def update(self, interaction: discord.Interaction) -> None:
        if not await is_admin(interaction):
            await interaction.response.send_message(
                embed=embeds.error_embed("Permission Denied", "Only server admins can update the bot."),
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=False)  # Visible so the guild sees the update
        log.info("Update requested by %s (%d)", interaction.user, interaction.user.id)

        success, output = await self.bot.do_update()

        # Truncate output if too long for Discord
        if len(output) > 1800:
            output = output[:1800] + "\n…(truncated)"

        if not success:
            await interaction.followup.send(
                embed=embeds.error_embed(
                    "Update Failed",
                    f"**git pull** returned an error:\n```\n{output}\n```\n"
                    f"The bot has **not** been restarted.",
                )
            )
            return

        already_up_to_date = "already up to date" in output.lower()
        if already_up_to_date:
            await interaction.followup.send(
                embed=embeds.info_embed(
                    "Already Up to Date",
                    f"```\n{output}\n```\nNo changes pulled — the bot will **not** restart.",
                )
            )
            return

        await interaction.followup.send(
            embed=embeds.success_embed(
                "Update Successful – Restarting…",
                f"```\n{output}\n```\nNew code pulled successfully.  Restarting now…",
            )
        )
        import asyncio
        await asyncio.sleep(1)
        await self.bot.do_restart()


    # ── Member audit (unregistered) ────────────────────────────────────────────

    @admin_group.command(
        name="unregistered",
        description="List guild members who have not registered any characters",
    )
    async def unregistered_members(self, interaction: discord.Interaction) -> None:
        if not await is_admin(interaction):
            await interaction.response.send_message(
                embed=embeds.error_embed("Permission Denied", "Only server admins can run a member audit."),
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        unregistered = await queries.get_unregistered_members(
            config.DATABASE_PATH, interaction.guild_id
        )

        if not unregistered:
            await interaction.followup.send(
                embed=embeds.success_embed(
                    "All Clear!",
                    "Every non-bot member in this server has at least one character registered.",
                ),
                ephemeral=True,
            )
            return

        # Build embed — Discord limits fields to 25, so paginate the list into chunks
        embed = discord.Embed(
            title=f"👤  Unregistered Members — {len(unregistered)} found",
            description=(
                f"The following **{len(unregistered)}** member(s) are in the server "
                f"but have **no characters registered**."
            ),
            color=0xE67E22,
        )

        # Build a plain text list, mention by Discord ID
        lines = []
        for m in unregistered:
            display = m.get("display_name") or m.get("username") or f"<@{m['discord_id']}>"
            lines.append(f"<@{m['discord_id']}> — {display}")

        # Split into chunks of 20 per field to stay under Discord limits
        chunk_size = 20
        for i in range(0, min(len(lines), 100), chunk_size):
            chunk = lines[i:i + chunk_size]
            embed.add_field(
                name="\u200b",
                value="\n".join(chunk),
                inline=False,
            )

        if len(unregistered) > 100:
            embed.set_footer(text=f"Showing first 100 of {len(unregistered)}. Check the web admin panel for the full list.")

        await interaction.followup.send(embed=embed, ephemeral=True)
        log.info(
            "Member audit by %s: %d unregistered member(s) in guild %d",
            interaction.user, len(unregistered), interaction.guild_id,
        )

    # ── Admin character management ─────────────────────────────────────────────

    char_admin_group = app_commands.Group(
        name="character",
        description="Admin tools for managing guild characters",
        parent=admin_group,
    )

    @char_admin_group.command(name="list", description="List all registered characters in this server")
    async def char_admin_list(self, interaction: discord.Interaction) -> None:
        if not await is_admin(interaction):
            await interaction.response.send_message(
                embed=embeds.error_embed("Permission Denied", "Only server admins can use this command."),
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        all_chars = await queries.get_all_guild_characters(config.DATABASE_PATH, interaction.guild_id)

        if not all_chars:
            await interaction.followup.send(
                embed=embeds.info_embed("No Characters", "No characters have been registered in this server yet."),
                ephemeral=True,
            )
            return

        # Group by class
        by_class: dict[str, list[dict]] = {}
        for char in all_chars:
            by_class.setdefault(char["char_class"], []).append(char)

        embed = discord.Embed(
            title=f"📋  Guild Characters  ({len(all_chars)} registered)",
            color=0x3498DB,
        )

        for cls in sorted(by_class.keys()):
            chars = by_class[cls]
            lines = []
            for char in chars:
                member = interaction.guild.get_member(char["discord_id"])
                owner = member.mention if member else f"<@{char['discord_id']}>"
                spec = char["main_spec"]
                if char.get("off_spec"):
                    spec += f"/{char['off_spec']}"
                ilvl_tag = f" · **{char['ilvl']}** ilvl" if char.get("ilvl") else ""
                main_tag = " ⭐" if char.get("is_main") else ""
                rio_tag  = f" · [rio]({char['raiderio_url']})" if char.get("raiderio_url") else ""
                lines.append(f"**{char['char_name']}**{main_tag} — {spec}{ilvl_tag}{rio_tag} ({owner})")

            embed.add_field(
                name=f"{cls}  ({len(chars)})",
                value="\n".join(lines),
                inline=False,
            )

        embed.set_footer(text=f"⭐ = main  ·  Total: {len(all_chars)} characters across {len(by_class)} classes")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @char_admin_group.command(name="view", description="View a character's full profile in a detailed embed")
    @app_commands.describe(char_name="Character name to look up (searches all guild members)")
    async def char_admin_view(self, interaction: discord.Interaction, char_name: str) -> None:
        if not await is_admin(interaction):
            await interaction.response.send_message(
                embed=embeds.error_embed("Permission Denied", "Only server admins can use this command."),
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        char = await queries.get_guild_character_by_name(
            config.DATABASE_PATH, interaction.guild_id, char_name
        )
        if not char:
            await interaction.followup.send(
                embed=embeds.error_embed("Not Found", f"No character named **{char_name}** found in this server."),
                ephemeral=True,
            )
            return

        member = interaction.guild.get_member(char["discord_id"])
        owner_name = member.display_name if member else f"<@{char['discord_id']}>"

        color = CLASS_COLORS.get(char["char_class"], 0x3498DB)
        embed = discord.Embed(
            title=f"{char['char_name']}  {'⭐' if char.get('is_main') else ''}",
            color=color,
        )
        if member:
            embed.set_author(name=owner_name, icon_url=member.display_avatar.url)
        else:
            embed.set_author(name=owner_name)

        if char.get("avatar_url"):
            embed.set_thumbnail(url=char["avatar_url"])

        # Core fields
        embed.add_field(name="Class",     value=char["char_class"], inline=True)
        embed.add_field(name="Main Spec", value=char["main_spec"],  inline=True)
        if char.get("off_spec"):
            embed.add_field(name="Off Spec", value=char["off_spec"], inline=True)
        if char.get("ilvl"):
            embed.add_field(name="Item Level", value=str(char["ilvl"]), inline=True)
        if char.get("race"):
            embed.add_field(name="Race", value=char["race"], inline=True)
        if char.get("faction"):
            embed.add_field(name="Faction", value=char["faction"], inline=True)

        # Realm / region
        if char.get("realm"):
            realm_str = char["realm"].replace("-", " ").title()
            if char.get("region"):
                realm_str += f"  ({char['region'].upper()})"
            embed.add_field(name="Realm", value=realm_str, inline=True)

        # Professions
        if char.get("professions"):
            embed.add_field(name="Professions", value=char["professions"], inline=False)

        # Progression
        if char.get("progression"):
            embed.add_field(name="Raid Progression", value=char["progression"], inline=False)

        # Notes
        if char.get("notes"):
            embed.add_field(name="Notes", value=char["notes"], inline=False)

        # Raider.IO link
        if char.get("raiderio_url"):
            embed.add_field(name="Raider.IO", value=f"[View Profile]({char['raiderio_url']})", inline=True)

        embed.set_footer(text=f"Registered by {owner_name}")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @char_admin_group.command(name="edit", description="Edit any guild member's character (admin override)")
    @app_commands.describe(
        member="The member who owns the character",
        char_name="Name of the character to edit",
        spec="New main spec",
        off_spec="New off spec",
        ilvl="New item level",
        professions="Professions (comma-separated)",
        progression="Raid progression (e.g. 8/8 M)",
        raiderio_url="Raider.IO profile URL",
        notes="Officer notes for this character",
    )
    async def char_admin_edit(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        char_name: str,
        spec: Optional[str] = None,
        off_spec: Optional[str] = None,
        ilvl: Optional[int] = None,
        professions: Optional[str] = None,
        progression: Optional[str] = None,
        raiderio_url: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> None:
        if not await is_admin(interaction):
            await interaction.response.send_message(
                embed=embeds.error_embed("Permission Denied", "Only server admins can use this command."),
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        char = await queries.get_character(config.DATABASE_PATH, member.id, interaction.guild_id, char_name)
        if not char:
            await interaction.followup.send(
                embed=embeds.error_embed("Not Found", f"**{member.display_name}** has no character named **{char_name}**."),
                ephemeral=True,
            )
            return

        updates: dict = {}

        if spec:
            validated = validate_spec(char["char_class"], spec)
            if not validated:
                spec_list = ", ".join(ALL_SPECS.get(char["char_class"], []))
                await interaction.followup.send(
                    embed=embeds.error_embed("Invalid Spec", f"**{spec}** is not valid for {char['char_class']}.\nValid specs: {spec_list}"),
                    ephemeral=True,
                )
                return
            updates["main_spec"] = validated

        if off_spec:
            validated_off = validate_spec(char["char_class"], off_spec)
            if not validated_off:
                spec_list = ", ".join(ALL_SPECS.get(char["char_class"], []))
                await interaction.followup.send(
                    embed=embeds.error_embed("Invalid Off-Spec", f"**{off_spec}** is not valid for {char['char_class']}.\nValid specs: {spec_list}"),
                    ephemeral=True,
                )
                return
            updates["off_spec"] = validated_off

        if ilvl is not None:
            if not validate_ilvl(ilvl):
                await interaction.followup.send(
                    embed=embeds.error_embed("Invalid Item Level", "Item level must be between 1 and 700."),
                    ephemeral=True,
                )
                return
            updates["ilvl"] = ilvl

        if professions is not None:
            updates["professions"] = professions
        if progression is not None:
            updates["progression"] = progression
        if notes is not None:
            updates["notes"] = notes
        if raiderio_url is not None:
            # Basic sanity check — must look like a raider.io URL
            if raiderio_url and not raiderio_url.startswith("https://raider.io/"):
                await interaction.followup.send(
                    embed=embeds.error_embed("Invalid URL", "Raider.IO URLs must start with `https://raider.io/`."),
                    ephemeral=True,
                )
                return
            updates["raiderio_url"] = raiderio_url

        if not updates:
            await interaction.followup.send(
                embed=embeds.warning_embed("Nothing to Change", "Provide at least one field to update."),
                ephemeral=True,
            )
            return

        await queries.update_character(config.DATABASE_PATH, member.id, interaction.guild_id, char_name, **updates)

        changed = ", ".join(k.replace("_", " ").title() for k in updates)
        await interaction.followup.send(
            embed=embeds.success_embed(
                "Character Updated",
                f"**{char['char_name']}** ({member.mention}) updated.\nFields changed: {changed}",
            ),
            ephemeral=True,
        )


    @char_admin_group.command(
        name="sync_raiderio",
        description="Bulk-sync every registered guild character with Raider.IO (ilvl, avatar, progression)",
    )
    async def sync_raiderio(self, interaction: discord.Interaction) -> None:
        if not await is_admin(interaction):
            await interaction.response.send_message(
                embed=embeds.error_embed("Permission Denied", "Only server admins can sync Raider.IO data."),
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        chars = await queries.get_guild_characters_for_sync(config.DATABASE_PATH, interaction.guild_id)
        if not chars:
            await interaction.followup.send(
                embed=embeds.warning_embed(
                    "Nothing to Sync",
                    "No characters have a realm + region saved.  "
                    "Members must register with `/char add realm:` or `/char link` so the bot knows where to look.",
                ),
                ephemeral=True,
            )
            return

        from utils import raiderio as rio
        import asyncio
        import re as _re

        updated: list[str] = []
        skipped: list[str] = []
        failed:  list[str] = []

        # Post a live-updating progress message
        progress_msg = await interaction.followup.send(
            embed=embeds.info_embed(
                "Syncing with Raider.IO…",
                f"Starting sync for **{len(chars)}** character(s).  This may take a moment.",
            ),
            ephemeral=True,
        )

        for i, char in enumerate(chars, start=1):
            name   = char["char_name"]
            realm  = char["realm"]
            region = char["region"]

            # Characters linked via /char link or admin-edit have a raiderio_url
            # but may not have realm/region columns — parse them from the URL.
            if (not realm or not region) and char.get("raiderio_url"):
                parsed = rio.parse_url(char["raiderio_url"])
                if parsed:
                    region, realm, _ = parsed  # name from URL; use char_name for the query

            if not realm or not region:
                # No way to look this character up; skip silently
                skipped.append(name)
                continue

            # Edit progress embed every 5 characters so the admin can see it's working
            if i % 5 == 1 and i > 1:
                try:
                    await progress_msg.edit(
                        embed=embeds.info_embed(
                            "Syncing with Raider.IO…",
                            f"Progress: **{i - 1}/{len(chars)}** — last: {name}",
                        )
                    )
                except Exception:
                    pass

            rio_data = await rio.client.get_character(region, realm, name)
            if rio_data is None:
                failed.append(name)
                await asyncio.sleep(0.5)
                continue

            # ── Extract fields ───────────────────────────────────────────────
            ilvl = (rio_data.get("gear") or {}).get("item_level_equipped") or None
            avatar_url = rio_data.get("thumbnail_url") or None

            # Build the canonical Raider.IO profile URL
            realm_slug = realm.lower()
            realm_slug = _re.sub(r"'", "", realm_slug)
            realm_slug = _re.sub(r"[^a-z0-9 \-]", "", realm_slug)
            realm_slug = realm_slug.replace(" ", "-")
            raiderio_url = f"https://raider.io/characters/{region}/{realm_slug}/{name.lower()}"

            # Pull progression summary from the most recent raid tier
            progression: Optional[str] = None
            raid_prog = rio_data.get("raid_progression") or {}
            if raid_prog:
                first_tier = next(iter(raid_prog.values()), {})
                summary = first_tier.get("summary")
                if summary:
                    progression = summary

            # ── Persist to DB ────────────────────────────────────────────────
            updates: dict = {}
            if ilvl is not None:
                updates["ilvl"] = int(ilvl)
            if avatar_url:
                updates["avatar_url"] = avatar_url
            updates["raiderio_url"] = raiderio_url
            if progression:
                updates["progression"] = progression

            if updates:
                await queries.update_character(
                    config.DATABASE_PATH,
                    char["discord_id"],
                    interaction.guild_id,
                    name,
                    **updates,
                )
                updated.append(name)
            else:
                skipped.append(name)

            # Be polite to the Raider.IO API — no auth key means rate limits apply
            await asyncio.sleep(0.5)

        # ── Summary embed ────────────────────────────────────────────────────
        lines: list[str] = []
        if updated:
            lines.append(f"**{len(updated)} updated:** {', '.join(updated)}")
        if skipped:
            lines.append(f"**{len(skipped)} skipped** (no data returned): {', '.join(skipped)}")
        if failed:
            lines.append(f"**{len(failed)} not found on Raider.IO:** {', '.join(failed)}")

        summary = "\n\n".join(lines) or "No characters were processed."
        await progress_msg.edit(
            embed=embeds.success_embed(
                f"Raider.IO Sync Complete  ({len(updated)}/{len(chars)} updated)",
                summary,
            )
        )
        log.info(
            "Raider.IO bulk sync by %s: %d updated, %d skipped, %d failed",
            interaction.user,
            len(updated),
            len(skipped),
            len(failed),
        )

    # ── Character audit ────────────────────────────────────────────────────────

    @char_admin_group.command(
        name="audit",
        description="Find characters owned by users who left the server and optionally delete them",
    )
    async def char_audit(self, interaction: discord.Interaction) -> None:
        if not await is_admin(interaction):
            await interaction.response.send_message(
                embed=embeds.error_embed("Permission Denied", "Only server admins can run a character audit."),
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        all_chars = await queries.get_all_guild_characters(config.DATABASE_PATH, interaction.guild_id)
        if not all_chars:
            await interaction.followup.send(
                embed=embeds.info_embed("No Characters", "No characters are registered in this server."),
                ephemeral=True,
            )
            return

        # Check each unique owner against the current member list
        orphans: list[dict] = []
        checked: set[int] = set()
        for char in all_chars:
            uid = char["discord_id"]
            member = interaction.guild.get_member(uid)
            if member is None and uid not in checked:
                # Not in cache — try a live fetch before marking as gone
                try:
                    member = await interaction.guild.fetch_member(uid)
                except discord.NotFound:
                    pass  # Confirmed not in server
                except Exception:
                    pass
            checked.add(uid)
            if member is None:
                orphans.append(char)

        if not orphans:
            await interaction.followup.send(
                embed=embeds.success_embed(
                    "All Clear!",
                    f"All **{len(all_chars)}** registered character(s) belong to current server members.\n"
                    f"No cleanup needed.",
                ),
                ephemeral=True,
            )
            return

        # Group orphans by owner for the embed
        by_user: dict[int, list[dict]] = {}
        for char in orphans:
            by_user.setdefault(char["discord_id"], []).append(char)

        embed = discord.Embed(
            title=f"🔍  Character Audit — {len(orphans)} Orphaned Character(s) Found",
            description=(
                f"The following **{len(orphans)}** character(s) are registered to Discord users "
                f"who are **no longer in this server**.\n\n"
                f"Press a 🗑️ button to start the deletion flow for that character."
            ),
            color=0xE67E22,
        )
        for uid, chars in by_user.items():
            lines = []
            for c in chars:
                ilvl_tag = f" · {c['ilvl']} ilvl" if c.get("ilvl") else ""
                main_tag = " ⭐" if c.get("is_main") else ""
                lines.append(f"**{c['char_name']}**{main_tag} — {c['char_class']} {c['main_spec']}{ilvl_tag}")
            embed.add_field(
                name=f"<@{uid}>  (left server)",
                value="\n".join(lines),
                inline=False,
            )

        if len(orphans) > 20:
            embed.set_footer(
                text=f"Showing first 20 of {len(orphans)} orphaned characters. "
                     f"Re-run /admin character audit after cleaning up to see the rest."
            )

        await interaction.followup.send(
            embed=embed,
            view=_AuditView(interaction.guild_id, orphans),
            ephemeral=True,
        )
        log.info(
            "Character audit by %s: %d total chars, %d orphaned",
            interaction.user, len(all_chars), len(orphans),
        )


# ── Character audit UI views ───────────────────────────────────────────────────
# Placed outside the cog class so discord.py can register the button decorators.

class _AuditView(discord.ui.View):
    """Main audit result — one 🗑️ button per orphaned character (up to 20)."""

    def __init__(self, guild_id: int, orphans: list[dict]) -> None:
        super().__init__(timeout=300)
        for char in orphans[:20]:
            self.add_item(_OrphanDeleteButton(guild_id, char["discord_id"], char["char_name"]))


class _OrphanDeleteButton(discord.ui.Button):
    """Represents a single orphaned character on the audit list."""

    def __init__(self, guild_id: int, discord_id: int, char_name: str) -> None:
        super().__init__(label=char_name, emoji="🗑️", style=discord.ButtonStyle.danger)
        self.guild_id   = guild_id
        self.discord_id = discord_id
        self.char_name  = char_name

    async def callback(self, interaction: discord.Interaction) -> None:
        view = _DeleteConfirmView(self.guild_id, self.discord_id, self.char_name)
        await interaction.response.send_message(
            embed=embeds.warning_embed(
                "Are you sure?",
                f"**{self.char_name}** is registered to a Discord user who has left the server.\n\n"
                f"Deleting it will permanently remove the character. **There is no undo.**",
            ),
            view=view,
            ephemeral=True,
        )


class _DeleteConfirmView(discord.ui.View):
    """Stage 2: 'Are you sure?' — one more click before the real gate."""

    def __init__(self, guild_id: int, discord_id: int, char_name: str) -> None:
        super().__init__(timeout=60)
        self.guild_id   = guild_id
        self.discord_id = discord_id
        self.char_name  = char_name

    @discord.ui.button(label="Yes, delete it", emoji="✅", style=discord.ButtonStyle.danger)
    async def yes(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        view = _DeleteDoubleConfirmView(self.guild_id, self.discord_id, self.char_name)
        await interaction.response.edit_message(
            embed=discord.Embed(
                title="⚠️  ARE YOU REALLY SURE?",
                description=(
                    f"You are about to **permanently delete** `{self.char_name}` "
                    f"from the guild registry.\n\n"
                    f"There is **no undo.** The player would need to re-register from scratch."
                ),
                color=0xFF0000,
            ),
            view=view,
        )

    @discord.ui.button(label="Cancel", emoji="❌", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        self.stop()
        await interaction.response.edit_message(
            embed=embeds.info_embed("Cancelled", f"**{self.char_name}** was not deleted."),
            view=None,
        )


class _DeleteDoubleConfirmView(discord.ui.View):
    """Stage 3: the final 'ARE YOU REALLY SURE?' gate before actual deletion."""

    def __init__(self, guild_id: int, discord_id: int, char_name: str) -> None:
        super().__init__(timeout=60)
        self.guild_id   = guild_id
        self.discord_id = discord_id
        self.char_name  = char_name

    @discord.ui.button(label="YES, DELETE FOREVER", emoji="💀", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await queries.remove_character(
            config.DATABASE_PATH, self.discord_id, self.guild_id, self.char_name
        )
        self.stop()
        await interaction.response.edit_message(
            embed=embeds.success_embed(
                "Character Deleted",
                f"**{self.char_name}** has been permanently removed from the guild registry.",
            ),
            view=None,
        )
        log.info(
            "Admin %s permanently deleted orphaned character %r (owner discord_id=%d)",
            interaction.user, self.char_name, self.discord_id,
        )

    @discord.ui.button(label="No, abort!", emoji="🛡️", style=discord.ButtonStyle.secondary)
    async def abort(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        self.stop()
        await interaction.response.edit_message(
            embed=embeds.info_embed("Aborted", f"**{self.char_name}** was not deleted."),
            view=None,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Admin(bot))
