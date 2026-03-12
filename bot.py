"""
Wrath of Midnight Raid Bot
Main entry point.  Loads cogs, initialises database, and starts the event loop.
"""

from __future__ import annotations

import asyncio
import logging
import logging.handlers
import os
import pathlib
import subprocess
import sys
from datetime import datetime, timedelta

import discord
from discord.ext import commands, tasks

import config
from database.db_setup import init_db
from database import queries

# ── Logging setup ─────────────────────────────────────────────────────────────

def setup_logging() -> None:
    log_dir = pathlib.Path("logs")
    log_dir.mkdir(exist_ok=True)

    fmt = logging.Formatter(
        "[%(asctime)s] [%(levelname)-8s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Rotating file handler – keeps 7 days of logs
    file_handler = logging.handlers.TimedRotatingFileHandler(
        log_dir / "raidbot.log",
        when="midnight",
        backupCount=7,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(file_handler)
    root.addHandler(console_handler)

    # Quiet down noisy discord.py internals
    logging.getLogger("discord.http").setLevel(logging.WARNING)
    logging.getLogger("discord.gateway").setLevel(logging.WARNING)


setup_logging()
log = logging.getLogger(__name__)

# ── Bot class ─────────────────────────────────────────────────────────────────

COGS = [
    "cogs.characters",
    "cogs.events",
    "cogs.attendance",
    "cogs.admin",
]


class RaidBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.members = True       # Required for member lookups
        intents.message_content = True

        super().__init__(
            command_prefix=config.COMMAND_PREFIX,
            intents=intents,
            help_command=None,       # We use slash commands; disable default help
        )

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    async def setup_hook(self) -> None:
        """Called once before the bot connects.  Load cogs and init DB."""
        log.info("Initialising database…")
        await init_db(config.DATABASE_PATH)

        log.info("Loading cogs…")
        for cog in COGS:
            try:
                await self.load_extension(cog)
                log.info("  ✓ %s", cog)
            except Exception as exc:
                log.exception("  ✗ Failed to load %s: %s", cog, exc)

        # Sync slash commands to the configured guild for instant availability.
        # Global sync can take up to an hour; guild sync is immediate.
        guild = discord.Object(id=config.GUILD_ID)
        self.tree.copy_global_to(guild=guild)
        synced = await self.tree.sync(guild=guild)
        log.info("Synced %d slash commands to guild %d", len(synced), config.GUILD_ID)

        # Start background tasks
        self.reminder_loop.start()
        self.auto_archive_loop.start()

    async def on_ready(self) -> None:
        log.info("=" * 60)
        log.info("Bot online: %s (ID: %s)", self.user, self.user.id)
        log.info("Version:  %s", config.VERSION)
        log.info("Guild:    %d", config.GUILD_ID)
        log.info("Database: %s", config.DATABASE_PATH)
        log.info("=" * 60)
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name=f"the raid calendar 📅  v{config.VERSION}",
            )
        )

    async def on_app_command_error(
        self,
        interaction: discord.Interaction,
        error: discord.app_commands.AppCommandError,
    ) -> None:
        log.exception("App command error for %s: %s", interaction.command, error)
        msg = "An unexpected error occurred.  Please try again or contact an officer."
        if isinstance(error, discord.app_commands.CommandOnCooldown):
            msg = f"Command on cooldown.  Try again in {error.retry_after:.1f}s."
        elif isinstance(error, discord.app_commands.MissingPermissions):
            msg = "You don't have permission to use this command."

        from utils.embeds import error_embed
        try:
            if interaction.response.is_done():
                await interaction.followup.send(embed=error_embed("Error", msg), ephemeral=True)
            else:
                await interaction.response.send_message(embed=error_embed("Error", msg), ephemeral=True)
        except Exception:
            pass

    # ── Background tasks ───────────────────────────────────────────────────────

    @tasks.loop(minutes=1)
    async def reminder_loop(self) -> None:
        """Fire any pending reminders every minute."""
        try:
            pending = await queries.get_pending_reminders(config.DATABASE_PATH)
            for reminder in pending:
                await self._fire_reminder(reminder)
        except Exception:
            log.exception("Error in reminder loop")

    async def _fire_reminder(self, reminder: dict) -> None:
        event = await queries.get_event(config.DATABASE_PATH, reminder["event_id"])
        if not event or event["status"] != "active":
            await queries.mark_reminder_sent(config.DATABASE_PATH, reminder["reminder_id"])
            return

        channel_id = event.get("channel_id")
        if not channel_id:
            await queries.mark_reminder_sent(config.DATABASE_PATH, reminder["reminder_id"])
            return

        channel = self.get_channel(channel_id)
        if not channel:
            await queries.mark_reminder_sent(config.DATABASE_PATH, reminder["reminder_id"])
            return

        label_map = {
            "24h": "24 hours",
            "2h":  "2 hours",
            "30m": "30 minutes",
            "5m":  "5 minutes",
        }
        time_label = label_map.get(reminder["label"], reminder["label"])

        all_signups = await queries.get_event_signups(config.DATABASE_PATH, event["event_id"])
        signed_up = sum(1 for s in all_signups if s["signup_status"] in ("confirmed", "bench"))

        from utils.embeds import build_reminder_embed
        embed = build_reminder_embed(event, time_label, signed_up)

        ping = "@here " if reminder["label"] == "5m" else ""
        await channel.send(f"{ping}", embed=embed)
        await queries.mark_reminder_sent(config.DATABASE_PATH, reminder["reminder_id"])
        log.info("Fired reminder [%s] for event %d", reminder["label"], event["event_id"])

    @reminder_loop.before_loop
    async def before_reminder_loop(self) -> None:
        await self.wait_until_ready()

    @tasks.loop(hours=6)
    async def auto_archive_loop(self) -> None:
        """Auto-complete events whose date/time has passed by more than 6 hours."""
        try:
            cutoff = (datetime.utcnow() - timedelta(hours=6)).strftime("%Y-%m-%d")
            from database.queries import _fetchall, _execute
            stale = await _fetchall(
                config.DATABASE_PATH,
                "SELECT event_id FROM events WHERE status='active' AND event_date < ?",
                (cutoff,),
            )
            for row in stale:
                await queries.complete_event(config.DATABASE_PATH, row["event_id"])
                log.info("Auto-archived event %d", row["event_id"])
        except Exception:
            log.exception("Error in auto-archive loop")

    @auto_archive_loop.before_loop
    async def before_archive_loop(self) -> None:
        await self.wait_until_ready()

    # ── Graceful shutdown ──────────────────────────────────────────────────────

    async def close(self) -> None:
        log.info("Shutting down gracefully…")
        self.reminder_loop.cancel()
        self.auto_archive_loop.cancel()
        await super().close()

    # ── Update & Restart ───────────────────────────────────────────────────────

    async def do_restart(self) -> None:
        """Close the bot then replace the process with a fresh instance."""
        log.info("Restarting bot process…")
        await self.close()
        os.execv(sys.executable, [sys.executable] + sys.argv)

    async def do_update(self) -> tuple[bool, str]:
        """
        Run ``git pull`` in the bot's working directory.
        Returns (success, output_text).
        Does NOT restart – caller decides whether to restart after.
        """
        bot_dir = pathlib.Path(__file__).parent
        try:
            result = subprocess.run(
                ["git", "pull"],
                capture_output=True,
                text=True,
                cwd=bot_dir,
                timeout=60,
            )
            output = (result.stdout + result.stderr).strip()
            success = result.returncode == 0
            log.info("git pull exit=%d  output=%s", result.returncode, output)
            return success, output
        except subprocess.TimeoutExpired:
            return False, "git pull timed out after 60 seconds."
        except FileNotFoundError:
            return False, "git not found.  Make sure git is installed and in PATH."
        except Exception as exc:
            return False, f"Unexpected error: {exc}"


# ── Entry point ───────────────────────────────────────────────────────────────

async def main() -> None:
    bot = RaidBot()
    async with bot:
        await bot.start(config.DISCORD_TOKEN)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Bot stopped by keyboard interrupt.")
