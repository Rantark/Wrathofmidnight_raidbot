"""
Complete World of Warcraft raid database – all expansions, all bosses.
Used for boss-progress tracking and autocomplete when creating events.

Structure:  RAID_DATABASE[expansion][raid_name] = [boss, ...]
Flat lookup: ALL_RAIDS[raid_name] = [boss, ...]
             RAID_EXPANSION[raid_name] = expansion
"""

from __future__ import annotations

RAID_DATABASE: dict[str, dict[str, list[str]]] = {

    # ── Classic ───────────────────────────────────────────────────────────────
    "Classic": {
        "Molten Core": [
            "Lucifron", "Magmadar", "Gehennas", "Garr",
            "Shazzrah", "Baron Geddon", "Golemagg the Incinerator",
            "Sulfuron Harbinger", "Majordomo Executus", "Ragnaros",
        ],
        "Onyxia's Lair (Classic)": [
            "Onyxia",
        ],
        "Blackwing Lair": [
            "Razorgore the Untamed", "Vaelastrasz the Corrupt", "Broodlord Lashlayer",
            "Firemaw", "Ebonroc", "Flamegor", "Chromaggus", "Nefarian",
        ],
        "Zul'Gurub": [
            "High Priest Venoxis", "High Priestess Jeklik", "High Priest Thekal",
            "High Priestess Mar'li", "High Priestess Arlokk", "Bloodlord Mandokir",
            "Edge of Madness", "Gahz'ranka", "Jin'do the Hexxer", "Hakkar the Soulflayer",
        ],
        "Ruins of Ahn'Qiraj": [
            "Kurinnaxx", "General Rajaxx", "Moam", "Buru the Gorger",
            "Ayamiss the Hunter", "Ossirian the Unscarred",
        ],
        "Temple of Ahn'Qiraj": [
            "The Prophet Skeram", "Battleguard Sartura", "Fankriss the Unyielding",
            "Princess Huhuran", "The Twin Emperors", "Ouro", "C'Thun",
        ],
        "Naxxramas (Classic)": [
            "Anub'Rekhan", "Grand Widow Faerlina", "Maexxna",
            "Noth the Plaguebringer", "Heigan the Unclean", "Loatheb",
            "Instructor Razuvious", "Gothik the Harvester", "The Four Horsemen",
            "Patchwerk", "Grobbulus", "Gluth", "Thaddius",
            "Sapphiron", "Kel'Thuzad",
        ],
    },

    # ── The Burning Crusade ───────────────────────────────────────────────────
    "The Burning Crusade": {
        "Karazhan": [
            "Attumen the Huntsman", "Moroes", "Maiden of Virtue",
            "Opera Event", "The Curator", "Terestian Illhoof",
            "Shade of Aran", "Netherspite", "Chess Event",
            "Prince Malchezaar", "Nightbane",
        ],
        "Gruul's Lair": [
            "High King Maulgar", "Gruul the Dragonkiller",
        ],
        "Magtheridon's Lair": [
            "Magtheridon",
        ],
        "Serpentshrine Cavern": [
            "Hydross the Unstable", "The Lurker Below", "Leotheras the Blind",
            "Fathom-Lord Karathress", "Morogrim Tidewalker", "Lady Vashj",
        ],
        "Tempest Keep": [
            "Al'ar", "Void Reaver", "High Astromancer Solarian",
            "Kael'thas Sunstrider",
        ],
        "Battle for Mount Hyjal": [
            "Rage Winterchill", "Anetheron", "Kaz'rogal",
            "Azgalor", "Archimonde",
        ],
        "Black Temple": [
            "High Warlord Naj'entus", "Supremus", "Shade of Akama",
            "Teron Gorefiend", "Gurtogg Bloodboil", "Reliquary of Souls",
            "Mother Shahraz", "The Illidari Council", "Illidan Stormrage",
        ],
        "Zul'Aman": [
            "Nalorakk", "Akil'zon", "Jan'alai",
            "Halazzi", "Hex Lord Malacrass", "Zul'jin",
        ],
        "Sunwell Plateau": [
            "Kalecgos", "Brutallus", "Felmyst",
            "The Eredar Twins", "M'uru", "Kil'jaeden",
        ],
    },

    # ── Wrath of the Lich King ────────────────────────────────────────────────
    "Wrath of the Lich King": {
        "Naxxramas": [
            "Anub'Rekhan", "Grand Widow Faerlina", "Maexxna",
            "Noth the Plaguebringer", "Heigan the Unclean", "Loatheb",
            "Instructor Razuvious", "Gothik the Harvester", "The Four Horsemen",
            "Patchwerk", "Grobbulus", "Gluth", "Thaddius",
            "Sapphiron", "Kel'Thuzad",
        ],
        "The Obsidian Sanctum": [
            "Shadron", "Tenebron", "Vesperon", "Sartharion",
        ],
        "The Eye of Eternity": [
            "Malygos",
        ],
        "Ulduar": [
            "Flame Leviathan", "Ignis the Furnace Master", "Razorscale", "XT-002 Deconstructor",
            "The Assembly of Iron", "Kologarn", "Auriaya",
            "Hodir", "Thorim", "Freya", "Mimiron",
            "General Vezax", "Yogg-Saron", "Algalon the Observer",
        ],
        "Trial of the Crusader": [
            "The Beasts of Northrend", "Lord Jaraxxus",
            "Faction Champions", "Val'kyr Twins", "Anub'arak",
        ],
        "Onyxia's Lair": [
            "Onyxia",
        ],
        "Icecrown Citadel": [
            "Lord Marrowgar", "Lady Deathwhisper", "Gunship Battle",
            "Deathbringer Saurfang", "Festergut", "Rotface",
            "Professor Putricide", "Blood Prince Council",
            "Blood-Queen Lana'thel", "Valithria Dreamwalker",
            "Sindragosa", "The Lich King",
        ],
        "The Ruby Sanctum": [
            "Saviana Ragefire", "Baltharus the Warborn",
            "General Zarithrian", "Halion",
        ],
    },

    # ── Cataclysm ─────────────────────────────────────────────────────────────
    "Cataclysm": {
        "Blackwing Descent": [
            "Magmaw", "Omnotron Defense System", "Chimaeron",
            "Atramedes", "Maloriak", "Nefarian",
        ],
        "Throne of the Four Winds": [
            "Conclave of Wind", "Al'Akir",
        ],
        "Bastion of Twilight": [
            "Halfus Wyrmbreaker", "Valiona and Theralion",
            "Twilight Ascendant Council", "Cho'gall", "Sinestra",
        ],
        "Firelands": [
            "Beth'tilac", "Lord Rhyolith", "Alysrazor",
            "Shannox", "Baleroc", "Majordomo Staghelm", "Ragnaros",
        ],
        "Dragon Soul": [
            "Morchok", "Warlord Zon'ozz", "Yor'sahj the Unsleeping",
            "Hagara the Stormbinder", "Ultraxion", "Warmaster Blackhorn",
            "Spine of Deathwing", "Madness of Deathwing",
        ],
    },

    # ── Mists of Pandaria ─────────────────────────────────────────────────────
    "Mists of Pandaria": {
        "Mogu'shan Vaults": [
            "The Stone Guard", "Feng the Accursed", "Gara'jal the Spiritbinder",
            "The Spirit Kings", "Elegon", "Will of the Emperor",
        ],
        "Heart of Fear": [
            "Imperial Vizier Zor'lok", "Blade Lord Ta'yak", "Garalon",
            "Wind Lord Mel'jarak", "Amber-Shaper Un'sok", "Grand Empress Shek'zeer",
        ],
        "Terrace of Endless Spring": [
            "Protectors of the Endless", "Tsulong",
            "Lei Shi", "Sha of Fear",
        ],
        "Throne of Thunder": [
            "Jin'rokh the Breaker", "Horridon", "Council of Elders",
            "Tortos", "Megaera", "Ji-Kun",
            "Durumu the Forgotten", "Primordius", "Dark Animus",
            "Iron Qon", "Twin Consorts", "Lei Shen", "Ra-den",
        ],
        "Siege of Orgrimmar": [
            "Immerseus", "The Fallen Protectors", "Norushen",
            "Sha of Pride", "Galakras", "Iron Juggernaut",
            "Kor'kron Dark Shaman", "General Nazgrim",
            "Malkorok", "Spoils of Pandaria", "Thok the Bloodthirsty",
            "Siegecrafter Blackfuse", "Paragons of the Klaxxi", "Garrosh Hellscream",
        ],
    },

    # ── Warlords of Draenor ───────────────────────────────────────────────────
    "Warlords of Draenor": {
        "Highmaul": [
            "Kargath Bladefist", "The Butcher", "Brackenspore",
            "Tectus", "Twin Ogron", "Ko'ragh", "Imperator Mar'gok",
        ],
        "Blackrock Foundry": [
            "Oregorger", "Gruul", "The Blast Furnace",
            "Hans'gar and Franzok", "Flamebender Ka'graz", "Kromog",
            "Beastlord Darmac", "Operator Thogar",
            "The Iron Maidens", "Blackhand",
        ],
        "Hellfire Citadel": [
            "Hellfire Assault", "Iron Reaver", "Kormrok",
            "Hellfire High Council", "Kilrogg Deadeye", "Gorefiend",
            "Shadow-Lord Iskar", "Socrethar the Eternal",
            "Tyrant Velhari", "Fel Lord Zakuun", "Xhul'horac",
            "Mannoroth", "Archimonde",
        ],
    },

    # ── Legion ────────────────────────────────────────────────────────────────
    "Legion": {
        "The Emerald Nightmare": [
            "Nythendra", "Il'gynoth, Heart of Corruption", "Elerethe Renferal",
            "Ursoc", "Dragons of Nightmare", "Cenarius", "Xavius",
        ],
        "Trial of Valor": [
            "Odyn", "Guarm", "Helya",
        ],
        "The Nighthold": [
            "Skorpyron", "Chronomatic Anomaly", "Trilliax",
            "Spellblade Aluriel", "Tichondrius", "Krosus",
            "High Botanist Tel'arn", "Star Augur Etraeus",
            "Grand Magistrix Elisande", "Gul'dan",
        ],
        "Tomb of Sargeras": [
            "Goroth", "Demonic Inquisition", "Harjatan",
            "Mistress Sassz'ine", "Sisters of the Moon",
            "The Desolate Host", "Maiden of Vigilance",
            "Fallen Avatar", "Kil'jaeden",
        ],
        "Antorus, the Burning Throne": [
            "Garothi Worldbreaker", "Felhounds of Sargeras", "Antoran High Command",
            "Portal Keeper Hasabel", "Eonar the Life-Binder",
            "Imonar the Soulhunter", "Kin'garoth",
            "Varimathras", "The Coven of Shivarra",
            "Aggramar", "Argus the Unmaker",
        ],
    },

    # ── Battle for Azeroth ────────────────────────────────────────────────────
    "Battle for Azeroth": {
        "Uldir": [
            "Taloc", "MOTHER", "Fetid Devourer", "Zek'voz, Herald of N'zoth",
            "Vectis", "Zul, Reborn", "Mythrax the Unraveler", "G'huun",
        ],
        "Battle of Dazar'alor": [
            "Frida Ironbellows / Champion of the Light", "Grong",
            "Jadefire Masters", "Opulence",
            "Conclave of the Chosen / King Rastakhan",
            "High Tinker Mekkatorque", "Stormwall Blockade", "Lady Jaina Proudmoore",
        ],
        "Crucible of Storms": [
            "The Restless Cabal", "Uu'nat, Harbinger of the Void",
        ],
        "The Eternal Palace": [
            "Abyssal Commander Sivara", "Blackwater Behemoth", "Radiance of Azshara",
            "Lady Ashvane", "Orgozoa", "The Queen's Court",
            "Za'qul, Harbinger of Ny'alotha", "Queen Azshara",
        ],
        "Ny'alotha, the Waking City": [
            "Wrathion, the Black Emperor", "Maut", "The Prophet Skitra",
            "Dark Inquisitor Xanesh", "The Hivemind",
            "Shadhar the Insatiable", "Drest'agath",
            "Il'gynoth, Corruption Reborn", "Vexiona",
            "Ra-den the Despoiled", "Carapace of N'Zoth", "N'Zoth the Corruptor",
        ],
    },

    # ── Shadowlands ───────────────────────────────────────────────────────────
    "Shadowlands": {
        "Castle Nathria": [
            "Shriekwing", "Huntsman Altimor", "Hungering Destroyer",
            "Sun King's Salvation", "Artificer Xy'mox",
            "Lady Inerva Darkvein", "The Council of Blood",
            "Sludgefist", "Stone Legion Generals", "Sire Denathrius",
        ],
        "Sanctum of Domination": [
            "The Tarragrue", "The Eye of the Jailer", "The Nine",
            "Remnant of Ner'zhul", "Soulrender Dormazain",
            "Painsmith Raznal", "Guardian of the First Ones",
            "Fatescribe Roh-Kalo", "Kel'Thuzad", "Sylvanas Windrunner",
        ],
        "Sepulcher of the First Ones": [
            "Vigilant Guardian", "Skolex, the Insatiable Ravener", "Artificer Xy'mox",
            "Dausegne, the Fallen Oracle", "Prototype Pantheon",
            "Lihuvim, Principal Architect", "Halondrus the Reclaimer",
            "Anduin Wrynn", "Lords of Dread",
            "Rygelon", "The Jailer",
        ],
    },

    # ── Dragonflight ──────────────────────────────────────────────────────────
    "Dragonflight": {
        "Vault of the Incarnates": [
            "Eranog", "Terros", "The Primal Council", "Sennarth, the Cold Breath",
            "Dathea, Ascended", "Kurog Grimtotem",
            "Broodkeeper Diurna", "Raszageth the Storm-Eater",
        ],
        "Aberrus, the Shadowed Crucible": [
            "Kazzara, the Hellforged", "The Amalgamation Chamber",
            "The Forgotten Experiments", "Assault of the Zaqali",
            "Rashok, the Elder", "The Vigilant Steward, Zskarn",
            "Magmorax", "Echo of Neltharion", "Scalecommander Sarkareth",
        ],
        "Amirdrassil, the Dream's Hope": [
            "Gnarlroot", "Igira the Cruel", "Volcoross",
            "Council of Dreams", "Larodar, Keeper of the Flame",
            "Nymue, Weaver of the Cycle", "Smolderon",
            "Tindral Sageswift, Seer of the Flame", "Fyrakk the Blazing",
        ],
    },

    # ── The War Within ────────────────────────────────────────────────────────
    "The War Within": {
        "Nerub-ar Palace": [
            "Ulgrax the Devourer", "The Bloodbound Horror", "Sikran, Captain of the Sureki",
            "Rasha'nan", "Broodtwister Ovi'nax", "Nexus-Princess Ky'veza",
            "The Silken Court", "Queen Ansurek",
        ],
        "Liberation of Undermine": [
            "Vexie and the Geargrinders", "Cauldron of Carnage",
            "Rik Reverb", "Stix Bunkjunker",
            "Sprocketmonger Lockenstock", "The One-Armed Bandit",
            "Mug'Zee, Heads of Security", "Chrome King Gallywix",
        ],
    },
}

# ── Convenience lookups ───────────────────────────────────────────────────────

# Flat raid → boss list
ALL_RAIDS: dict[str, list[str]] = {
    raid: bosses
    for expansion in RAID_DATABASE.values()
    for raid, bosses in expansion.items()
}

# Raid → expansion name
RAID_EXPANSION: dict[str, str] = {
    raid: expansion
    for expansion, raids in RAID_DATABASE.items()
    for raid in raids
}

# Sorted list of all raid names (for autocomplete)
ALL_RAID_NAMES: list[str] = sorted(ALL_RAIDS.keys())


def get_bosses(raid_name: str) -> list[str]:
    """Return the boss list for a raid, case-insensitive. Returns [] if not found."""
    for name, bosses in ALL_RAIDS.items():
        if name.lower() == raid_name.lower():
            return bosses
    return []


def find_raid(query: str) -> list[str]:
    """
    Return raid names matching a partial, case-insensitive query.
    Used for autocomplete — returns up to 25 results.
    """
    q = query.lower()
    return [name for name in ALL_RAID_NAMES if q in name.lower()][:25]
