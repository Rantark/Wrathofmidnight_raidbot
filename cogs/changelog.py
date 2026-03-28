"""
Changelog cog.
Command: /changelog [version]
"""

from __future__ import annotations

import json
import pathlib
import logging
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

log = logging.getLogger(__name__)

_CHANGELOG_PATH = pathlib.Path(__file__).parent.parent / "changelog.json"

_TYPE_EMOJI = {
    "new":      "✨",
    "improved": "⬆️",
    "fix":      "🔧",
    "removed":  "🗑️",
}

_TYPE_LABEL = {
    "new":      "New",
    "improved": "Improved",
    "fix":      "Fix",
    "removed":  "Removed",
}


def _load_changelog() -> dict:
    try:
        return json.loads(_CHANGELOG_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        log.error("Could not load changelog.json: %s", exc)
        return {}


def _build_embed(entry: dict, is_latest: bool) -> discord.Embed:
    color = 0x5865F2 if is_latest else 0x4F5660
    embed = discord.Embed(
        title=f"{'🆕  ' if is_latest else ''}v{entry['version']} — {entry['title']}",
        color=color,
    )
    embed.set_footer(text=f"Released {entry.get('date', 'unknown')}")

    lines: list[str] = []
    for c in entry.get("changes", []):
        emoji = _TYPE_EMOJI.get(c["type"], "•")
        label = _TYPE_LABEL.get(c["type"], c["type"].title())
        lines.append(f"{emoji} **{label}** — {c['text']}")

    if lines:
        embed.description = "\n".join(lines)
    else:
        embed.description = "*No details recorded.*"

    return embed


class Changelog(commands.Cog):
    """Show bot and web-app changelog entries."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="changelog", description="Show what's new in the bot and web portal")
    @app_commands.describe(version="Specific version to look up (e.g. 1.6.0) — defaults to latest")
    async def changelog_cmd(
        self,
        interaction: discord.Interaction,
        version: Optional[str] = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        data = _load_changelog()
        if not data:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="Changelog Unavailable",
                    description="Could not load the changelog file.",
                    color=0xED4245,
                ),
                ephemeral=True,
            )
            return

        entries: list[dict] = data.get("entries", [])
        current = data.get("current", "?")

        if version:
            # Look up a specific version
            target = next((e for e in entries if e["version"] == version.lstrip("v")), None)
            if not target:
                available = ", ".join(f"v{e['version']}" for e in entries)
                await interaction.followup.send(
                    embed=discord.Embed(
                        title="Version Not Found",
                        description=f"No changelog entry for **v{version}**.\n\nAvailable versions: {available}",
                        color=0xED4245,
                    ),
                    ephemeral=True,
                )
                return
            embed = _build_embed(target, is_latest=(target["version"] == current))
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            # Show latest + a summary list of older versions
            if not entries:
                await interaction.followup.send("No changelog entries found.", ephemeral=True)
                return

            latest = entries[0]
            embed = _build_embed(latest, is_latest=True)

            if len(entries) > 1:
                older = entries[1:]
                embed.add_field(
                    name="Previous Versions",
                    value=" · ".join(f"`v{e['version']}`" for e in older),
                    inline=False,
                )
                embed.set_footer(text=f"Released {latest.get('date', 'unknown')} · Use /changelog version:<version> to view older entries")

            await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Changelog(bot))
