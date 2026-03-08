"""
Admin and configuration cog.
Commands: /admin set_raid_leader, remove_raid_leader, set_event_channel,
           roster_config, attendance_threshold, status, export_data
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


def is_admin(interaction: discord.Interaction) -> bool:
    return interaction.user.guild_permissions.administrator


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
        if not is_admin(interaction):
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
        if not is_admin(interaction):
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
    @app_commands.describe(channel="Channel where events will be posted")
    async def set_event_channel(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ) -> None:
        if not is_admin(interaction):
            await interaction.response.send_message(
                embed=embeds.error_embed("Permission Denied", "Only server admins can configure the bot."),
                ephemeral=True,
            )
            return

        await queries.get_guild_settings(config.DATABASE_PATH, interaction.guild_id)  # ensure row exists
        await queries.update_guild_setting(
            config.DATABASE_PATH, interaction.guild_id, "event_channel_id", channel.id
        )
        await interaction.response.send_message(
            embed=embeds.success_embed(
                "Channel Set",
                f"Events will now be posted in {channel.mention} by default.",
            ),
            ephemeral=True,
        )

    @admin_group.command(name="set_log_channel", description="Set the bot audit log channel")
    @app_commands.describe(channel="Channel for bot logs/audit messages")
    async def set_log_channel(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ) -> None:
        if not is_admin(interaction):
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
        if not is_admin(interaction):
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
        if not is_admin(interaction):
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

    # ── Status overview ────────────────────────────────────────────────────────

    @admin_group.command(name="status", description="View bot configuration for this server")
    async def status(self, interaction: discord.Interaction) -> None:
        if not is_admin(interaction):
            await interaction.response.send_message(
                embed=embeds.error_embed("Permission Denied", "Only server admins can view configuration."),
                ephemeral=True,
            )
            return

        settings = await queries.get_guild_settings(config.DATABASE_PATH, interaction.guild_id)
        embed = discord.Embed(title="⚙️  Bot Configuration", color=0x3498DB)

        evt_ch = f"<#{settings['event_channel_id']}>" if settings.get("event_channel_id") else "_Not set_"
        log_ch = f"<#{settings['log_channel_id']}>"   if settings.get("log_channel_id")   else "_Not set_"

        embed.add_field(name="Event Channel",         value=evt_ch, inline=True)
        embed.add_field(name="Log Channel",           value=log_ch, inline=True)
        embed.add_field(name="Attendance Threshold",  value=f"{settings.get('attendance_threshold', 75)}%", inline=True)
        embed.add_field(name="Default Tanks",         value=str(settings.get("default_max_tanks",   2)),  inline=True)
        embed.add_field(name="Default Healers",       value=str(settings.get("default_max_healers", 5)),  inline=True)
        embed.add_field(name="Default DPS",           value=str(settings.get("default_max_dps",    13)), inline=True)
        embed.add_field(name="Timezone",              value=settings.get("timezone", "America/New_York"),  inline=True)
        embed.add_field(name="Database",              value=f"`{config.DATABASE_PATH}`", inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── Permissions list ───────────────────────────────────────────────────────

    @admin_group.command(name="list_permissions", description="Show members with bot permissions")
    async def list_permissions(self, interaction: discord.Interaction) -> None:
        if not is_admin(interaction):
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
        if not is_admin(interaction):
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
        if not is_admin(interaction):
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


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Admin(bot))
