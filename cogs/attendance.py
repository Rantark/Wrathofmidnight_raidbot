"""
Attendance tracking and absence management cog.
Commands: /attendance mark, view, report
           /absence request, list
"""

from __future__ import annotations

import csv
import io
import logging
from datetime import datetime, timedelta
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

import config
from database import queries
from utils import embeds
from utils.validators import validate_date

log = logging.getLogger(__name__)


async def is_raid_leader(interaction: discord.Interaction) -> bool:
    if interaction.user.guild_permissions.administrator:
        return True
    role = await queries.get_permission(
        config.DATABASE_PATH, interaction.guild_id, interaction.user.id
    )
    return role in ("officer", "raid_leader")


# ── Attendance marking view ───────────────────────────────────────────────────

class AttendanceMarkView(discord.ui.View):
    """
    Interactive view for marking attendance.
    The raid leader selects each signup and marks them present/absent/late/excused.
    """

    def __init__(
        self,
        bot: commands.Bot,
        event_id: int,
        signups: list[dict],
        marked_by: int,
    ) -> None:
        super().__init__(timeout=600)
        self.bot = bot
        self.event_id = event_id
        self.signups = [s for s in signups if s["signup_status"] in ("confirmed", "bench")]
        self.marked_by = marked_by
        self.results: dict[int, str] = {}  # discord_id -> status

        # Build a select menu of members
        if self.signups:
            options = [
                discord.SelectOption(
                    label=s["char_name"],
                    value=str(s["discord_id"]),
                    description=f"{s['char_class']} – {s['signup_status']}",
                )
                for s in self.signups[:25]  # Discord limit
            ]
            select = discord.ui.Select(
                placeholder="Select a member to mark…",
                options=options,
                custom_id="attendance_select",
            )
            select.callback = self.select_callback
            self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction) -> None:
        discord_id = int(interaction.data["values"][0])
        signup = next((s for s in self.signups if s["discord_id"] == discord_id), None)
        if not signup:
            await interaction.response.send_message("Not found.", ephemeral=True)
            return

        view = SingleMarkView(self, discord_id, signup["char_name"])
        await interaction.response.send_message(
            f"Mark attendance for **{signup['char_name']}**:", view=view, ephemeral=True
        )

    @discord.ui.button(label="✅ Finish & Save All", style=discord.ButtonStyle.success, row=4)
    async def finish(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await interaction.response.defer(ephemeral=True)

        # Mark those who weren't explicitly marked as absent
        for s in self.signups:
            did = s["discord_id"]
            status = self.results.get(did, "absent")
            await queries.upsert_attendance(
                config.DATABASE_PATH,
                self.event_id,
                did,
                s["char_name"],
                status,
                self.marked_by,
            )

        # Also mark declined/tentative absences
        await queries.complete_event(config.DATABASE_PATH, self.event_id)

        count = len(self.signups)
        present = sum(1 for v in self.results.values() if v in ("present", "late"))
        await interaction.followup.send(
            embed=embeds.success_embed(
                "Attendance Saved",
                f"Marked {count} members.  **{present}** present / **{count-present}** absent.",
            ),
            ephemeral=True,
        )
        self.stop()


class SingleMarkView(discord.ui.View):
    """Buttons to mark a single member's attendance status."""

    def __init__(self, parent: AttendanceMarkView, discord_id: int, char_name: str) -> None:
        super().__init__(timeout=120)
        self.parent = parent
        self.discord_id = discord_id
        self.char_name = char_name

    async def _mark(self, interaction: discord.Interaction, status: str) -> None:
        self.parent.results[self.discord_id] = status
        await interaction.response.edit_message(
            content=f"Marked **{self.char_name}** as **{status}**.", view=None
        )
        self.stop()

    @discord.ui.button(label="✅ Present",  style=discord.ButtonStyle.success)
    async def present(self, i: discord.Interaction, _: discord.ui.Button) -> None:
        await self._mark(i, "present")

    @discord.ui.button(label="⏰ Late",    style=discord.ButtonStyle.primary)
    async def late(self, i: discord.Interaction, _: discord.ui.Button) -> None:
        await self._mark(i, "late")

    @discord.ui.button(label="🔵 Excused", style=discord.ButtonStyle.secondary)
    async def excused(self, i: discord.Interaction, _: discord.ui.Button) -> None:
        await self._mark(i, "excused")

    @discord.ui.button(label="❌ Absent",  style=discord.ButtonStyle.danger)
    async def absent(self, i: discord.Interaction, _: discord.ui.Button) -> None:
        await self._mark(i, "absent")


# ══════════════════════════════════════════════════════════════════════════════
# Attendance Cog
# ══════════════════════════════════════════════════════════════════════════════

class Attendance(commands.Cog):
    """Commands for attendance tracking and absence management."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ── /attendance ────────────────────────────────────────────────────────────
    att_group = app_commands.Group(name="attendance", description="Attendance tracking commands")

    @att_group.command(name="mark", description="Mark attendance for an event (raid leader only)")
    @app_commands.describe(event_id="The event ID to mark attendance for")
    async def attendance_mark(self, interaction: discord.Interaction, event_id: int) -> None:
        await interaction.response.defer(ephemeral=True)

        if not await is_raid_leader(interaction):
            await interaction.followup.send(
                embed=embeds.error_embed("Permission Denied", "Only raid leaders can mark attendance."),
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

        signups = await queries.get_event_signups(config.DATABASE_PATH, event_id)
        active = [s for s in signups if s["signup_status"] in ("confirmed", "bench")]
        if not active:
            await interaction.followup.send(
                embed=embeds.warning_embed("No Signups", "There are no confirmed/bench signups to mark."),
                ephemeral=True,
            )
            return

        view = AttendanceMarkView(self.bot, event_id, signups, interaction.user.id)
        await interaction.followup.send(
            embed=embeds.info_embed(
                f"Marking Attendance: {event['event_name']}",
                "Select members from the dropdown and mark their attendance.\n"
                "When finished, click **Finish & Save All**.",
            ),
            view=view,
            ephemeral=True,
        )

    @att_group.command(name="view", description="View attendance statistics for a member")
    @app_commands.describe(member="Member to view (defaults to yourself)")
    async def attendance_view(
        self, interaction: discord.Interaction, member: Optional[discord.Member] = None
    ) -> None:
        await interaction.response.defer()
        target = member or interaction.user
        records = await queries.get_user_attendance(
            config.DATABASE_PATH, target.id, interaction.guild_id
        )
        recent = await queries.get_user_attendance(
            config.DATABASE_PATH, target.id, interaction.guild_id, days=30
        )

        stats = queries.compute_attendance_stats(records)
        stats_30d = queries.compute_attendance_stats(recent)
        stats["pct_30d"] = stats_30d["pct_all_time"]

        # Build history emojis for last 10
        history_map = {"present": "✅", "late": "⏰", "absent": "❌", "excused": "🔵"}
        history = [history_map.get(r["status"], "❓") for r in records[-10:]]

        embed = embeds.build_attendance_embed(target.display_name, stats, history)
        await interaction.followup.send(embed=embed)

    @att_group.command(name="report", description="Generate an attendance report for all members")
    @app_commands.describe(
        start_date="Start date (YYYY-MM-DD, optional)",
        end_date="End date (YYYY-MM-DD, optional)",
        export_csv="Export as CSV file?",
    )
    async def attendance_report(
        self,
        interaction: discord.Interaction,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        export_csv: bool = False,
    ) -> None:
        await interaction.response.defer()

        if not await is_raid_leader(interaction):
            await interaction.followup.send(
                embed=embeds.error_embed("Permission Denied", "Only raid leaders can generate reports."),
                ephemeral=True,
            )
            return

        # Pull low-attendance members
        settings = await queries.get_guild_settings(config.DATABASE_PATH, interaction.guild_id)
        threshold = settings.get("attendance_threshold", 75)
        low_members = await queries.get_low_attendance_members(
            config.DATABASE_PATH, interaction.guild_id, threshold
        )

        embed = discord.Embed(
            title="📊  Attendance Report",
            description=f"Members below **{threshold}%** attendance threshold:",
            color=0xE74C3C if low_members else 0x2ECC71,
        )

        if not low_members:
            embed.description = f"✅ All members are above the **{threshold}%** threshold!"
        else:
            for row in low_members:
                denom = row["total"] - row["excused"]
                pct = (row["attended"] / denom * 100) if denom > 0 else 0
                try:
                    member = interaction.guild.get_member(row["discord_id"])
                    name = member.display_name if member else f"<@{row['discord_id']}>"
                except Exception:
                    name = f"<@{row['discord_id']}>"
                embed.add_field(
                    name=name,
                    value=f"{row['attended']}/{denom}  ({pct:.1f}%)",
                    inline=True,
                )

        if export_csv:
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["Member ID", "Member Name", "Attended", "Total", "Excused", "Percentage"])
            for row in low_members:
                denom = row["total"] - row["excused"]
                pct = (row["attended"] / denom * 100) if denom > 0 else 0
                member = interaction.guild.get_member(row["discord_id"])
                name = member.display_name if member else str(row["discord_id"])
                writer.writerow([row["discord_id"], name, row["attended"], row["total"], row["excused"], f"{pct:.1f}"])
            output.seek(0)
            file = discord.File(io.BytesIO(output.read().encode()), filename="attendance_report.csv")
            await interaction.followup.send(embed=embed, file=file)
        else:
            await interaction.followup.send(embed=embed)

    @att_group.command(name="event", description="View attendance records for a specific event")
    @app_commands.describe(event_id="Event ID")
    async def attendance_event(self, interaction: discord.Interaction, event_id: int) -> None:
        await interaction.response.defer()

        if not await is_raid_leader(interaction):
            await interaction.followup.send(
                embed=embeds.error_embed("Permission Denied", "Only raid leaders can view event attendance."),
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

        records = await queries.get_event_attendance(config.DATABASE_PATH, event_id)
        if not records:
            await interaction.followup.send(
                embed=embeds.warning_embed("No Records", "Attendance has not been marked for this event yet."),
                ephemeral=True,
            )
            return

        status_emoji = {"present": "✅", "late": "⏰", "absent": "❌", "excused": "🔵"}
        embed = discord.Embed(
            title=f"📋  Attendance: {event['event_name']}",
            color=0x3498DB,
        )
        present = [r for r in records if r["status"] in ("present", "late")]
        absent  = [r for r in records if r["status"] == "absent"]
        excused = [r for r in records if r["status"] == "excused"]

        def fmt(rows: list[dict]) -> str:
            return "\n".join(
                f"{status_emoji.get(r['status'],'❓')} {r['char_name']}" for r in rows
            ) or "_None_"

        embed.add_field(name=f"✅ Present ({len(present)})", value=fmt(present), inline=True)
        embed.add_field(name=f"❌ Absent ({len(absent)})", value=fmt(absent), inline=True)
        embed.add_field(name=f"🔵 Excused ({len(excused)})", value=fmt(excused), inline=True)

        total = len(records)
        pct = len(present) / total * 100 if total else 0
        embed.set_footer(text=f"Overall attendance: {pct:.1f}%  •  {len(present)}/{total}")
        await interaction.followup.send(embed=embed)

    # ── /absence ───────────────────────────────────────────────────────────────
    absence_group = app_commands.Group(name="absence", description="Manage raid absences")

    @absence_group.command(name="request", description="Submit an absence for an upcoming event")
    @app_commands.describe(event_id="Event ID you will miss", reason="Reason for absence")
    async def absence_request(
        self, interaction: discord.Interaction, event_id: int, reason: str
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        event = await queries.get_event(config.DATABASE_PATH, event_id)
        if not event or event["guild_id"] != interaction.guild_id or event["status"] != "active":
            await interaction.followup.send(
                embed=embeds.error_embed("Not Found", f"No active event with ID `{event_id}`."),
                ephemeral=True,
            )
            return

        await queries.add_absence(
            config.DATABASE_PATH,
            interaction.user.id,
            interaction.guild_id,
            event_id,
            reason,
        )

        # Auto-mark as excused in attendance if signup exists
        signup = await queries.get_signup(config.DATABASE_PATH, event_id, interaction.user.id)
        if signup:
            await queries.upsert_attendance(
                config.DATABASE_PATH,
                event_id,
                interaction.user.id,
                signup["char_name"],
                "excused",
                None,
            )

        await interaction.followup.send(
            embed=embeds.success_embed(
                "Absence Submitted",
                f"Your absence for **{event['event_name']}** has been recorded and marked as excused.\n\n"
                f"**Reason:** {reason}",
            ),
            ephemeral=True,
        )

    @absence_group.command(name="list", description="View your submitted absences")
    async def absence_list(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        absences = await queries.get_user_absences(
            config.DATABASE_PATH, interaction.user.id, interaction.guild_id
        )
        if not absences:
            await interaction.followup.send(
                embed=embeds.info_embed("No Absences", "You have no submitted absences on record."),
                ephemeral=True,
            )
            return

        embed = discord.Embed(title="🔵  Your Submitted Absences", color=0x3498DB)
        for a in absences:
            event_label = f"{a.get('event_name', 'Unknown')} ({a.get('event_date', '?')})" \
                if a.get("event_name") else "General Absence"
            embed.add_field(
                name=event_label,
                value=f"**Reason:** {a['reason']}\n_Submitted: {a['submitted_at'][:10]}_",
                inline=False,
            )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @absence_group.command(name="event_list", description="View absences submitted for a specific event")
    @app_commands.describe(event_id="Event ID")
    async def absence_event_list(self, interaction: discord.Interaction, event_id: int) -> None:
        await interaction.response.defer(ephemeral=True)

        if not await is_raid_leader(interaction):
            await interaction.followup.send(
                embed=embeds.error_embed("Permission Denied", "Only raid leaders can view event absences."),
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

        absences = await queries.get_event_absences(config.DATABASE_PATH, event_id)
        embed = discord.Embed(
            title=f"🔵  Submitted Absences: {event['event_name']}",
            color=0x3498DB,
        )
        if not absences:
            embed.description = "No absences submitted for this event."
        else:
            for a in absences:
                member = interaction.guild.get_member(a["discord_id"])
                name = member.display_name if member else f"<@{a['discord_id']}>"
                embed.add_field(
                    name=name,
                    value=f"**Reason:** {a['reason']}\n_Submitted: {a['submitted_at'][:10]}_",
                    inline=False,
                )
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Attendance(bot))
