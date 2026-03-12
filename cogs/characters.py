"""
Character management cog.
Commands: /character add, main, list, update, remove, sync
"""

from __future__ import annotations

import logging
import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional

import config
from database import queries
from utils import embeds
from utils import blizzard as bnet
from utils.constants import VALID_SPECS, ALL_SPECS, CLASS_COLORS
from utils.validators import validate_class, validate_spec, validate_ilvl, validate_char_name

log = logging.getLogger(__name__)


class Characters(commands.Cog):
    """Commands for registering and managing WoW characters."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ── /character ────────────────────────────────────────────────────────────
    char_group = app_commands.Group(name="character", description="Manage your WoW characters")

    @char_group.command(name="add", description="Register a new WoW character (auto-fills from Armory if realm provided)")
    @app_commands.describe(
        name="Character name",
        realm="Your realm name only, no region suffix (e.g. Anvilmar)",
        region="Your region: us, eu, kr, tw (default: us)",
        char_class="WoW class — required if no realm, optional override with realm",
        main_spec="Main spec — required if no realm, optional override with realm",
        off_spec="Off spec (optional)",
        ilvl="Item level — auto-filled from Armory if realm provided",
    )
    async def character_add(
        self,
        interaction: discord.Interaction,
        name: str,
        realm: Optional[str] = None,
        region: str = "us",
        char_class: Optional[str] = None,
        main_spec: Optional[str] = None,
        off_spec: Optional[str] = None,
        ilvl: Optional[int] = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        if not validate_char_name(name):
            await interaction.followup.send(
                embed=embeds.error_embed(
                    "Invalid Name",
                    "Character names must be 2–12 letters with no spaces or numbers.",
                ),
                ephemeral=True,
            )
            return

        region = region.lower().strip()
        if region not in bnet.BlizzardClient.REGIONS:
            await interaction.followup.send(
                embed=embeds.error_embed(
                    "Invalid Region",
                    f"Region must be one of: {', '.join(bnet.BlizzardClient.REGIONS)}",
                ),
                ephemeral=True,
            )
            return

        # ── Blizzard Armory lookup ────────────────────────────────────────────
        api_race:       Optional[str] = None
        api_faction:    Optional[str] = None
        api_avatar_url: Optional[str] = None

        if realm:
            client = bnet.get_client()
            if not client:
                await interaction.followup.send(
                    embed=embeds.error_embed(
                        "API Not Configured",
                        "Blizzard API credentials are not set up on this bot.\n"
                        "Register your character manually by omitting the `realm` field.",
                    ),
                    ephemeral=True,
                )
                return

            await interaction.followup.send(
                embed=embeds.info_embed("🔍 Looking up character…", f"Fetching **{name}**–{realm} from the Armory…"),
                ephemeral=True,
            )

            api_data = await client.get_character(region, realm, name)
            if api_data is None:
                await interaction.followup.send(
                    embed=embeds.error_embed(
                        "Character Not Found",
                        f"**{name}** on **{realm}** was not found in the Armory.\n"
                        "Check the spelling and try again, or register manually (omit `realm`).",
                    ),
                    ephemeral=True,
                )
                return

            # Auto-fill fields from API (user overrides take priority)
            if not char_class:
                char_class = api_data.get("character_class", {}).get("name")
            if not main_spec:
                main_spec = api_data.get("active_spec", {}).get("name")
            if ilvl is None:
                ilvl = api_data.get("average_item_level") or None

            api_race    = api_data.get("race",    {}).get("name")
            api_faction = api_data.get("faction", {}).get("name")

            # Fetch avatar URL (best-effort, non-fatal)
            media = await client.get_character_media(region, realm, name)
            if media:
                api_avatar_url = client.extract_avatar_url(media)

        # ── Validate class / spec ─────────────────────────────────────────────
        if not char_class:
            class_list = "\n".join(f"• {c}" for c in sorted(VALID_SPECS.keys()))
            await interaction.followup.send(
                embed=embeds.error_embed(
                    "Class Required",
                    f"Provide `char_class` or use the `realm` parameter for Armory lookup.\n\n"
                    f"Valid classes:\n{class_list}",
                ),
                ephemeral=True,
            )
            return

        validated_class = validate_class(char_class)
        if not validated_class:
            class_list = "\n".join(f"• {c}" for c in sorted(VALID_SPECS.keys()))
            await interaction.followup.send(
                embed=embeds.error_embed(
                    "Invalid Class",
                    f"**{char_class}** is not a valid WoW class.\n\nValid classes:\n{class_list}",
                ),
                ephemeral=True,
            )
            return

        if not main_spec:
            spec_list = "\n".join(f"• {s}" for s in ALL_SPECS[validated_class])
            await interaction.followup.send(
                embed=embeds.error_embed(
                    "Spec Required",
                    f"Provide `main_spec` or use the `realm` parameter for Armory lookup.\n\n"
                    f"Valid specs for {validated_class}:\n{spec_list}",
                ),
                ephemeral=True,
            )
            return

        validated_spec = validate_spec(validated_class, main_spec)
        if not validated_spec:
            spec_list = "\n".join(f"• {s}" for s in ALL_SPECS[validated_class])
            await interaction.followup.send(
                embed=embeds.error_embed(
                    "Invalid Spec",
                    f"**{main_spec}** is not valid for {validated_class}.\n\nValid specs:\n{spec_list}",
                ),
                ephemeral=True,
            )
            return

        validated_off: Optional[str] = None
        if off_spec:
            validated_off = validate_spec(validated_class, off_spec)
            if not validated_off:
                await interaction.followup.send(
                    embed=embeds.error_embed(
                        "Invalid Off-Spec",
                        f"**{off_spec}** is not valid for {validated_class}.",
                    ),
                    ephemeral=True,
                )
                return

        if ilvl is not None and not validate_ilvl(ilvl):
            await interaction.followup.send(
                embed=embeds.error_embed("Invalid Item Level", "Item level must be between 1 and 700."),
                ephemeral=True,
            )
            return

        # ── Duplicate check ───────────────────────────────────────────────────
        existing = await queries.get_character(
            config.DATABASE_PATH, interaction.user.id, interaction.guild_id, name
        )
        if existing:
            await interaction.followup.send(
                embed=embeds.error_embed(
                    "Already Registered",
                    f"You already have a character named **{name}**. Use `/character update` to change it.",
                ),
                ephemeral=True,
            )
            return

        await queries.add_character(
            config.DATABASE_PATH,
            interaction.user.id,
            interaction.guild_id,
            name.capitalize(),
            validated_class,
            validated_spec,
            validated_off,
            ilvl,
            race=api_race,
            realm=realm,
            region=region if realm else None,
            avatar_url=api_avatar_url,
            faction=api_faction,
        )

        color = CLASS_COLORS.get(validated_class, 0x3498DB)
        embed = discord.Embed(
            title=f"✅  Character Registered: {name.capitalize()}",
            color=color,
        )
        embed.add_field(name="Class",     value=validated_class, inline=True)
        embed.add_field(name="Main Spec", value=validated_spec,  inline=True)
        if validated_off:
            embed.add_field(name="Off Spec", value=validated_off, inline=True)
        if ilvl:
            embed.add_field(name="Item Level", value=str(ilvl), inline=True)
        if api_race:
            embed.add_field(name="Race",    value=api_race,    inline=True)
        if api_faction:
            embed.add_field(name="Faction", value=api_faction, inline=True)
        if realm:
            embed.add_field(name="Realm",   value=f"{realm.title()} ({region.upper()})", inline=True)
        if api_avatar_url:
            embed.set_thumbnail(url=api_avatar_url)
        if realm:
            embed.set_footer(text="✨ Data auto-filled from the Blizzard Armory")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @char_group.command(name="main", description="Set your main character")
    @app_commands.describe(name="Name of the character to set as main")
    async def character_main(self, interaction: discord.Interaction, name: str) -> None:
        await interaction.response.defer(ephemeral=True)
        char = await queries.get_character(
            config.DATABASE_PATH, interaction.user.id, interaction.guild_id, name
        )
        if not char:
            await interaction.followup.send(
                embed=embeds.error_embed("Not Found", f"No character named **{name}** found."),
                ephemeral=True,
            )
            return
        await queries.set_main_character(
            config.DATABASE_PATH, interaction.user.id, interaction.guild_id, name
        )
        await interaction.followup.send(
            embed=embeds.success_embed("Main Updated", f"**{char['char_name']}** is now your main character."),
            ephemeral=True,
        )

    @char_group.command(name="list", description="View your registered characters")
    async def character_list(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        chars = await queries.get_user_characters(
            config.DATABASE_PATH, interaction.user.id, interaction.guild_id
        )
        embed = embeds.build_character_list_embed(interaction.user.display_name, chars)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @char_group.command(name="update", description="Update a character's info")
    @app_commands.describe(
        name="Character name",
        spec="New main spec",
        off_spec="New off spec",
        ilvl="New item level",
    )
    async def character_update(
        self,
        interaction: discord.Interaction,
        name: str,
        spec: Optional[str] = None,
        off_spec: Optional[str] = None,
        ilvl: Optional[int] = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        char = await queries.get_character(
            config.DATABASE_PATH, interaction.user.id, interaction.guild_id, name
        )
        if not char:
            await interaction.followup.send(
                embed=embeds.error_embed("Not Found", f"No character named **{name}** found."),
                ephemeral=True,
            )
            return

        updates: dict = {}
        if spec:
            validated = validate_spec(char["char_class"], spec)
            if not validated:
                await interaction.followup.send(
                    embed=embeds.error_embed(
                        "Invalid Spec",
                        f"**{spec}** is not valid for {char['char_class']}.",
                    ),
                    ephemeral=True,
                )
                return
            updates["main_spec"] = validated
        if off_spec:
            validated_off = validate_spec(char["char_class"], off_spec)
            if not validated_off:
                await interaction.followup.send(
                    embed=embeds.error_embed(
                        "Invalid Off-Spec",
                        f"**{off_spec}** is not valid for {char['char_class']}.",
                    ),
                    ephemeral=True,
                )
                return
            updates["off_spec"] = validated_off
        if ilvl is not None:
            if not validate_ilvl(ilvl):
                await interaction.followup.send(
                    embed=embeds.error_embed("Invalid Item Level", "Item level must be 1–700."),
                    ephemeral=True,
                )
                return
            updates["ilvl"] = ilvl

        if not updates:
            await interaction.followup.send(
                embed=embeds.warning_embed("Nothing to Update", "Please provide at least one field to update."),
                ephemeral=True,
            )
            return

        await queries.update_character(
            config.DATABASE_PATH, interaction.user.id, interaction.guild_id, name, **updates
        )
        await interaction.followup.send(
            embed=embeds.success_embed("Character Updated", f"**{char['char_name']}** has been updated."),
            ephemeral=True,
        )

    @char_group.command(name="sync", description="Re-sync a character's class/spec/ilvl from the Blizzard Armory")
    @app_commands.describe(name="Character name to sync")
    async def character_sync(self, interaction: discord.Interaction, name: str) -> None:
        await interaction.response.defer(ephemeral=True)

        client = bnet.get_client()
        if not client:
            await interaction.followup.send(
                embed=embeds.error_embed(
                    "API Not Configured",
                    "Blizzard API credentials are not set up on this bot.",
                ),
                ephemeral=True,
            )
            return

        char = await queries.get_character(
            config.DATABASE_PATH, interaction.user.id, interaction.guild_id, name
        )
        if not char:
            await interaction.followup.send(
                embed=embeds.error_embed("Not Found", f"No character named **{name}** found."),
                ephemeral=True,
            )
            return

        realm  = char.get("realm")
        region = char.get("region") or "us"
        if not realm:
            await interaction.followup.send(
                embed=embeds.error_embed(
                    "No Realm Stored",
                    f"**{char['char_name']}** has no realm on record.\n"
                    "Remove and re-add with the `realm` field to enable Armory sync.",
                ),
                ephemeral=True,
            )
            return

        api_data = await client.get_character(region, realm, char["char_name"])
        if api_data is None:
            await interaction.followup.send(
                embed=embeds.error_embed(
                    "Not Found in Armory",
                    f"**{char['char_name']}** on **{realm}-{region.upper()}** could not be found.",
                ),
                ephemeral=True,
            )
            return

        updates: dict = {}
        new_ilvl = api_data.get("average_item_level")
        if new_ilvl:
            updates["ilvl"] = new_ilvl
        new_race = api_data.get("race", {}).get("name")
        if new_race:
            updates["race"] = new_race
        new_faction = api_data.get("faction", {}).get("name")
        if new_faction:
            updates["faction"] = new_faction

        media = await client.get_character_media(region, realm, char["char_name"])
        if media:
            avatar = client.extract_avatar_url(media)
            if avatar:
                updates["avatar_url"] = avatar

        if updates:
            await queries.update_character(
                config.DATABASE_PATH, interaction.user.id, interaction.guild_id, name, **updates
            )

        color = CLASS_COLORS.get(char["char_class"], 0x3498DB)
        embed = discord.Embed(
            title=f"🔄  Armory Sync: {char['char_name']}",
            color=color,
        )
        if new_ilvl:
            embed.add_field(name="Item Level", value=str(new_ilvl), inline=True)
        if new_race:
            embed.add_field(name="Race",       value=new_race,      inline=True)
        if new_faction:
            embed.add_field(name="Faction",    value=new_faction,   inline=True)
        if updates.get("avatar_url"):
            embed.set_thumbnail(url=updates["avatar_url"])
        embed.set_footer(text=f"Synced from {realm.title()}-{region.upper()}")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @char_group.command(name="remove", description="Remove a registered character")
    @app_commands.describe(name="Character name to remove")
    async def character_remove(self, interaction: discord.Interaction, name: str) -> None:
        await interaction.response.defer(ephemeral=True)
        char = await queries.get_character(
            config.DATABASE_PATH, interaction.user.id, interaction.guild_id, name
        )
        if not char:
            await interaction.followup.send(
                embed=embeds.error_embed("Not Found", f"No character named **{name}** found."),
                ephemeral=True,
            )
            return

        await queries.remove_character(
            config.DATABASE_PATH, interaction.user.id, interaction.guild_id, name
        )
        await interaction.followup.send(
            embed=embeds.success_embed("Character Removed", f"**{char['char_name']}** has been removed."),
            ephemeral=True,
        )

    @char_group.command(name="info", description="View another member's characters")
    @app_commands.describe(member="Discord member to look up")
    async def character_info(
        self, interaction: discord.Interaction, member: discord.Member
    ) -> None:
        await interaction.response.defer()
        chars = await queries.get_user_characters(
            config.DATABASE_PATH, member.id, interaction.guild_id
        )
        embed = embeds.build_character_list_embed(member.display_name, chars)
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Characters(bot))
