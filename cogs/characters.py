"""
Character management cog.
Commands: /character add, main, list, update, remove, sync
"""

from __future__ import annotations

import logging
import discord
from discord import app_commands
from discord.ext import commands, tasks
from typing import Optional

import config
from database import queries
from utils import embeds
from utils import blizzard as bnet
from utils import raiderio as rio
from utils.constants import VALID_SPECS, ALL_SPECS, CLASS_COLORS
from utils.validators import validate_class, validate_spec, validate_ilvl, validate_char_name


WEBSITE_URL = "https://raids.wrathofmidnight.org"


class RegistrationView(discord.ui.View):
    """Persistent view attached to the registration channel pinned message."""

    def __init__(self) -> None:
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(
            label="Register on Website",
            style=discord.ButtonStyle.link,
            url=WEBSITE_URL,
            emoji="🌐",
        ))

    @discord.ui.button(
        label="How to Register",
        style=discord.ButtonStyle.secondary,
        custom_id="char_reg_help",
        emoji="💬",
    )
    async def help_button(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.send_message(
            embed=discord.Embed(
                title="📋  Character Registration",
                description=(
                    "**Option 1 — Web Portal (Recommended)**\n"
                    f"Visit [{WEBSITE_URL}]({WEBSITE_URL}) and log in with Discord "
                    "to register and manage your characters.\n\n"
                    "**Option 2 — Discord Slash Command**\n"
                    "Use `/character add` directly in Discord:\n"
                    "```\n/character add name:Thrall realm:Stormrage\n```\n"
                    "Or paste your Raider.IO URL with `/character link`."
                ),
                color=0x5865F2,
            ),
            ephemeral=True,
        )


def _build_registration_embed() -> discord.Embed:
    embed = discord.Embed(
        title="⚔️  Start Character Registration Here",
        description=(
            "Register your World of Warcraft characters so raid leaders can build optimal rosters!\n\n"
            f"**🌐 Web Portal:** [{WEBSITE_URL}]({WEBSITE_URL})\n"
            "Log in with Discord for the full experience — manage multiple characters, "
            "view attendance stats, and more.\n\n"
            "**💬 Discord Command:** `/character add`\n"
            "Quick registration without leaving Discord.\n\n"
            "Click **How to Register** below for step-by-step instructions."
        ),
        color=0x5865F2,
    )
    embed.set_footer(text="Only your registration reply will be kept — all other messages are auto-deleted.")
    return embed


async def is_officer(interaction: discord.Interaction) -> bool:
    """Return True if the user is a server admin or has Officer/Raid Leader bot role."""
    if interaction.user.guild_permissions.administrator:
        return True
    role = await queries.get_permission(config.DATABASE_PATH, interaction.guild_id, interaction.user.id)
    return role in ("officer", "raid_leader")

log = logging.getLogger(__name__)

# Primary professions players can pick (up to 2)
PRIMARY_PROFESSIONS = [
    "Alchemy", "Blacksmithing", "Enchanting", "Engineering",
    "Herbalism", "Inscription", "Jewelcrafting", "Leatherworking",
    "Mining", "Skinning", "Tailoring",
]
SECONDARY_PROFESSIONS = ["Cooking", "Fishing"]
ALL_PROFESSIONS = sorted(PRIMARY_PROFESSIONS + SECONDARY_PROFESSIONS)


class Characters(commands.Cog):
    """Commands for registering and managing WoW characters."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.bot.add_view(RegistrationView())  # re-attach persistent view on restart

    async def cog_load(self) -> None:
        self._restore_reg_messages.start()

    async def cog_unload(self) -> None:
        self._restore_reg_messages.cancel()

    @tasks.loop(count=1)
    async def _restore_reg_messages(self) -> None:
        """Restore registration messages that may have been lost while the bot was offline."""
        await self.bot.wait_until_ready()
        for guild in self.bot.guilds:
            await self._ensure_registration_message(guild.id)

    async def _ensure_registration_message(self, guild_id: int) -> None:
        """Post or restore the registration channel pinned message if it's gone."""
        settings = await queries.get_guild_settings(config.DATABASE_PATH, guild_id)
        channel_id = settings.get("char_reg_channel_id")
        message_id = settings.get("char_reg_message_id")
        if not channel_id:
            return
        channel = self.bot.get_channel(channel_id)
        if not channel:
            return
        # Check if the message still exists
        if message_id:
            try:
                await channel.fetch_message(message_id)
                return  # message is fine
            except (discord.NotFound, discord.Forbidden):
                pass
        # Post a new registration message
        try:
            msg = await channel.send(embed=_build_registration_embed(), view=RegistrationView())
            await queries.update_guild_setting(config.DATABASE_PATH, guild_id, "char_reg_message_id", msg.id)
            try:
                await msg.pin()
            except Exception:
                pass
        except Exception as exc:
            log.warning("Could not post registration message in guild %s: %s", guild_id, exc)

    async def _refresh_roster_embed(self, guild_id: int) -> None:
        """Edit the pinned public roster embed if one has been posted."""
        settings = await queries.get_guild_settings(config.DATABASE_PATH, guild_id)
        channel_id  = settings.get("roster_channel_id")
        message_id  = settings.get("roster_message_id")
        if not channel_id or not message_id:
            return
        channel = self.bot.get_channel(channel_id)
        if not channel:
            return
        try:
            msg = await channel.fetch_message(message_id)
            all_chars = await queries.get_all_guild_characters(config.DATABASE_PATH, guild_id)
            embed = embeds.build_guild_roster_embed(all_chars)
            await msg.edit(embed=embed)
        except discord.NotFound:
            pass
        except Exception as exc:
            log.warning("Could not refresh guild roster embed: %s", exc)

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
        professions="Your professions, comma-separated (e.g. Alchemy, Herbalism)",
        progression="Current raid progression (e.g. 8/8 M, 4/8 H Nerub-ar Palace)",
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
        professions: Optional[str] = None,
        progression: Optional[str] = None,
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

        # ── API lookup: Raider.IO first, Blizzard as fallback ─────────────────
        api_race:       Optional[str] = None
        api_faction:    Optional[str] = None
        api_avatar_url: Optional[str] = None
        data_source:    Optional[str] = None

        if realm:
            await interaction.followup.send(
                embed=embeds.info_embed("🔍 Looking up character…", f"Checking Raider.IO and Blizzard Armory for **{name}**–{realm}…"),
                ephemeral=True,
            )

            # 1. Try Raider.IO (no credentials required)
            rio_data = await rio.client.get_character(region, realm, name)
            if rio_data is not None:
                data_source = "Raider.IO"
                if not char_class:
                    char_class = rio_data.get("class")
                if not main_spec:
                    main_spec = rio_data.get("active_spec_name")
                if ilvl is None:
                    ilvl = (rio_data.get("gear") or {}).get("item_level_equipped") or None
                api_race       = rio_data.get("race")
                api_avatar_url = rio_data.get("thumbnail_url")

            else:
                # 2. Fall back to Blizzard API
                bnet_client = bnet.get_client()
                if bnet_client:
                    bnet_data = await bnet_client.get_character(region, realm, name)
                    if bnet_data is not None:
                        data_source = "Blizzard Armory"
                        if not char_class:
                            char_class = bnet_data.get("character_class", {}).get("name")
                        if not main_spec:
                            main_spec = bnet_data.get("active_spec", {}).get("name")
                        if ilvl is None:
                            ilvl = bnet_data.get("average_item_level") or None
                        api_race    = bnet_data.get("race",    {}).get("name")
                        api_faction = bnet_data.get("faction", {}).get("name")
                        media = await bnet_client.get_character_media(region, realm, name)
                        if media:
                            api_avatar_url = bnet_client.extract_avatar_url(media)

            if data_source is None:
                realm_slug = realm.lower().replace("'", "").replace(" ", "-")
                await interaction.followup.send(
                    embed=embeds.error_embed(
                        "Character Not Found",
                        f"Neither Raider.IO nor the Blizzard Armory could find **{name}** on **{realm}**.\n\n"
                        "Make sure you have logged into WoW recently and your profile is public on Raider.IO: "
                        f"raider.io/characters/{region}/{realm_slug}/{name.lower()}\n\n"
                        "You can also register manually by omitting the `realm` field.",
                    ),
                    ephemeral=True,
                )
                return

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
            professions=professions,
            progression=progression,
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
        if professions:
            embed.add_field(name="Professions", value=professions, inline=True)
        if progression:
            embed.add_field(name="Progression", value=progression, inline=True)
        if api_avatar_url:
            embed.set_thumbnail(url=api_avatar_url)
        if data_source:
            embed.set_footer(text=f"✅ Found via {data_source}")
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        await interaction.followup.send(embed=embed, ephemeral=False)
        await self._refresh_roster_embed(interaction.guild_id)

    @char_group.command(name="link", description="Register a character by pasting their Raider.IO profile URL")
    @app_commands.describe(
        url="Raider.IO character URL (e.g. https://raider.io/characters/us/stormrage/thrall)",
        off_spec="Off spec (optional)",
        professions="Your professions, comma-separated (e.g. Alchemy, Herbalism)",
        progression="Current raid progression (e.g. 8/8 M, 4/8 H Nerub-ar Palace)",
    )
    async def character_link(
        self,
        interaction: discord.Interaction,
        url: str,
        off_spec: Optional[str] = None,
        professions: Optional[str] = None,
        progression: Optional[str] = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        parsed = rio.parse_url(url)
        if parsed is None:
            await interaction.followup.send(
                embed=embeds.error_embed(
                    "Invalid URL",
                    "Please provide a valid Raider.IO character URL.\n"
                    "Example: `https://raider.io/characters/us/stormrage/thrall`",
                ),
                ephemeral=True,
            )
            return

        region, realm, name = parsed

        await interaction.followup.send(
            embed=embeds.info_embed("🔍 Looking up character…", f"Checking Raider.IO and Blizzard Armory for **{name.capitalize()}**–{realm}…"),
            ephemeral=True,
        )

        # ── API lookup: Raider.IO first, Blizzard as fallback ─────────────────
        char_class:     Optional[str] = None
        main_spec:      Optional[str] = None
        api_race:       Optional[str] = None
        api_faction:    Optional[str] = None
        api_avatar_url: Optional[str] = None
        api_ilvl:       Optional[int] = None
        data_source:    Optional[str] = None

        rio_data = await rio.client.get_character(region, realm, name)
        if rio_data is not None:
            data_source    = "Raider.IO"
            char_class     = rio_data.get("class")
            main_spec      = rio_data.get("active_spec_name")
            api_ilvl       = (rio_data.get("gear") or {}).get("item_level_equipped") or None
            api_race       = rio_data.get("race")
            api_avatar_url = rio_data.get("thumbnail_url")
        else:
            bnet_client = bnet.get_client()
            if bnet_client:
                bnet_data = await bnet_client.get_character(region, realm, name)
                if bnet_data is not None:
                    data_source  = "Blizzard Armory"
                    char_class   = bnet_data.get("character_class", {}).get("name")
                    main_spec    = bnet_data.get("active_spec", {}).get("name")
                    api_ilvl     = bnet_data.get("average_item_level") or None
                    api_race     = bnet_data.get("race",    {}).get("name")
                    api_faction  = bnet_data.get("faction", {}).get("name")
                    media = await bnet_client.get_character_media(region, realm, name)
                    if media:
                        api_avatar_url = bnet_client.extract_avatar_url(media)

        if data_source is None:
            await interaction.followup.send(
                embed=embeds.error_embed(
                    "Character Not Found",
                    f"Neither Raider.IO nor the Blizzard Armory could find **{name.capitalize()}** on **{realm}**.\n\n"
                    "Make sure you have logged into WoW recently and your profile is public on Raider.IO.",
                ),
                ephemeral=True,
            )
            return

        # ── Validate class / spec ─────────────────────────────────────────────
        validated_class = validate_class(char_class) if char_class else None
        if not validated_class:
            await interaction.followup.send(
                embed=embeds.error_embed(
                    "Unknown Class",
                    f"Could not determine a valid class for **{name.capitalize()}** from {data_source}.",
                ),
                ephemeral=True,
            )
            return

        validated_spec = validate_spec(validated_class, main_spec) if main_spec else None
        if not validated_spec:
            await interaction.followup.send(
                embed=embeds.error_embed(
                    "Unknown Spec",
                    f"Could not determine a valid spec for **{name.capitalize()}** from {data_source}.",
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

        # ── Duplicate check ───────────────────────────────────────────────────
        existing = await queries.get_character(
            config.DATABASE_PATH, interaction.user.id, interaction.guild_id, name
        )
        if existing:
            await interaction.followup.send(
                embed=embeds.error_embed(
                    "Already Registered",
                    f"You already have a character named **{name.capitalize()}**. Use `/character update` to change it.",
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
            api_ilvl,
            race=api_race,
            realm=realm,
            region=region,
            avatar_url=api_avatar_url,
            faction=api_faction,
            professions=professions,
            progression=progression,
        )

        color = CLASS_COLORS.get(validated_class, 0x3498DB)
        embed = discord.Embed(
            title=f"✅  Character Registered: {name.capitalize()}",
            color=color,
        )
        embed.add_field(name="Class",     value=validated_class, inline=True)
        embed.add_field(name="Main Spec", value=validated_spec,  inline=True)
        if validated_off:
            embed.add_field(name="Off Spec",    value=validated_off,  inline=True)
        if api_ilvl:
            embed.add_field(name="Item Level",  value=str(api_ilvl),  inline=True)
        if api_race:
            embed.add_field(name="Race",        value=api_race,       inline=True)
        if api_faction:
            embed.add_field(name="Faction",     value=api_faction,    inline=True)
        embed.add_field(name="Realm", value=f"{realm.replace('-', ' ').title()} ({region.upper()})", inline=True)
        if professions:
            embed.add_field(name="Professions", value=professions, inline=True)
        if progression:
            embed.add_field(name="Progression", value=progression, inline=True)
        if api_avatar_url:
            embed.set_thumbnail(url=api_avatar_url)
        embed.set_footer(text=f"✅ Found via {data_source}")
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        await interaction.followup.send(embed=embed, ephemeral=False)
        await self._refresh_roster_embed(interaction.guild_id)

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
        await self._refresh_roster_embed(interaction.guild_id)

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
        professions="Your professions, comma-separated (e.g. Alchemy, Herbalism)",
        progression="Current raid progression (e.g. 8/8 M, 4/8 H Nerub-ar Palace)",
    )
    async def character_update(
        self,
        interaction: discord.Interaction,
        name: str,
        spec: Optional[str] = None,
        off_spec: Optional[str] = None,
        ilvl: Optional[int] = None,
        professions: Optional[str] = None,
        progression: Optional[str] = None,
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
        if professions is not None:
            updates["professions"] = professions
        if progression is not None:
            updates["progression"] = progression

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
        await self._refresh_roster_embed(interaction.guild_id)

    @char_group.command(name="progression", description="Set your raid progression for a character")
    @app_commands.describe(
        name="Character name",
        progression="Current raid progression (e.g. 8/8 M, 4/8 H Nerub-ar Palace)",
    )
    async def character_progression(
        self,
        interaction: discord.Interaction,
        name: str,
        progression: str,
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

        await queries.update_character(
            config.DATABASE_PATH, interaction.user.id, interaction.guild_id, name,
            progression=progression,
        )
        await interaction.followup.send(
            embed=embeds.success_embed(
                "Progression Updated",
                f"**{char['char_name']}**'s progression set to **{progression}**.",
            ),
            ephemeral=True,
        )
        await self._refresh_roster_embed(interaction.guild_id)

    @char_group.command(name="sync", description="Re-sync a character's class/spec/ilvl from Raider.IO or the Blizzard Armory")
    @app_commands.describe(name="Character name to sync")
    async def character_sync(self, interaction: discord.Interaction, name: str) -> None:
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

        realm  = char.get("realm")
        region = char.get("region") or "us"
        if not realm:
            await interaction.followup.send(
                embed=embeds.error_embed(
                    "No Realm Stored",
                    f"**{char['char_name']}** has no realm on record.\n"
                    "Remove and re-add with the `realm` field to enable sync.",
                ),
                ephemeral=True,
            )
            return

        updates: dict = {}
        sync_source: Optional[str] = None
        new_ilvl:    Optional[int] = None
        new_race:    Optional[str] = None
        new_faction: Optional[str] = None

        # 1. Try Raider.IO first
        rio_data = await rio.client.get_character(region, realm, char["char_name"])
        if rio_data is not None:
            sync_source = "Raider.IO"
            new_ilvl = (rio_data.get("gear") or {}).get("item_level_equipped")
            new_race = rio_data.get("race")
            avatar   = rio_data.get("thumbnail_url")
            if new_ilvl:
                updates["ilvl"] = new_ilvl
            if new_race:
                updates["race"] = new_race
            if avatar:
                updates["avatar_url"] = avatar

        else:
            # 2. Fall back to Blizzard API
            bnet_client = bnet.get_client()
            if bnet_client:
                bnet_data = await bnet_client.get_character(region, realm, char["char_name"])
                if bnet_data is not None:
                    sync_source = "Blizzard Armory"
                    new_ilvl    = bnet_data.get("average_item_level")
                    new_race    = bnet_data.get("race",    {}).get("name")
                    new_faction = bnet_data.get("faction", {}).get("name")
                    if new_ilvl:
                        updates["ilvl"] = new_ilvl
                    if new_race:
                        updates["race"] = new_race
                    if new_faction:
                        updates["faction"] = new_faction
                    media = await bnet_client.get_character_media(region, realm, char["char_name"])
                    if media:
                        avatar = bnet_client.extract_avatar_url(media)
                        if avatar:
                            updates["avatar_url"] = avatar

        if sync_source is None:
            await interaction.followup.send(
                embed=embeds.error_embed(
                    "Not Found",
                    f"**{char['char_name']}** on **{realm}-{region.upper()}** could not be found "
                    "on Raider.IO or the Blizzard Armory.",
                ),
                ephemeral=True,
            )
            return

        if updates:
            await queries.update_character(
                config.DATABASE_PATH, interaction.user.id, interaction.guild_id, name, **updates
            )

        color = CLASS_COLORS.get(char["char_class"], 0x3498DB)
        embed = discord.Embed(
            title=f"🔄  Sync: {char['char_name']}",
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
        embed.set_footer(text=f"✅ Found via {sync_source} — {realm.title()}-{region.upper()}")
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
        await self._refresh_roster_embed(interaction.guild_id)

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

    @char_group.command(name="setup_registration_channel", description="Set a channel as the character registration channel (officers only)")
    @app_commands.describe(channel="The channel to use for character registration")
    async def character_setup_registration_channel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
    ) -> None:
        if not await is_officer(interaction):
            await interaction.response.send_message(
                embed=embeds.error_embed("Permission Denied", "Only officers can configure the registration channel."),
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        # Save channel setting
        await queries.update_guild_setting(config.DATABASE_PATH, interaction.guild_id, "char_reg_channel_id", channel.id)
        # Clear any stale message ID so a fresh one is posted
        await queries.update_guild_setting(config.DATABASE_PATH, interaction.guild_id, "char_reg_message_id", None)

        # Post the registration message
        await self._ensure_registration_message(interaction.guild_id)

        await interaction.followup.send(
            embed=embeds.success_embed(
                "Registration Channel Set",
                f"{channel.mention} is now the character registration channel.\n"
                "A pinned registration prompt has been posted there.\n"
                "Non-bot messages in that channel will be automatically deleted.",
            ),
            ephemeral=True,
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Delete non-bot messages posted in the character registration channel."""
        if message.author.bot or not message.guild:
            return
        settings = await queries.get_guild_settings(config.DATABASE_PATH, message.guild.id)
        reg_channel_id = settings.get("char_reg_channel_id")
        if not reg_channel_id or message.channel.id != reg_channel_id:
            return
        try:
            await message.delete()
        except (discord.NotFound, discord.Forbidden):
            pass

    @char_group.command(name="roster", description="List all registered characters in this server (officers only)")
    async def character_roster(self, interaction: discord.Interaction) -> None:
        if not await is_officer(interaction):
            await interaction.response.send_message(
                embed=embeds.error_embed("Permission Denied", "Only officers and raid leaders can view the guild roster."),
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        all_chars = await queries.get_all_guild_characters(config.DATABASE_PATH, interaction.guild_id)

        if not all_chars:
            await interaction.followup.send(
                embed=embeds.info_embed("Guild Roster", "No characters have been registered yet."),
                ephemeral=True,
            )
            return

        # Group by class
        by_class: dict[str, list[dict]] = {}
        for char in all_chars:
            by_class.setdefault(char["char_class"], []).append(char)

        embed = discord.Embed(
            title=f"📋  Guild Character Roster  ({len(all_chars)} characters)",
            color=0x3498DB,
        )

        for cls in sorted(by_class.keys()):
            chars = by_class[cls]
            color_hex = CLASS_COLORS.get(cls, 0x3498DB)
            lines = []
            for char in chars:
                member = interaction.guild.get_member(char["discord_id"])
                member_tag = member.mention if member else f"<@{char['discord_id']}>"
                spec_info = char["main_spec"]
                if char.get("off_spec"):
                    spec_info += f" / {char['off_spec']}"
                ilvl_tag = f" · {char['ilvl']} ilvl" if char.get("ilvl") else ""
                main_tag = " ⭐" if char.get("is_main") else ""
                lines.append(f"**{char['char_name']}**{main_tag} — {spec_info}{ilvl_tag} ({member_tag})")

            embed.add_field(
                name=f"{cls}  ({len(chars)})",
                value="\n".join(lines),
                inline=False,
            )

        embed.set_footer(text="⭐ = main character")
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Characters(bot))
