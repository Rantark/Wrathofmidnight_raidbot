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
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

import config
from database import queries
from utils import embeds
from utils.validators import validate_percentage

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

        import pytz
        try:
            pytz.timezone(timezone)
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

        await queries.get_guild_settings(config.DATABASE_PATH, interaction.guild_id)
        await queries.update_guild_setting(config.DATABASE_PATH, interaction.guild_id, "timezone", timezone)
        await interaction.response.send_message(
            embed=embeds.success_embed(
                "Timezone Updated",
                f"Server timezone is now **{timezone}**.\n"
                "All future event times will be displayed and scheduled in this timezone.",
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


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Admin(bot))
