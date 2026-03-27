# Wrath of Midnight — Raid Portal Web App

A mobile-first web application for the Wrath of Midnight WoW guild. Connects to the same SQLite database used by the Discord bot — no separate data store required.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Front-end | React 18 + TypeScript + Vite + Tailwind CSS |
| Back-end  | FastAPI (Python 3.10+) + aiosqlite |
| Auth      | Discord OAuth2 → JWT (stored in localStorage) |
| Database  | Shared SQLite at `data/raidbot.db` (WAL mode) |
| Deployment| Nginx + Cloudflare Tunnel on Raspberry Pi |

---

## Quick Start (Development)

### 1. Back-end

```bash
cd web/backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env — fill in Discord OAuth2 credentials, ALLOWED_GUILD_ID, JWT_SECRET_KEY

uvicorn main:app --host 127.0.0.1 --port 8001 --reload
```

The API is now available at `http://localhost:8001`. Visit `/docs` for the interactive Swagger UI.

### 2. Front-end

```bash
cd web/frontend
npm install

cp .env.example .env
# Set VITE_DISCORD_CLIENT_ID and VITE_DISCORD_REDIRECT_URI (use http://localhost:5173/login for dev)

npm run dev
```

Open `http://localhost:5173`. The dev server proxies `/api` and `/auth` to the FastAPI server.

---

## Discord OAuth2 Setup

1. Go to [discord.com/developers/applications](https://discord.com/developers/applications) and open your bot application.
2. Under **OAuth2 → General**, add a **Redirect URI**:
   - Development: `http://localhost:5173/login`
   - Production: `https://raids.yourwowguild.com/login`
3. Copy the **Client ID** and **Client Secret** into `web/backend/.env` and `web/frontend/.env`.
4. Set `ALLOWED_GUILD_ID` in `web/backend/.env` to your Discord server ID.

---

## Environment Variables

### `web/backend/.env`

```ini
DISCORD_CLIENT_ID=your_client_id
DISCORD_CLIENT_SECRET=your_client_secret
DISCORD_REDIRECT_URI=https://raids.yourwowguild.com/login
ALLOWED_GUILD_ID=your_guild_id
JWT_SECRET_KEY=generate_with: python -c "import secrets; print(secrets.token_urlsafe(32))"
DATABASE_PATH=../../data/raidbot.db
API_HOST=127.0.0.1
API_PORT=8001
CORS_ORIGINS=https://raids.yourwowguild.com,http://localhost:5173
```

### `web/frontend/.env`

```ini
VITE_API_URL=https://raids.yourwowguild.com
VITE_DISCORD_CLIENT_ID=your_client_id
VITE_DISCORD_REDIRECT_URI=https://raids.yourwowguild.com/login
```

---

## Production Deployment (Raspberry Pi)

### 1. Build the front-end

```bash
cd web/frontend
npm run build
# Output: web/frontend/dist/
```

### 2. Start the back-end as a systemd service

```bash
sudo nano /etc/systemd/system/raidbot-web.service
```

```ini
[Unit]
Description=Wrath of Midnight Web API
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/Wrathofmidnight_raidbot/web/backend
ExecStart=/home/pi/Wrathofmidnight_raidbot/web/backend/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8001
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable raidbot-web
sudo systemctl start raidbot-web
```

### 3. Configure Nginx

```bash
sudo cp web/nginx.conf.example /etc/nginx/sites-available/raidbot
sudo ln -s /etc/nginx/sites-available/raidbot /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### 4. Set up Cloudflare Tunnel

```bash
cloudflared tunnel create raidbot
cloudflared tunnel route dns raidbot raids.yourwowguild.com
cloudflared tunnel run raidbot
```

---

## Features

| Feature | Who can use |
|---|---|
| View upcoming raid events + rosters | All members |
| Manage own characters (add/edit/delete/set main) | All members |
| View own attendance stats + history | All members |
| Submit absence requests | All members |
| Mark event attendance | Raid Leader+ |
| View guild roster | Officer+ |
| Low attendance report | Officer+ |
| Admin character list | Officer+ |
| Dashboard stats | Officer+ |

> **Note:** Raid signups happen in Discord only. The web app shows event rosters read-only with a "Sign Up in Discord" button.

---

## Project Structure

```
web/
├── backend/
│   ├── main.py              FastAPI app + CORS + router registration
│   ├── config.py            .env loading
│   ├── routers/             auth, characters, events, attendance, admin
│   ├── database/            connection.py (WAL SQLite), queries.py
│   ├── auth/                oauth.py (Discord), jwt_handler.py
│   ├── middleware/          auth.py (JWT dependency injection)
│   ├── models/              schemas.py (Pydantic request/response models)
│   ├── requirements.txt
│   └── .env.example
│
├── frontend/
│   ├── src/
│   │   ├── main.tsx         React entry — BrowserRouter + QueryClient + AuthProvider
│   │   ├── App.tsx          Route definitions + layout wrapper
│   │   ├── contexts/        AuthContext.tsx
│   │   ├── pages/           Dashboard, EventsList, CharactersPage, RosterView,
│   │   │                    AttendancePage, AdminPage, Login
│   │   ├── components/      Layout (Sidebar, MobileMenu, TopBar, ProtectedRoute)
│   │   │                    Events (EventCard, EventFilters)
│   │   │                    Characters (CharacterCard, CharacterForm)
│   │   │                    Attendance (AttendanceStats, AttendanceMarker)
│   │   ├── lib/             api.ts (Axios instance), utils.ts
│   │   ├── types/           index.ts (TypeScript interfaces + constants)
│   │   └── index.css        Tailwind + glass morphism + custom utilities
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   └── .env.example
│
├── nginx.conf.example
└── README.md
```
