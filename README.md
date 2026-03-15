# ⚔️ Wrath of Midnight Raid Bot

A self-hosted Discord bot for managing World of Warcraft guild raid events, roster signups, character registration, and attendance tracking. Built with Python and discord.py 2.0.

---

## Table of Contents

1. [Features Overview](#features-overview)
2. [Prerequisites](#prerequisites)
3. [Step 1 – Create Your Discord Bot Application](#step-1--create-your-discord-bot-application)
4. [Step 2 – Install Python & Dependencies](#step-2--install-python--dependencies)
5. [Step 3 – Configure Your .env File](#step-3--configure-your-env-file)
6. [Step 4 – Run the Bot](#step-4--run-the-bot)
7. [Step 5 – Invite the Bot to Your Server](#step-5--invite-the-bot-to-your-server)
8. [Step 6 – First-Time Server Setup](#step-6--first-time-server-setup)
9. [Command Reference](#command-reference)
   - [/character commands](#character-commands)
   - [/raid commands](#raid-commands)
   - [/attendance commands](#attendance-commands)
   - [/absence commands](#absence-commands)
   - [/admin commands](#admin-commands)
10. [Permissions System](#permissions-system)
11. [Attendance Tracking Guide](#attendance-tracking-guide)
12. [Event & Signup System Guide](#event--signup-system-guide)
13. [Boss Progress Tracking](#boss-progress-tracking)
14. [Automatic Reminders](#automatic-reminders)
15. [Character API Integration](#character-api-integration)
16. [Running as a System Service (Linux)](#running-as-a-system-service-linux)
17. [Running as a System Service (Windows)](#running-as-a-system-service-windows)
18. [Backup & Restore](#backup--restore)
19. [Troubleshooting](#troubleshooting)
20. [FAQ](#faq)

---

## Features Overview

| Feature | Description |
|---|---|
| **Raid Event Management** | Create, edit, and cancel raid events with live interactive signup embeds |
| **Role-Based Signups** | Tank / Healer / DPS buttons with automatic bench management when slots fill |
| **Character Registration** | Register WoW characters with class, spec, and item level |
| **Armory Integration** | Auto-fill character info from Raider.IO or the Blizzard Battle.net API |
| **Attendance Tracking** | Mark members present/late/excused/absent; generate threshold reports and CSV exports |
| **Absence Requests** | Members submit excused absences before events; absences are excluded from their % |
| **Boss Progress Tracking** | Set a raid's boss list from a 373-boss database and mark kills live |
| **Event Templates** | Save a raid as a template and re-use it with a new date in seconds |
| **Automatic Reminders** | DMs / channel pings at 24h, 2h, 30m, and 5m before every event |
| **Auto-Archive** | Completed events are automatically archived 6 hours after they end |
| **Multi-Channel Support** | Post events to any combination of channels; per-channel labeling |
| **Auto Guild Registration** | Inviting the bot to a new server instantly syncs commands and saves the guild ID |
| **Data Export** | Export all guild data (events, signups, characters, attendance) as JSON |
| **Self-Update** | `/admin update` pulls the latest code from git and restarts the bot |

---

## Prerequisites

- **Python 3.10+** (3.11 or 3.12 recommended)
- **git** installed and available in your PATH
- A machine that can run a process 24/7 (Linux VPS, Windows Server, Raspberry Pi, etc.)
- A Discord account with a server where you have administrator rights

---

## Step 1 – Create Your Discord Bot Application

1. Go to [https://discord.com/developers/applications](https://discord.com/developers/applications) and click **New Application**.
2. Give it a name (e.g. `Wrath of Midnight`), click **Create**.
3. In the left sidebar click **Bot**, then click **Add Bot** → **Yes, do it!**
4. Under **Token**, click **Reset Token** and copy the token — you will paste this into `.env` later. **Never share this token.**
5. Scroll down to **Privileged Gateway Intents** and enable:
   - **Server Members Intent**
   - **Message Content Intent**
6. Click **Save Changes**.
7. In the left sidebar click **OAuth2 → URL Generator**:
   - Under **Scopes** tick: `bot` and `applications.commands`
   - Under **Bot Permissions** tick: `Send Messages`, `Embed Links`, `Attach Files`, `Read Message History`, `Use External Emojis`, `Add Reactions`, `Manage Messages`
8. Copy the generated URL at the bottom — this is your invite link (used in Step 5).

---

## Step 2 – Install Python & Dependencies

```bash
# Clone the repository
git clone https://github.com/Rantark/Wrathofmidnight_raidbot.git
cd Wrathofmidnight_raidbot

# Create and activate a virtual environment (recommended)
python3 -m venv .venv
source .venv/bin/activate          # Linux / macOS
# .venv\Scripts\activate           # Windows

# Install dependencies
pip install -r requirements.txt
```

**Dependencies installed:**

| Package | Purpose |
|---|---|
| `discord.py >= 2.3.0` | Discord API library with slash command support |
| `python-dotenv >= 1.0.0` | Loads `.env` configuration file |
| `aiosqlite >= 0.19.0` | Async SQLite for non-blocking database access |
| `pytz >= 2023.3` | Timezone-aware event display |
| `aiohttp >= 3.9.0` | Async HTTP client for Raider.IO / Battle.net API |
| `APScheduler >= 3.10.0` | Task scheduling support |

---

## Step 3 – Configure Your .env File

Copy the example config and fill it in:

```bash
cp .env.example .env
nano .env   # or use your preferred editor
```

### All Configuration Options

```ini
# ──────────────────────────────────────────────────────
# REQUIRED — bot will not start without these
# ──────────────────────────────────────────────────────

# Your Discord bot token from the Developer Portal
DISCORD_TOKEN=your_bot_token_here

# Comma-separated Discord server (guild) IDs for instant command syncing.
# Enables slash commands in those servers immediately without the ~1 hour
# global propagation delay.
# Right-click server name → Copy Server ID (requires Developer Mode enabled).
# Leave blank to use global sync only.
# Note: When you invite the bot to a new server this is updated automatically.
GUILD_IDS=123456789012345678,987654321098765432

# ──────────────────────────────────────────────────────
# OPTIONAL — sensible defaults are provided
# ──────────────────────────────────────────────────────

# Default channel ID where raid events are posted
EVENT_CHANNEL_ID=

# Attendance % below which members appear in low-attendance reports (default: 75)
ATTENDANCE_WARNING_THRESHOLD=75

# Timezone for all event display (default: America/New_York)
# Full list: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones
TIMEZONE=America/New_York

# Channel ID for bot audit log messages (optional)
LOG_CHANNEL_ID=

# Prefix for legacy text commands (default: !)
COMMAND_PREFIX=!

# SQLite database file path (default: ./data/raidbot.db)
DATABASE_PATH=./data/raidbot.db

# ──────────────────────────────────────────────────────
# OPTIONAL — Blizzard Battle.net API (enables Armory lookup)
# Create a client at https://develop.battle.net/access/clients
# Enables /character add realm:<realm> to auto-fill class/spec/ilvl
# and /character sync to refresh stats from the Armory.
# ──────────────────────────────────────────────────────
BNET_CLIENT_ID=
BNET_CLIENT_SECRET=
```

> **Tip – How to enable Developer Mode in Discord:**
> User Settings → Advanced → Developer Mode → toggle on.
> You can then right-click any server or channel to **Copy ID**.

---

## Step 4 – Run the Bot

```bash
# Make sure your virtual environment is active
source .venv/bin/activate

# Start the bot
python bot.py
```

You should see output similar to:
```
============================================================
Bot online: Wrath of Midnight#1234 (ID: 123456789012345678)
Version:  1.5.1
Guild IDs: [123456789012345678]
Database: ./data/raidbot.db
============================================================
```

Logs are written to `./logs/raidbot.log` (rotated daily, 7-day retention) and also printed to the console.

---

## Step 5 – Invite the Bot to Your Server

Paste the OAuth2 URL you generated in Step 1 into your browser. Select your server and click **Authorise**.

**What happens automatically when the bot joins a new server:**
- Slash commands are synced to that server immediately (no ~1 hour wait)
- The server's guild ID is appended to `GUILD_IDS` in your `.env` file automatically
- No restart required — the bot is instantly usable

---

## Step 6 – First-Time Server Setup

Run these commands once in your Discord server as a server administrator:

```
1. /admin set_event_channel  #your-raids-channel
2. /admin roster_config  tanks:2  healers:5  dps:13
3. /admin attendance_threshold  75
4. /admin set_raid_leader  @YourRaidLeader  role:raid_leader
5. /admin set_log_channel  #bot-logs         ← optional
```

That's it. Your raid leaders can now create events with `/raid create`.

---

## Command Reference

Slash commands are grouped into five categories. All commands are sent as `/group subcommand`.

---

### `/character` Commands

Manage your WoW characters. Every guild member can use these.

---

#### `/character add`

Register a new WoW character to your profile.

| Parameter | Required | Description |
|---|---|---|
| `name` | Yes | Character name (2–12 letters, letters only) |
| `realm` | No | Realm slug for Armory auto-fill (e.g. `stormrage`, `area-52`) |
| `region` | No | Region for API lookup: `us`, `eu`, `kr`, `tw` (default: `us`) |
| `char_class` | If no realm | WoW class (e.g. `Warrior`, `Mage`) — auto-filled if realm provided |
| `main_spec` | If no realm | Main spec (e.g. `Protection`, `Frost`) — auto-filled if realm provided |
| `off_spec` | No | Off-spec (optional) |
| `ilvl` | No | Item level (1–700) — auto-filled if realm provided |

**Examples:**
```
/character add name:Arthax realm:stormrage region:us
/character add name:Arthax char_class:Warrior main_spec:Protection ilvl:480
```

If `realm` is provided, the bot queries Raider.IO (then Blizzard Armory as fallback) to auto-fill class, spec, item level, race, and avatar. If no realm is given, you must supply `char_class` and `main_spec` manually.

Your first added character is automatically set as your main and will be used when you sign up for raids.

---

#### `/character main`

Set one of your registered characters as your main. Your main is used for automatic role detection when you click a signup button.

| Parameter | Required | Description |
|---|---|---|
| `name` | Yes | Name of the character to set as main |

```
/character main name:Arthax
```

---

#### `/character list`

View all characters you have registered in this server, including class, spec, item level, and which one is your main.

```
/character list
```

---

#### `/character update`

Update an existing character's spec or item level.

| Parameter | Required | Description |
|---|---|---|
| `name` | Yes | Character name to update |
| `spec` | No | New main spec |
| `off_spec` | No | New off-spec |
| `ilvl` | No | New item level (1–700) |

```
/character update name:Arthax spec:Arms ilvl:490
```

---

#### `/character remove`

Delete a character from your profile.

| Parameter | Required | Description |
|---|---|---|
| `name` | Yes | Character name to delete |

```
/character remove name:Arthax
```

---

#### `/character sync`

Re-fetch class, spec, item level, and avatar from Raider.IO / Blizzard Armory. The character must have been added with a realm originally.

| Parameter | Required | Description |
|---|---|---|
| `name` | Yes | Character name to sync |

```
/character sync name:Arthax
```

---

#### `/character info`

View another member's registered characters.

| Parameter | Required | Description |
|---|---|---|
| `member` | Yes | The Discord member to look up (@ mention) |

```
/character info member:@Rantark
```

---

### `/raid` Commands

Create and manage raid events. Most commands require **Raid Leader** or **Officer** permissions. `/raid list` and `/raid info` are available to everyone.

---

#### `/raid create`

Create a new raid event. An interactive signup embed is posted to the event channel with Tank / Healer / DPS / Tentative / Decline buttons. Reminders are automatically scheduled at 24h, 2h, 30m, and 5m before the event.

| Parameter | Required | Description |
|---|---|---|
| `name` | Yes | Event name (e.g. `Heroic Vault of the Incarnates`) |
| `date` | Yes | Date in `YYYY-MM-DD` or `MM/DD/YYYY` format |
| `time` | Yes | Start time — accepts `20:00`, `8:00 PM`, `8 PM` |
| `event_type` | Yes | One of the predefined event types (see below) |
| `description` | No | Optional description shown on the embed |
| `channel` | No | Channel to post in (defaults to your configured event channel) |
| `max_tanks` | No | Maximum tank slots (overrides server default) |
| `max_healers` | No | Maximum healer slots (overrides server default) |
| `max_dps` | No | Maximum DPS slots (overrides server default) |

**Available event types:**
- `Normal Raid`
- `Heroic Raid`
- `Mythic Raid`
- `Mythic+ Night`
- `PvP - RBG`
- `PvP - Arena`
- `Achievement Run`
- `Alt Raid`
- `Social Event`

```
/raid create name:"Heroic Vault" date:2025-03-20 time:20:00 event_type:"Heroic Raid" max_tanks:2 max_healers:5 max_dps:13
```

---

#### `/raid edit`

Edit an existing active event. The signup embed updates live — no need to re-post it.

| Parameter | Required | Description |
|---|---|---|
| `event_id` | Yes | The event ID (shown on the embed footer) |
| `name` | No | New event name |
| `date` | No | New date |
| `time` | No | New time |
| `description` | No | New description |
| `max_tanks` | No | New tank cap |
| `max_healers` | No | New healer cap |
| `max_dps` | No | New DPS cap |

```
/raid edit event_id:5 time:21:00 description:"Starting one hour later this week"
```

---

#### `/raid cancel`

Cancel an active event. The embed is updated to show the cancellation.

| Parameter | Required | Description |
|---|---|---|
| `event_id` | Yes | The event ID to cancel |
| `reason` | No | Optional cancellation reason shown to members |

```
/raid cancel event_id:5 reason:"Not enough signups"
```

---

#### `/raid lock`

Toggle the signup lock on an event. When locked, members cannot add or change their signup. Existing signups are preserved.

| Parameter | Required | Description |
|---|---|---|
| `event_id` | Yes | The event ID to lock/unlock |

```
/raid lock event_id:5
```

---

#### `/raid list`

Show all upcoming active events for this server sorted by date and time. Available to all members.

```
/raid list
```

---

#### `/raid info`

Show the full details and current roster for a specific event. Available to all members.

| Parameter | Required | Description |
|---|---|---|
| `event_id` | Yes | The event ID to view |

```
/raid info event_id:5
```

---

#### `/raid template save`

Save an existing event as a reusable template. Templates capture the event name, type, time, description, and roster caps — not the specific date or who signed up.

| Parameter | Required | Description |
|---|---|---|
| `event_id` | Yes | The event to save as a template |
| `template_name` | Yes | A name for the template (e.g. `weekly-heroic`) |

```
/raid template save event_id:5 template_name:weekly-heroic
```

---

#### `/raid template load`

Create a new event from a saved template. You only need to provide the new date — everything else is pre-filled from the template.

| Parameter | Required | Description |
|---|---|---|
| `template_name` | Yes | The template to load |
| `date` | Yes | The date for the new event |

```
/raid template load template_name:weekly-heroic date:2025-03-27
```

---

#### `/raid template list`

List all saved templates for this server.

```
/raid template list
```

---

#### `/raid template delete`

Permanently delete a template.

| Parameter | Required | Description |
|---|---|---|
| `template_name` | Yes | Template to delete |

```
/raid template delete template_name:old-template
```

---

#### `/raid bosses set`

Set the boss list for an event from the built-in WoW raid database (373 bosses across 80+ raids from Classic through Midnight). A separate boss progress embed is posted to the channel.

| Parameter | Required | Description |
|---|---|---|
| `event_id` | Yes | The event to attach bosses to |
| `raid_name` | Yes | Raid name (autocomplete from the full boss database) |

```
/raid bosses set event_id:5 raid_name:"Vault of the Incarnates"
```

---

#### `/raid bosses show`

Display the current boss progress embed for an event.

| Parameter | Required | Description |
|---|---|---|
| `event_id` | Yes | The event to show boss progress for |

```
/raid bosses show event_id:5
```

---

#### `/raid bosses mark`

Toggle a single boss as defeated or alive. The progress embed updates live.

| Parameter | Required | Description |
|---|---|---|
| `event_id` | Yes | The event |
| `boss_name` | Yes | The boss to toggle (autocomplete available) |

```
/raid bosses mark event_id:5 boss_name:"Eranog"
```

---

#### `/raid bosses reset`

Reset all bosses in an event to alive (undoes all kills).

| Parameter | Required | Description |
|---|---|---|
| `event_id` | Yes | The event to reset |

```
/raid bosses reset event_id:5
```

---

#### `/raid bosses clear`

Remove all bosses from an event entirely (deletes the progress embed).

| Parameter | Required | Description |
|---|---|---|
| `event_id` | Yes | The event to clear |

```
/raid bosses clear event_id:5
```

---

### `/attendance` Commands

Track and report attendance. Marking and reporting require **Raid Leader** or **Officer** permissions. Members can view their own stats freely.

---

#### `/attendance mark`

Open an interactive menu to mark attendance for every member who signed up to an event. Each signup can be marked as:

- ✅ **Present** — showed up on time
- ⏰ **Late** — arrived after the start
- 🔵 **Excused** — submitted an absence request (automatically pre-filled from `/absence request`)
- ❌ **Absent** — expected but didn't show up

Members not explicitly marked default to **Absent**.

| Parameter | Required | Description |
|---|---|---|
| `event_id` | Yes | The event to mark attendance for |

```
/attendance mark event_id:5
```

---

#### `/attendance view`

View attendance statistics for yourself or another member. Shows:
- Total events attended, late arrivals, excused, unexcused absences
- 30-day attendance percentage
- All-time attendance percentage
- Last 10 events history

| Parameter | Required | Description |
|---|---|---|
| `member` | No | The member to view (defaults to yourself) |

```
/attendance view
/attendance view member:@Rantark
```

---

#### `/attendance report`

Show a report of all guild members whose attendance is below the configured threshold (default 75%). Officers only.

| Parameter | Required | Description |
|---|---|---|
| `start_date` | No | Filter to events on or after this date (YYYY-MM-DD) |
| `end_date` | No | Filter to events on or before this date (YYYY-MM-DD) |
| `export_csv` | No | `True` to receive the report as a downloadable CSV file |

```
/attendance report
/attendance report start_date:2025-01-01 export_csv:True
```

---

#### `/attendance event`

Show a full attendance breakdown for a single event — who was present, late, excused, and absent with character names listed. Raid leaders only.

| Parameter | Required | Description |
|---|---|---|
| `event_id` | Yes | The event to view |

```
/attendance event event_id:5
```

---

### `/absence` Commands

Members use these to submit excused absences before a raid. Available to all members.

---

#### `/absence request`

Submit an excused absence for an upcoming event. This:
- Records your absence with your reason
- Pre-fills your status as **Excused** when a raid leader runs `/attendance mark`
- Excludes the event from your attendance percentage denominator (so it doesn't hurt your %)

| Parameter | Required | Description |
|---|---|---|
| `event_id` | Yes | The event you'll be missing |
| `reason` | Yes | Reason for the absence (visible to raid leaders) |

```
/absence request event_id:5 reason:"Travelling for work this week"
```

---

#### `/absence list`

View your last 20 submitted absence requests in this server, including event ID, reason, and submission date.

```
/absence list
```

---

#### `/absence event_list`

View all absence requests submitted for a specific event. Raid leaders only.

| Parameter | Required | Description |
|---|---|---|
| `event_id` | Yes | The event to check |

```
/absence event_list event_id:5
```

---

### `/admin` Commands

Server configuration and bot administration. All `/admin` commands require Discord **Server Administrator** permission.

---

#### `/admin set_raid_leader`

Grant a member Raid Leader or Officer permissions within the bot.

| Parameter | Required | Description |
|---|---|---|
| `member` | Yes | The member to promote |
| `role` | No | `raid_leader` or `officer` (default: `raid_leader`) |

**Permission differences:**
- **Raid Leader** — create/edit/cancel events, lock rosters, mark attendance, view reports, save templates
- **Officer** — all Raid Leader powers + export CSV attendance reports + view event absence lists

```
/admin set_raid_leader member:@Healbot role:officer
```

---

#### `/admin remove_raid_leader`

Revoke a member's bot role (Raid Leader or Officer). They revert to regular member access.

| Parameter | Required | Description |
|---|---|---|
| `member` | Yes | The member to demote |

```
/admin remove_raid_leader member:@Healbot
```

---

#### `/admin list_permissions`

Show all members who have been granted bot-level roles (Raid Leader / Officer) in this server.

```
/admin list_permissions
```

---

#### `/admin set_event_channel`

Set the default channel where new raid events are posted. Also registers the channel in the multi-channel list.

| Parameter | Required | Description |
|---|---|---|
| `channel` | Yes | The text channel to use as the default |

```
/admin set_event_channel channel:#raid-signups
```

---

#### `/admin add_event_channel`

Add an additional channel to the event channel list. When a raid leader runs `/raid create`, they can optionally pick from this list to post to a specific channel.

| Parameter | Required | Description |
|---|---|---|
| `channel` | Yes | The channel to add |
| `label` | No | Friendly name for the channel (e.g. `Heroic Raids`) |

```
/admin add_event_channel channel:#mythic-signups label:"Mythic Prog"
```

---

#### `/admin remove_event_channel`

Remove a channel from the event channel list.

| Parameter | Required | Description |
|---|---|---|
| `channel` | Yes | The channel to remove |

```
/admin remove_event_channel channel:#old-channel
```

---

#### `/admin list_event_channels`

Show all registered event channels with their labels. The default channel is marked with a ⭐.

```
/admin list_event_channels
```

---

#### `/admin set_log_channel`

Set a channel where the bot posts audit log messages (role changes, event creations, admin actions).

| Parameter | Required | Description |
|---|---|---|
| `channel` | Yes | The text channel for audit logs |

```
/admin set_log_channel channel:#bot-logs
```

---

#### `/admin roster_config`

Set the default tank/healer/DPS slot counts used when creating new events. These can always be overridden per-event in `/raid create`.

| Parameter | Required | Description |
|---|---|---|
| `tanks` | Yes | Default max tank slots (0–40) |
| `healers` | Yes | Default max healer slots (0–40) |
| `dps` | Yes | Default max DPS slots (0–40) |

```
/admin roster_config tanks:2 healers:5 dps:13
```

---

#### `/admin attendance_threshold`

Set the attendance percentage below which members will appear in `/attendance report` as flagged for low attendance.

| Parameter | Required | Description |
|---|---|---|
| `percentage` | Yes | Threshold percentage (0–100, default: 75) |

```
/admin attendance_threshold percentage:80
```

---

#### `/admin status`

View a complete overview of the bot's current configuration for this server: channels, roster defaults, attendance threshold, timezone, database path, and bot version.

```
/admin status
```

---

#### `/admin sync`

Manually sync slash commands to this server. Use this if commands aren't showing up after an invite or an update.

```
/admin sync
```

---

#### `/admin export_data`

Export all of this server's bot data (settings, characters, events, signups, attendance records, absences) as a JSON file sent to you in a private message. Useful for backups or migration.

```
/admin export_data
```

---

#### `/admin restart`

Gracefully restart the bot process. The bot sends a visible message before shutting down so your guild knows what's happening, then comes back online automatically.

```
/admin restart
```

---

#### `/admin update`

Run `git pull` to fetch the latest code, then restart the bot automatically if new commits were downloaded. If the repo is already up to date, the bot does **not** restart.

```
/admin update
```

---

## Permissions System

The bot uses a four-tier permission system:

| Tier | Who | Access |
|---|---|---|
| **Member** | Everyone | Sign up for events, register characters, view own attendance, submit absence requests |
| **Raid Leader** | Granted via `/admin set_raid_leader` | All member access + create/edit/cancel events, lock rosters, mark attendance, view attendance reports, save/load templates, boss tracking |
| **Officer** | Granted via `/admin set_raid_leader role:officer` | All Raid Leader access + CSV attendance exports, event absence lists |
| **Server Admin** | Discord server administrator role | All of the above + all `/admin` configuration commands |

> Discord server administrators always have full bot access regardless of bot role assignments.

---

## Attendance Tracking Guide

### How Attendance is Calculated

```
Attendance % = (Present + Late) / (Total Events − Excused) × 100
```

- **Present** and **Late** both count as attended
- **Excused** absences are removed from the denominator entirely (they don't penalise the member)
- **Absent** (unexcused) counts as a missed event

### Workflow

1. **Member submits an absence** (optional but recommended):
   ```
   /absence request event_id:12 reason:"Family commitment"
   ```

2. **Raid leader marks attendance after the event:**
   ```
   /attendance mark event_id:12
   ```
   This opens an interactive panel. Anyone who submitted an absence is pre-marked Excused.

3. **Members check their own stats:**
   ```
   /attendance view
   ```

4. **Officers generate reports:**
   ```
   /attendance report
   /attendance report start_date:2025-01-01 export_csv:True
   ```

### Attendance Threshold

Set with `/admin attendance_threshold`. Members below this percentage appear in `/attendance report`. The default is **75%**. Adjust it to fit your guild's expectations.

---

## Event & Signup System Guide

### Creating an Event

```
/raid create name:"Heroic Amirdrassil" date:2025-03-20 time:20:00 event_type:"Heroic Raid"
```

The bot posts an embed to your event channel containing:
- Event name, type, date, time, and description
- Current roster broken into **Tanks**, **Healers**, and **DPS** sections
- A **Bench** section for overflow signups
- **Tentative** and **Declined** sections
- Five buttons: 🛡️ Tank · 💚 Healer · ⚔️ DPS · ❓ Tentative · ❌ Decline

### Signing Up

Members click a button on the embed. The bot:
1. Looks up their main character's class and spec
2. Determines their role automatically (e.g. a Protection Paladin clicking DPS still signs up under their selected role)
3. Adds them to the confirmed list if slots are open, or the bench if the role is full
4. Updates the embed live

### Bench Promotion

When a confirmed signup changes to Tentative or Declined, the first person on the bench for that role is automatically promoted to Confirmed. The embed updates immediately.

### Locking the Roster

```
/raid lock event_id:12
```

Locked rosters prevent new signups or changes. The embed shows a **LOCKED** banner. Useful once you've finalized your composition.

### Event Lifecycle

```
active → (auto-archive after 6h past event time) → completed
active → /raid cancel → cancelled
```

---

## Boss Progress Tracking

Set a boss list for any event using the built-in 373-boss database:

```
/raid bosses set event_id:12 raid_name:"Amirdrassil, the Dream's Hope"
```

A separate embed is posted to the event channel showing all bosses with ⚔️ (alive) or ✅ (defeated) icons and a progress bar.

During the raid, mark bosses as killed:
```
/raid bosses mark event_id:12 boss_name:"Gnarlroot"
```

The embed updates live. Reset progress or clear the boss list at any time:
```
/raid bosses reset event_id:12
/raid bosses clear event_id:12
```

---

## Automatic Reminders

Reminders are scheduled automatically when an event is created. The bot sends a message to the event channel at:

| Before event | Message |
|---|---|
| 24 hours | Reminder embed with current signup count |
| 2 hours | Reminder embed with current signup count |
| 30 minutes | Reminder embed with current signup count |
| 5 minutes | Reminder embed + `@here` ping |

Reminders for cancelled or already-completed events are silently skipped.

---

## Character API Integration

The bot supports two character data sources:

### Raider.IO (Primary — no credentials needed)

Automatically used when you provide a `realm` in `/character add`. Returns class, spec, item level, race, and thumbnail.

### Blizzard Battle.net API (Secondary — credentials required)

Used as a fallback if Raider.IO doesn't return results. To enable it:

1. Go to [https://develop.battle.net/access/clients](https://develop.battle.net/access/clients)
2. Create a new client, set the redirect URI to `https://localhost`
3. Copy the **Client ID** and **Client Secret** into your `.env`:
   ```ini
   BNET_CLIENT_ID=your_client_id
   BNET_CLIENT_SECRET=your_client_secret
   ```
4. Restart the bot

> If neither API is configured, `/character add` still works — you just need to enter class and spec manually.

---

## Running as a System Service (Linux)

To keep the bot running after you close your terminal and have it restart automatically on failure:

**1. Create a systemd service file:**

```bash
sudo nano /etc/systemd/system/raidbot.service
```

**2. Paste and edit the following:**

```ini
[Unit]
Description=Wrath of Midnight Raid Bot
After=network.target

[Service]
Type=simple
User=YOUR_USERNAME
WorkingDirectory=/path/to/Wrathofmidnight_raidbot
ExecStart=/path/to/Wrathofmidnight_raidbot/.venv/bin/python bot.py
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

**3. Enable and start the service:**

```bash
sudo systemctl daemon-reload
sudo systemctl enable raidbot
sudo systemctl start raidbot
```

**4. Useful management commands:**

```bash
sudo systemctl status raidbot          # Check if running
sudo systemctl restart raidbot         # Restart manually
sudo journalctl -u raidbot -f          # Follow live logs
sudo journalctl -u raidbot --since today   # Today's logs
```

---

## Running as a System Service (Windows)

Use **NSSM (Non-Sucking Service Manager)** to run the bot as a Windows service:

**1. Download NSSM** from [https://nssm.cc/download](https://nssm.cc/download) and place `nssm.exe` somewhere in your PATH.

**2. Install the service** (run in an Administrator command prompt):

```cmd
nssm install RaidBot "C:\path\to\.venv\Scripts\python.exe" "C:\path\to\Wrathofmidnight_raidbot\bot.py"
nssm set RaidBot AppDirectory "C:\path\to\Wrathofmidnight_raidbot"
nssm set RaidBot Start SERVICE_AUTO_START
nssm start RaidBot
```

**3. Manage the service:**

```cmd
nssm status RaidBot
nssm restart RaidBot
nssm stop RaidBot
```

---

## Backup & Restore

### Backup

The entire bot state lives in one SQLite file. Back it up with:

```bash
cp ./data/raidbot.db ./data/raidbot.db.bak

# Or for a timestamped backup:
cp ./data/raidbot.db "./data/raidbot_$(date +%Y%m%d).db"
```

You can also use the in-Discord export:
```
/admin export_data
```
This exports all data as JSON attached to a DM.

### Restore

```bash
# Stop the bot first
sudo systemctl stop raidbot

# Replace the database
cp ./data/raidbot_backup.db ./data/raidbot.db

# Restart
sudo systemctl start raidbot
```

### Automated Daily Backup (Linux cron)

```bash
crontab -e
```

Add this line (backs up every day at 3 AM, keeps 30 days):
```
0 3 * * * cp /path/to/data/raidbot.db /path/to/backups/raidbot_$(date +\%Y\%m\%d).db && find /path/to/backups -name "raidbot_*.db" -mtime +30 -delete
```

---

## Troubleshooting

### Commands aren't showing up in Discord

- Wait up to 1 hour for global propagation, or
- Run `/admin sync` in your server, or
- Ensure your guild ID is in `GUILD_IDS` in `.env` (this happens automatically when you invite the bot)

### Bot is online but not responding to slash commands

1. Confirm the bot has `applications.commands` scope (re-invite using the OAuth2 URL from Step 1)
2. Check that `Message Content Intent` and `Server Members Intent` are enabled in the Developer Portal
3. Check `./logs/raidbot.log` for error messages

### `DISCORD_TOKEN` errors on startup

- Ensure `.env` exists in the project root (not `.env.example`)
- Verify there are no spaces around the `=` sign: `DISCORD_TOKEN=abc123` not `DISCORD_TOKEN = abc123`
- Reset the token in the Developer Portal if you think it was leaked

### "Unknown interaction" or buttons not working

- The bot must be running when a button is clicked — buttons send an interaction to the bot in real time
- If you restarted the bot, old embeds with buttons will still work as long as the bot is now running

### Character sync / Armory lookup returns "not found"

- Verify the realm slug is correct (use hyphens, no spaces — e.g. `area-52`, not `Area 52`)
- Some characters may not be indexed on Raider.IO; configure Blizzard API credentials as a fallback
- Check that the character name spelling is correct (case-insensitive but must match exactly)

### Database errors

- Ensure `./data/` directory exists or set `DATABASE_PATH` to a writable location
- The bot creates the database and all tables automatically on first run

### `/admin update` fails

- Ensure git is installed and the bot was cloned (not downloaded as a ZIP)
- The bot user must have read permissions on the repository directory
- Check for local uncommitted changes that may block `git pull`

---

## FAQ

**Q: Can the bot manage multiple Discord servers?**
Yes. The bot runs globally and maintains separate settings, characters, events, and attendance records for each server. When invited to a new server its commands sync automatically and the guild ID is saved to `.env`.

**Q: Do I need a Blizzard API key?**
No. Raider.IO is used by default for character lookups and requires no credentials. The Blizzard API is an optional fallback for characters not found on Raider.IO.

**Q: What happens if I restart the bot mid-raid?**
All data is stored in SQLite. Signups, characters, and attendance records persist across restarts. The signup embed buttons resume working as soon as the bot comes back online.

**Q: Can members sign up with a different character than their main?**
Members click the role buttons (Tank/Healer/DPS) and the bot uses their registered main character. To sign up on an alt, they should change their main first with `/character main`.

**Q: How do I move the bot to a different machine?**
Copy the entire project directory, including `.env` and `./data/raidbot.db`. Install dependencies on the new machine and start the bot. No other migration steps are needed.

**Q: Can I have different roster sizes for different events?**
Yes. The `/raid create` command accepts `max_tanks`, `max_healers`, and `max_dps` parameters that override the server defaults for that specific event. Server-wide defaults are configured with `/admin roster_config`.

**Q: What WoW expansions does boss tracking support?**
The built-in database covers raids from Classic through the Midnight expansion (373 bosses across 80+ raids). Autocomplete on `/raid bosses set` lets you search the full list.

**Q: How do I update the bot?**
Run `/admin update` in Discord. The bot pulls the latest code from git and restarts automatically. Or manually:
```bash
git pull
sudo systemctl restart raidbot
```

---

*Wrath of Midnight Raid Bot — built for guilds, by players.*
