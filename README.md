# ⚔️ Wrath of Midnight Raid Bot

A self-hosted Discord bot for managing World of Warcraft guild raid events, roster signups, and attendance tracking.  Built with Python and discord.py.

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
10. [Permissions System](#permissions-system)
11. [Attendance Tracking Guide](#attendance-tracking-guide)
12. [Event & Signup System Guide](#event--signup-system-guide)
13. [Running as a System Service (Linux)](#running-as-a-system-service-linux)
14. [Backup & Restore](#backup--restore)
15. [Troubleshooting](#troubleshooting)
16. [FAQ](#faq)

---

## Features Overview

| Feature | Description |
|---------|-------------|
| **Character Management** | Register WoW characters with class/spec validation |
| **Event Creation** | Create raids, M+ nights, PvP sessions with date/time |
| **One-Click Signups** | Button-based Tank / Healer / DPS / Tentative / Decline |
| **Auto-Roster Embeds** | Live-updating embed shows roster as people sign up |
| **Role Overflow** | Excess signups auto-move to bench in signup-time order |
| **Attendance Tracking** | Mark present/late/absent/excused after each event |
| **Absence Requests** | Members submit excused absences before events |
| **Attendance Stats** | Per-member stats with 30-day and all-time percentages |
| **Low-Attendance Alerts** | Officers see who's below the configured threshold |
| **Event Templates** | Save and reuse event configs for recurring raids |
| **Automated Reminders** | 24h / 2h / 30m / 5m reminders in the event channel |
| **Data Export** | Export everything to JSON or attendance to CSV |
| **Admin Controls** | Set channels, thresholds, roster defaults, permissions |

---

## Prerequisites

Before setting up the bot, make sure you have:

- **Python 3.10 or newer** — [Download Python](https://www.python.org/downloads/)
- **A Discord account** with permissions to manage a server
- **A server** where you have Administrator access
- **Git** (optional, for cloning) — [Download Git](https://git-scm.com/)

---

## Step 1 – Create Your Discord Bot Application

### 1.1  Create the Application

1. Go to [https://discord.com/developers/applications](https://discord.com/developers/applications)
2. Click **New Application** in the top-right corner
3. Give it a name (e.g. `Wrath of Midnight Raid Bot`) and click **Create**

### 1.2  Create the Bot User

1. In the left sidebar, click **Bot**
2. Click **Add Bot** → **Yes, do it!**
3. Under **Token**, click **Reset Token** then **Copy** — **save this somewhere safe, you will need it shortly**
   > ⚠️ **Never share your bot token.** Anyone with it has full control of your bot.

### 1.3  Enable Required Intents

Still on the **Bot** page, scroll down to **Privileged Gateway Intents** and enable:

- ✅ **Server Members Intent** — required for member lookups
- ✅ **Message Content Intent** — required for prefix commands

Click **Save Changes**.

### 1.4  Note Your Bot Token

You will enter this token into the `.env` file in Step 3.

---

## Step 2 – Install Python & Dependencies

### 2.1  Verify Python Version

```bash
python --version
# or
python3 --version
```

You need **3.10 or higher**.  If your version is older, download a newer version from [python.org](https://www.python.org/downloads/).

### 2.2  Download the Bot Files

**Option A – Clone with Git:**
```bash
git clone https://github.com/your-org/Wrathofmidnight_raidbot.git
cd Wrathofmidnight_raidbot
```

**Option B – Download ZIP:**
Download and extract the ZIP file, then open a terminal/command prompt in the folder.

### 2.3  Create a Virtual Environment (Recommended)

A virtual environment keeps the bot's dependencies separate from your system Python:

**Windows:**
```cmd
python -m venv venv
venv\Scripts\activate
```

**Linux / macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

> You'll see `(venv)` in your prompt when the virtual environment is active.  You need to activate it every time you open a new terminal to run the bot.

### 2.4  Install Dependencies

```bash
pip install -r requirements.txt
```

This installs:
- `discord.py` — Discord API library
- `python-dotenv` — Environment variable loading
- `APScheduler` — Reminder scheduling
- `aiosqlite` — Async SQLite database
- `pytz` — Timezone handling
- `aiohttp` — HTTP client

---

## Step 3 – Configure Your .env File

### 3.1  Copy the Example File

**Windows:**
```cmd
copy .env.example .env
```

**Linux / macOS:**
```bash
cp .env.example .env
```

### 3.2  Edit the .env File

Open `.env` in a text editor (Notepad, VS Code, nano, etc.) and fill in the values:

```env
# REQUIRED
DISCORD_TOKEN=your_bot_token_here       ← Paste your bot token from Step 1.3
GUILD_ID=123456789012345678             ← Your Discord server ID (see below)

# OPTIONAL
EVENT_CHANNEL_ID=123456789012345678     ← Where raid event posts appear
ATTENDANCE_WARNING_THRESHOLD=75        ← Attendance % to flag as low
TIMEZONE=America/New_York              ← Your guild's timezone
```

### 3.3  How to Find Your Server ID

1. Open Discord
2. Go to **User Settings** → **Advanced** → enable **Developer Mode**
3. Right-click your server name in the left sidebar
4. Click **Copy Server ID**
5. Paste it into `GUILD_ID=`

### 3.4  How to Find a Channel ID

1. Right-click the channel name in Discord
2. Click **Copy Channel ID**
3. Paste it into `EVENT_CHANNEL_ID=`

### 3.5  Timezone Reference

Common timezones:

| Region | Timezone String |
|--------|-----------------|
| US Eastern | `America/New_York` |
| US Central | `America/Chicago` |
| US Mountain | `America/Denver` |
| US Pacific | `America/Los_Angeles` |
| UK / Ireland | `Europe/London` |
| Central Europe | `Europe/Berlin` |
| Australia Eastern | `Australia/Sydney` |

Full list: [https://en.wikipedia.org/wiki/List_of_tz_database_time_zones](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones)

---

## Step 4 – Run the Bot

Make sure your virtual environment is active (`(venv)` visible in prompt), then:

```bash
python bot.py
```

**Expected output on first run:**
```
[2024-03-12 20:00:00] [INFO    ] __main__: Initialising database…
[2024-03-12 20:00:00] [INFO    ] __main__: Loading cogs…
[2024-03-12 20:00:00] [INFO    ] __main__:   ✓ cogs.characters
[2024-03-12 20:00:00] [INFO    ] __main__:   ✓ cogs.events
[2024-03-12 20:00:00] [INFO    ] __main__:   ✓ cogs.attendance
[2024-03-12 20:00:00] [INFO    ] __main__:   ✓ cogs.admin
[2024-03-12 20:00:00] [INFO    ] __main__: Synced 22 slash commands to guild 123456789
[2024-03-12 20:00:01] [INFO    ] __main__: ============================================================
[2024-03-12 20:00:01] [INFO    ] __main__: Bot online: WrathBot#1234 (ID: 987654321)
```

**To stop the bot:** press `Ctrl+C`

---

## Step 5 – Invite the Bot to Your Server

### 5.1  Generate an Invite Link

1. Go back to [https://discord.com/developers/applications](https://discord.com/developers/applications)
2. Select your application → **OAuth2** → **URL Generator**
3. Under **Scopes**, check:
   - ✅ `bot`
   - ✅ `applications.commands`
4. Under **Bot Permissions**, check:
   - ✅ **View Channels**
   - ✅ **Send Messages**
   - ✅ **Embed Links**
   - ✅ **Attach Files**
   - ✅ **Read Message History**
   - ✅ **Add Reactions**
   - ✅ **Use External Emojis**
   - ✅ **Manage Messages** (to edit live roster embeds)
5. Copy the generated URL at the bottom

### 5.2  Invite the Bot

1. Paste the URL into your browser
2. Select your server from the dropdown
3. Click **Authorise**
4. Complete the CAPTCHA

The bot will now appear in your server's member list.

---

## Step 6 – First-Time Server Setup

Once the bot is online and in your server, a server **Administrator** should run these setup commands in Discord.

### 6.1  Set the Event Channel

```
/admin set_event_channel #raid-events
```

Replace `#raid-events` with your actual channel.  All future raid events will be posted here automatically.

### 6.2  Set a Log Channel (Optional)

```
/admin set_log_channel #bot-logs
```

### 6.3  Grant Raid Leader Permissions

```
/admin set_raid_leader @YourRaidLeader
```

Repeat for each raid leader or officer.  Officers have all raid leader permissions plus access to admin commands like reports and exports.

```
/admin set_raid_leader @OfficerName role:officer
```

### 6.4  Configure Default Roster Size (Optional)

```
/admin roster_config tanks:2 healers:5 dps:13
```

This sets the default for new events.  Individual events can override this.

### 6.5  Set Attendance Warning Threshold (Optional)

```
/admin attendance_threshold percentage:75
```

Members with overall attendance below this % will appear in `/attendance report`.

### 6.6  Have Members Register Characters

Each guild member should run:
```
/character add name:Grommash char_class:Warrior main_spec:Protection
```

---

## Command Reference

### Character Commands

All guild members can use these commands.

| Command | Description | Example |
|---------|-------------|---------|
| `/character add` | Register a WoW character | `/character add name:Sylvanas char_class:Hunter main_spec:Marksmanship` |
| `/character list` | View your registered characters | `/character list` |
| `/character main` | Set your main character | `/character main name:Sylvanas` |
| `/character update` | Update spec or item level | `/character update name:Sylvanas ilvl:489` |
| `/character remove` | Remove a character | `/character remove name:AltName` |
| `/character info` | View another member's characters | `/character info member:@Sylvanas` |

**Character name rules:** 2–12 letters, no spaces or numbers (matches real WoW names).

**Valid classes and specs:**

| Class | Tank Specs | Healer Specs | DPS Specs |
|-------|-----------|--------------|-----------|
| Death Knight | Blood | — | Frost, Unholy |
| Demon Hunter | Vengeance | — | Havoc |
| Druid | Guardian | Restoration | Balance, Feral |
| Evoker | — | Preservation | Devastation, Augmentation |
| Hunter | — | — | Beast Mastery, Marksmanship, Survival |
| Mage | — | — | Arcane, Fire, Frost |
| Monk | Brewmaster | Mistweaver | Windwalker |
| Paladin | Protection | Holy | Retribution |
| Priest | — | Discipline, Holy | Shadow |
| Rogue | — | — | Assassination, Outlaw, Subtlety |
| Shaman | — | Restoration | Elemental, Enhancement |
| Warlock | — | — | Affliction, Demonology, Destruction |
| Warrior | Protection | — | Arms, Fury |

---

### Raid / Event Commands

**Raid leaders and officers only** (except `/raid list` and `/raid info` which everyone can use).

| Command | Description | Example |
|---------|-------------|---------|
| `/raid create` | Create a new event | `/raid create name:"Heroic Vault" date:2024-03-12 time:20:00 event_type:"Heroic Raid"` |
| `/raid list` | Show upcoming events | `/raid list` |
| `/raid info` | View detailed event info | `/raid info event_id:5` |
| `/raid edit` | Edit an event's details | `/raid edit event_id:5 time:20:30` |
| `/raid cancel` | Cancel an event | `/raid cancel event_id:5 reason:"Roster too low"` |
| `/raid lock` | Toggle roster lock | `/raid lock event_id:5` |
| `/raid template save` | Save event as template | `/raid template save event_id:5 template_name:"Heroic Tuesday"` |
| `/raid template load` | Create event from template | `/raid template load template_name:"Heroic Tuesday" date:2024-03-19` |
| `/raid template list` | List saved templates | `/raid template list` |
| `/raid template delete` | Delete a template | `/raid template delete template_name:"Old Template"` |

**Valid event types:**
- `Normal Raid`, `Heroic Raid`, `Mythic Raid`
- `Mythic+ Night`
- `PvP - RBG`, `PvP - Arena`
- `Achievement Run`
- `Alt Raid`
- `Social Event`

**Date formats accepted:** `2024-03-12` or `03/12/2024`

**Time formats accepted:** `20:00` or `8:00 PM` or `8 PM`

---

### Signing Up for Events

After a raid is created, an embed appears in the event channel with five buttons:

| Button | Meaning |
|--------|---------|
| 🛡️ Tank | Sign up as a tank |
| 💚 Healer | Sign up as a healer |
| ⚔️ DPS | Sign up as DPS |
| ❓ Tentative | Not sure if you can make it |
| ❌ Decline | Mark yourself as not attending |

**Important notes:**
- You must have a main character registered (`/character add`) before signing up
- If a role is full, you're automatically moved to the Bench
- You can change your signup at any time by clicking a different button
- The roster embed updates live each time someone signs up or changes status

---

### Attendance Commands

| Command | Who Can Use | Description |
|---------|-------------|-------------|
| `/attendance mark` | Raid leaders | Mark attendance after an event |
| `/attendance view` | Everyone | View your (or another member's) stats |
| `/attendance report` | Raid leaders | See all members below threshold |
| `/attendance event` | Raid leaders | View attendance for a specific event |

#### How to Mark Attendance After a Raid

1. Run `/attendance mark event_id:5` (use the correct event ID)
2. A dropdown appears listing all signed-up members
3. Select each member and click **Present**, **Late**, **Excused**, or **Absent**
4. When done, click **✅ Finish & Save All**

Members not explicitly marked are defaulted to **Absent**.

#### Reading Your Attendance Stats

```
/attendance view
```

Shows:
- **Events Attended** — total events attended / total events you were expected at
- **Late Arrivals** — times you arrived after start time
- **Excused Absences** — absences you submitted in advance (don't count against you)
- **Unexcused Absences** — missed events without a submitted absence
- **30-Day Attendance** — attendance over the past 30 days
- **All-Time Attendance** — your overall percentage
- **Last 10 Events** — ✅ Present  ⏰ Late  ❌ Absent  🔵 Excused

---

### Absence Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/absence request` | Submit an excused absence | `/absence request event_id:5 reason:"Family vacation"` |
| `/absence list` | View your submitted absences | `/absence list` |
| `/absence event_list` | Officers: see all absences for an event | `/absence event_list event_id:5` |

**How excused absences work:**
1. Before the event, run `/absence request event_id:X reason:"Your reason"`
2. The bot automatically marks you as **Excused** in attendance
3. Excused absences do NOT count against your attendance percentage
4. You can still sign up and attend even after submitting an absence request

---

### Admin Commands

**Server Administrators only.**

| Command | Description |
|---------|-------------|
| `/admin set_raid_leader` | Grant raid leader or officer permissions |
| `/admin remove_raid_leader` | Remove someone's bot permissions |
| `/admin set_event_channel` | Set default event posting channel |
| `/admin set_log_channel` | Set bot log/audit channel |
| `/admin roster_config` | Set default tank/healer/DPS counts |
| `/admin attendance_threshold` | Set low-attendance warning % |
| `/admin status` | View current bot configuration |
| `/admin list_permissions` | See who has bot permissions |
| `/admin export_data` | Export all data as JSON |
| `/admin sync` | Sync slash commands to this server |

---

## Permissions System

The bot has three permission levels:

| Level | Who Has It | What They Can Do |
|-------|-----------|-----------------|
| **Member** | Everyone | Sign up for events, register characters, view their own stats, submit absences |
| **Raid Leader** | Set by admin via `/admin set_raid_leader` | Create/edit/cancel events, lock rosters, mark attendance, view reports, save templates |
| **Officer** | Set by admin via `/admin set_raid_leader role:officer` | All raid leader permissions + run attendance reports, view event absences, export CSV |
| **Administrator** | Discord server admins | All of the above + all `/admin` configuration commands |

**Note:** Discord server administrators always have full access to all commands, even without being assigned a bot role.

---

## Attendance Tracking Guide

### For Raid Leaders – Step-by-Step

**Before the Raid:**
1. Create the event: `/raid create name:"Heroic Vault" date:2024-03-12 time:20:00 event_type:"Heroic Raid"`
2. The bot posts the signup embed automatically in the event channel
3. Members sign up using the buttons

**During / After the Raid:**
1. Run `/attendance mark event_id:5`
2. Use the dropdown to mark each member
3. Click **Finish & Save All**

**Reviewing Attendance:**
- `/attendance report` — shows everyone below the threshold
- `/attendance view @member` — individual member stats
- `/attendance event event_id:5` — full breakdown for one event

### For Members – Step-by-Step

**Before a Raid You'll Miss:**
1. Run `/absence request event_id:5 reason:"Out of town"`
2. You're automatically marked excused — it won't hurt your attendance %

**Checking Your Attendance:**
1. Run `/attendance view`
2. If your percentage is in orange or red, you may receive a DM reminder from officers

### Attendance Calculation

```
Attendance % = (Present + Late) / (Total Events - Excused Absences) × 100
```

- **Present** — you showed up on time
- **Late** — you arrived after start but still attended
- **Excused** — you submitted an absence request ahead of time (NOT counted in denominator)
- **Absent** — you were expected but didn't show (NO prior request)

---

## Event & Signup System Guide

### Creating a Good Event Description

```
/raid create name:"Heroic Vault of the Incarnates" date:2024-03-12 time:20:00
  event_type:"Heroic Raid"
  description:"World bosses first, then full heroic clear. Bring flasks and food!"
  max_tanks:2 max_healers:5 max_dps:13
```

### Using Templates for Weekly Raids

**Save your regular raid as a template:**
```
/raid template save event_id:5 template_name:"Heroic Tuesday"
```

**Next week, load it with just a new date:**
```
/raid template load template_name:"Heroic Tuesday" date:2024-03-19
```

This saves you from re-entering all the settings every week!

### How the Roster Auto-Updates

- Every time someone clicks a signup button, the roster embed is immediately edited
- No manual refresh needed
- The "Last updated" timestamp at the bottom shows when it was last changed
- The embed shows FULL next to any role that has hit its cap

### Managing a Full Roster

When a role fills up:
- New signups for that role automatically go to **Bench**
- Bench members are listed in order of signup time (earlier = higher priority)
- When someone drops, you can manually adjust rosters
- Use `/raid lock event_id:5` to prevent new signups once your roster is set

---

## Running as a System Service (Linux)

To keep the bot running 24/7 even after closing your SSH session, use systemd:

### Create the Service File

```bash
sudo nano /etc/systemd/system/raidbot.service
```

Paste:
```ini
[Unit]
Description=Wrath of Midnight Raid Bot
After=network.target

[Service]
Type=simple
User=YOUR_LINUX_USERNAME
WorkingDirectory=/path/to/Wrathofmidnight_raidbot
ExecStart=/path/to/Wrathofmidnight_raidbot/venv/bin/python bot.py
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Replace `YOUR_LINUX_USERNAME` and `/path/to/Wrathofmidnight_raidbot` with your actual values.

### Enable and Start the Service

```bash
sudo systemctl daemon-reload
sudo systemctl enable raidbot        # Start on boot
sudo systemctl start raidbot         # Start now

sudo systemctl status raidbot        # Check it's running
sudo journalctl -u raidbot -f        # Watch live logs
```

### Running with screen (simpler alternative)

```bash
screen -S raidbot
source venv/bin/activate
python bot.py
# Detach with Ctrl+A then D
# Reattach with: screen -r raidbot
```

---

## Backup & Restore

### Backing Up the Database

All bot data is stored in `data/raidbot.db` (or whatever path you set in `.env`).

**Simple backup:**
```bash
cp data/raidbot.db data/raidbot_backup_$(date +%Y%m%d).db
```

**Automated daily backup (Linux cron):**
```bash
crontab -e
# Add this line:
0 4 * * * cp /path/to/data/raidbot.db /path/to/backups/raidbot_$(date +\%Y\%m\%d).db
```

### Restoring from Backup

1. Stop the bot
2. Copy your backup over the current database:
   ```bash
   cp data/raidbot_backup_20240312.db data/raidbot.db
   ```
3. Restart the bot

### Export Data via Bot Command

Admins can also export all data as JSON from within Discord:
```
/admin export_data
```

This sends a JSON file with all events, signups, characters, and attendance records.

---

## Troubleshooting

### Bot is online but slash commands don't appear

**Cause:** Commands haven't been synced yet.
**Fix:** Run `/admin sync` in your Discord server.  Wait a few seconds and try again.

If that doesn't work, restart the bot — it syncs commands to your guild automatically on startup.

---

### "Missing required environment variable" on startup

**Cause:** Your `.env` file is missing or incomplete.
**Fix:**
1. Make sure the file is named exactly `.env` (not `.env.txt`)
2. Make sure `DISCORD_TOKEN` and `GUILD_ID` are set
3. Check there are no spaces around the `=` sign

---

### "Invalid Token" error

**Cause:** Your bot token is wrong, expired, or has extra whitespace.
**Fix:**
1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click your application → **Bot** → **Reset Token**
3. Copy the new token and paste it into `.env`

---

### Signup buttons don't respond

**Cause:** The bot was restarted and lost the in-memory view registration.

This is a known limitation with discord.py persistent views.  After a bot restart, existing signup buttons on old messages may not respond.

**Fix:** Edit the event to trigger a re-post, or use `/raid create` for future events.  The new event's buttons will work correctly.

For production use, consider recreating events after planned bot restarts.

---

### Bot can't find the event channel

**Cause:** The event channel ID in `.env` or set via `/admin set_event_channel` is wrong.
**Fix:**
1. Re-run `/admin set_event_channel #your-channel`
2. Make sure the bot has **Send Messages** and **Embed Links** permissions in that channel

---

### Characters aren't showing in the signup roster

**Cause:** The user signing up hasn't registered a main character yet.
**Fix:** They need to run `/character add` first, then `/character main` to set their main.

---

### Database file grows very large

**Cause:** Many events and attendance records accumulating over time.
**Fix:** The bot auto-archives completed events.  The database should stay small for a 15-20 person guild.  SQLite databases are efficient; a year of data for a 20-person guild would likely be under 10 MB.

---

### "403 Forbidden" when posting to event channel

**Cause:** The bot doesn't have permission to post in that channel.
**Fix:** Go to your Discord channel settings → **Permissions** → add the bot role with **Send Messages**, **Embed Links**, and **Manage Messages** permissions.

---

## FAQ

**Q: Do members need a specific Discord role to use the bot?**

No.  All Discord members in the server can sign up for events and register characters.  Only administrative commands require special bot roles (raid leader / officer / admin).

---

**Q: Can one Discord user have multiple WoW characters?**

Yes!  Each user can register as many characters as they want.  One is designated their "main" (the one used for auto-signup when pressing the buttons).

---

**Q: What happens if I restart the bot during an active event?**

All data is persisted in the SQLite database — no data is lost.  Upcoming reminders will be re-read from the database on restart.  Existing signup button presses on old messages may need the event to be re-created to restore interactivity.

---

**Q: Can I run this bot on multiple servers?**

Technically yes, but the bot is designed and optimised for a single guild.  Set `GUILD_ID` to your main server.  Guild-specific slash commands will only appear in that server.

---

**Q: How do I change the timezone after initial setup?**

Edit the `TIMEZONE=` line in your `.env` file and restart the bot.  This affects how event times are displayed.

---

**Q: Can I customise the default raid size (e.g., for a 10-man team)?**

Yes!  Run `/admin roster_config tanks:2 healers:3 dps:5` to set 10-man as the default.  Individual events can still override this.

---

**Q: How do I give someone Officer vs Raid Leader access?**

```
/admin set_raid_leader @member role:raid_leader    ← Can create events, mark attendance
/admin set_raid_leader @member role:officer        ← All of the above + reports and exports
```

---

**Q: Where are the log files?**

In the `logs/` folder inside the bot directory.  Log files rotate daily and are kept for 7 days.

---

**Q: How do I completely wipe and reset the bot data?**

Stop the bot, delete `data/raidbot.db`, and restart.  The database will be recreated from scratch.

---

## Project Structure

```
Wrathofmidnight_raidbot/
├── bot.py                    Main entry point
├── config.py                 Environment variable loading
├── requirements.txt          Python dependencies
├── .env.example              Configuration template
├── .env                      Your configuration (never commit this!)
│
├── cogs/
│   ├── characters.py         /character commands
│   ├── events.py             /raid commands + signup buttons
│   ├── attendance.py         /attendance and /absence commands
│   └── admin.py              /admin commands
│
├── database/
│   ├── db_setup.py           Creates tables on first run
│   └── queries.py            All database query functions
│
├── utils/
│   ├── constants.py          WoW classes, specs, colors, emojis
│   ├── validators.py         Input validation helpers
│   └── embeds.py             Discord embed builders
│
├── data/
│   └── raidbot.db            SQLite database (auto-created)
│
└── logs/
    └── raidbot.log           Application logs (auto-created)
```

---

## Support & Contributing

- **Issues:** Open a GitHub issue with the error message and logs from the `logs/` folder
- **Logs:** Check `logs/raidbot.log` for detailed error information
- **Discord.py Docs:** [https://discordpy.readthedocs.io/](https://discordpy.readthedocs.io/)

---

*Built for the Wrath of Midnight guild.  Forged in Azeroth, deployed in Python.*
