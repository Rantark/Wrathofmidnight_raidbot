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
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands, tasks

import config
from database.db_setup import init_db
from database import queries


def _persist_guild_id(guild_id: int) -> None:
    """Add guild_id to GUILD_IDS in .env if not already present (no restart needed)."""
    env_path = pathlib.Path(".env")
    if not env_path.exists():
        return

    lines = env_path.read_text(encoding="utf-8").splitlines(keepends=True)
    new_lines = []
    found = False
    for line in lines:
        if line.startswith("GUILD_IDS="):
            found = True
            current = line.strip().removeprefix("GUILD_IDS=")
            ids = [g.strip() for g in current.split(",") if g.strip()]
            if str(guild_id) not in ids:
                ids.append(str(guild_id))
            new_lines.append(f"GUILD_IDS={','.join(ids)}\n")
        else:
            new_lines.append(line)

    if not found:
        new_lines.append(f"GUILD_IDS={guild_id}\n")

    env_path.write_text("".join(new_lines), encoding="utf-8")
    # Update the live config so the next startup loop already has it
    if guild_id not in config.GUILD_IDS:
        config.GUILD_IDS.append(guild_id)

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
    "cogs.changelog",
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

        # Initialise Blizzard API client if credentials are configured
        if config.BNET_CLIENT_ID and config.BNET_CLIENT_SECRET:
            from utils.blizzard import init_client as bnet_init
            bnet_init(config.BNET_CLIENT_ID, config.BNET_CLIENT_SECRET)
            log.info("Blizzard Battle.net API client ready")
        else:
            log.info("Blizzard API not configured (BNET_CLIENT_ID/SECRET not set)")

        log.info("Loading cogs…")
        for cog in COGS:
            try:
                await self.load_extension(cog)
                log.info("  ✓ %s", cog)
            except Exception as exc:
                log.exception("  ✗ Failed to load %s: %s", cog, exc)

        # Copy global commands to known guilds so they're ready when on_ready fires.
        # Actual sync() calls are deferred to on_ready where a connection exists.
        for gid in config.GUILD_IDS:
            guild = discord.Object(id=gid)
            self.tree.copy_global_to(guild=guild)

        # Start background tasks
        self.reminder_loop.start()
        self.auto_archive_loop.start()
        self.deletion_loop.start()

    async def on_ready(self) -> None:
        log.info("=" * 60)
        log.info("Bot online: %s (ID: %s)", self.user, self.user.id)
        log.info("Version:  %s", config.VERSION)
        log.info("Connected to %d guild(s)", len(self.guilds))
        log.info("Database: %s", config.DATABASE_PATH)
        log.info("=" * 60)

        # Sync commands to all guilds now that we have a live connection.
        # Known guilds had copy_global_to called in setup_hook; unknown guilds
        # (added while the bot was offline) get it here before syncing.
        known = set(config.GUILD_IDS)
        for guild in self.guilds:
            if guild.id not in known:
                self.tree.copy_global_to(guild=guild)
                _persist_guild_id(guild.id)
            synced = await self.tree.sync(guild=discord.Object(id=guild.id))
            log.info("Synced %d commands to guild %s (%d)", len(synced), guild.name, guild.id)

        # Clear stale globally-registered commands after guild syncs are done.
        self.tree.clear_commands(guild=None)
        await self.tree.sync()
        log.info("Cleared global slash commands (prevents duplicates)")

        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name=f"the raid calendar 📅  v{config.VERSION}",
            )
        )

    async def on_guild_join(self, guild: discord.Guild) -> None:
        """When invited to a new server: sync commands instantly and save the guild ID."""
        log.info("Joined new guild: %s (%d) — syncing commands", guild.name, guild.id)
        guild_obj = discord.Object(id=guild.id)
        self.tree.copy_global_to(guild=guild_obj)
        synced = await self.tree.sync(guild=guild_obj)
        log.info("Synced %d commands to new guild %d", len(synced), guild.id)
        _persist_guild_id(guild.id)
        log.info("Saved guild %d to .env GUILD_IDS", guild.id)

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

        guild_settings = await queries.get_guild_settings(config.DATABASE_PATH, event["guild_id"])
        tz_name = guild_settings.get("timezone") or config.TIMEZONE or "America/New_York"
        import pytz
        try:
            tz = pytz.timezone(tz_name)
            naive_dt = datetime.strptime(f"{event['event_date']} {event['event_time']}", "%Y-%m-%d %H:%M")
            tz_abbrev = tz.localize(naive_dt).strftime("%Z")
        except Exception:
            tz_abbrev = ""

        from utils.embeds import build_reminder_embed
        embed = build_reminder_embed(event, time_label, signed_up, tz_label=tz_abbrev)

        # Delete any previously posted reminder messages for this event so the
        # channel doesn't fill up with stacked reminder posts.
        old_msgs = await queries.get_sent_reminder_messages(config.DATABASE_PATH, event["event_id"])
        for old in old_msgs:
            try:
                old_ch = self.get_channel(old["msg_channel_id"])
                if old_ch:
                    old_msg = await old_ch.fetch_message(old["message_id"])
                    await old_msg.delete()
            except (discord.NotFound, discord.Forbidden):
                pass
            except Exception:
                pass  # Don't let cleanup failure block the new reminder

        ping = "@here " if reminder["label"] == "5m" else ""
        sent_msg = await channel.send(f"{ping}", embed=embed)

        # Persist the message ID so the *next* reminder can delete this one.
        await queries.set_reminder_message(
            config.DATABASE_PATH, reminder["reminder_id"], sent_msg.id, channel.id
        )
        await queries.mark_reminder_sent(config.DATABASE_PATH, reminder["reminder_id"])
        log.info("Fired reminder [%s] for event %d", reminder["label"], event["event_id"])

    @reminder_loop.before_loop
    async def before_reminder_loop(self) -> None:
        await self.wait_until_ready()

    @tasks.loop(minutes=30)
    async def auto_archive_loop(self) -> None:
        """Complete events that ended >4 hours ago and delete their Discord posts."""
        try:
            import pytz
            from database.queries import _fetchall
            active = await _fetchall(
                config.DATABASE_PATH,
                "SELECT event_id, guild_id, event_date, event_time, channel_id, message_id, "
                "boss_channel_id, boss_message_id FROM events WHERE status='active'",
            )
            now_utc = datetime.now(timezone.utc)
            for event in active:
                # Convert event start time to UTC using the guild's configured timezone
                guild_settings = await queries.get_guild_settings(
                    config.DATABASE_PATH, event["guild_id"]
                )
                tz_name = guild_settings.get("timezone") or config.TIMEZONE or "America/New_York"
                try:
                    tz = pytz.timezone(tz_name)
                    naive_dt = datetime.strptime(
                        f"{event['event_date']} {event['event_time']}", "%Y-%m-%d %H:%M"
                    )
                    event_dt_utc = tz.localize(naive_dt).astimezone(timezone.utc)
                except Exception:
                    # Fallback: treat stored time as UTC
                    event_dt_utc = datetime.strptime(
                        f"{event['event_date']} {event['event_time']}", "%Y-%m-%d %H:%M"
                    ).replace(tzinfo=timezone.utc)

                if now_utc < event_dt_utc + timedelta(hours=4):
                    continue  # Not time yet

                # Mark complete first so the embed refresh no longer picks it up
                await queries.complete_event(config.DATABASE_PATH, event["event_id"])

                # Delete the signup embed
                if event.get("channel_id") and event.get("message_id"):
                    try:
                        ch = self.get_channel(event["channel_id"]) or \
                             await self.fetch_channel(event["channel_id"])
                        msg = await ch.fetch_message(event["message_id"])
                        await msg.delete()
                    except (discord.NotFound, discord.Forbidden):
                        pass
                    except Exception:
                        log.exception("Error deleting signup embed for event %d", event["event_id"])

                # Delete the boss progress embed if one exists
                if event.get("boss_channel_id") and event.get("boss_message_id"):
                    try:
                        ch = self.get_channel(event["boss_channel_id"]) or \
                             await self.fetch_channel(event["boss_channel_id"])
                        msg = await ch.fetch_message(event["boss_message_id"])
                        await msg.delete()
                    except (discord.NotFound, discord.Forbidden):
                        pass
                    except Exception:
                        log.exception("Error deleting boss embed for event %d", event["event_id"])

                log.info("Auto-archived event %d and deleted channel posts", event["event_id"])
        except Exception:
            log.exception("Error in auto-archive loop")

    @auto_archive_loop.before_loop
    async def before_archive_loop(self) -> None:
        await self.wait_until_ready()

    @tasks.loop(minutes=1)
    async def deletion_loop(self) -> None:
        """Delete messages that were scheduled for deferred removal (e.g. cancelled events)."""
        try:
            due = await queries.get_due_deletions(config.DATABASE_PATH)
            for row in due:
                try:
                    channel = self.get_channel(row["channel_id"])
                    if channel is None:
                        channel = await self.fetch_channel(row["channel_id"])
                    msg = await channel.fetch_message(row["message_id"])
                    await msg.delete()
                    log.info("Deleted scheduled message %d in channel %d", row["message_id"], row["channel_id"])
                except (discord.NotFound, discord.Forbidden):
                    pass  # Already gone or no permission – still clean up the record
                except Exception:
                    log.exception("Error deleting scheduled message %d", row["message_id"])
                finally:
                    await queries.remove_scheduled_deletion(config.DATABASE_PATH, row["deletion_id"])
        except Exception:
            log.exception("Error in deletion loop")

    @deletion_loop.before_loop
    async def before_deletion_loop(self) -> None:
        await self.wait_until_ready()

    # ── Graceful shutdown ──────────────────────────────────────────────────────

    async def close(self) -> None:
        log.info("Shutting down gracefully…")
        self.reminder_loop.cancel()
        self.auto_archive_loop.cancel()
        self.deletion_loop.cancel()
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
