# Alumni AI

**Alumni AI** is a full-stack AI workspace built by **Team Alum** — multi-mode intelligence, an interactive voice companion **May**, a 3D mascot **Pengu**, persistent chat sessions, and a resilient AI engine that keeps working when an individual provider is unavailable.

- **Startup & Founder**: Sudarshan Hadmode — *Startup & Founder of Team Alum, Alumni AI Developer*

---

## Features

| | |
|---|---|
| **Three intelligence modes** | 🎓 Professional (scholarly rigor) · 📖 Basic (simple, friendly) · 😏 Sarcastic (senior-dev banter, accurate answers) |
| **Resilient AI engine** | Automatic failover keeps responses flowing when a provider is rate-limited or down. The provider order and configuration are private. |
| **Voice assistant "May"** | Hindi, Hinglish & Indian English detection with neural TTS — concise answers by default, silent on small talk, voice-controlled UI actions |
| **Sessions & chat history** | Email-bound accounts with strict per-user isolation — nobody can read another user's sessions. Powered by Supabase Postgres. |
| **Sign-in options** | Google Sign-In (server-verified OAuth credentials), username/password, and guest access that politely asks for a display name first |
| **3D companion "Pengu"** | Interactive SVG mascot with eye/flipper physics, shy & happy states |
| **System Pulse analytics** | Founder-only (`is_team_alum`) latency/provider/mode dashboards — 403-locked for everyone else |
| **Extras** | YouTube educational embeds with channel deduplication, file attachments, text research pipeline, dark claymorphic UI, mobile-first layout |

---

## Architecture

```
alumni-ai/
├── app/
│   ├── main.py              # FastAPI app, routers, static mount
│   ├── config.py            # Env settings — ALL secrets come from .env (never committed)
│   ├── database.py          # Dual-mode DB layer: Supabase Postgres (prod) or SQLite (local)
│   ├── security.py          # Token auth dependency
│   ├── models.py            # Pydantic schemas
│   ├── routes/
│   │   ├── auth.py          # /api/auth — password, verified Google OAuth, guest
│   │   ├── chat.py          # /api/chat — sessions, messages, AI responses
│   │   ├── sessions.py      # /api/sessions
│   │   ├── voice.py         # /api/voice — May
│   │   ├── browser.py       # /api/tools
│   │   ├── research.py      # /api/research
│   │   ├── youtube.py       # /api/youtube
│   │   ├── files.py         # /api/files — attachments
│   │   └── analytics.py     # /api/analytics — founder-only
│   └── services/
│       ├── ai_service.py    # AI response orchestration
│       ├── voice_service.py # May: language detection, TTS, speech formatting
│       ├── browser_service.py
│       └── code_sandbox.py
├── static/
│   └── index.html           # Single-file UI (login, workspace, Pengu, May)
├── vercel.json              # Function config (python3.12, maxDuration)
├── pyproject.toml           # Vercel entrypoint: app.main:app
├── requirements.txt
├── .env.example             # Template — copy to .env and fill in
└── run.bat                  # Local Windows runner
```

**Database tables:** `users`, `auth_tokens`, `sessions`, `messages`, `analytics_events` — created automatically on first startup.

---

## Quick Start (Local)

Requires **Python 3.11+**.

```bash
git clone https://github.com/teamalumorg-develop/alumni-ai.git
cd alumni-ai
pip install -r requirements.txt
copy .env.example .env       # Windows (use cp on macOS/Linux)
```

Edit `.env` — at minimum set `DATABASE_URL` (Supabase) or leave it empty to use local SQLite. AI provider credentials are optional and configured privately; the engine degrades gracefully when a provider is not available.

```bash
run.bat
# or: python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Open **http://127.0.0.1:8000**

---

## Environment Variables

| Variable | Purpose | Required |
|---|---|---|
| `DATABASE_URL` | Supabase Postgres connection string (URI). Empty = local SQLite mode | Production |
| `GOOGLE_CLIENT_ID` | Google OAuth Web client ID for Sign-In button | Google login |
| `SARVAM_API_KEY` | May's neural voice | Voice |
| AI provider credentials | Configured privately via `.env` or the hosting provider's environment settings | Production |

> **Security:** secrets live only in `.env` — it is gitignored. Never hardcode keys in source.

---

## Deploy (Vercel)

1. Push this repo to GitHub and import it at [vercel.com/new](https://vercel.com/new)
2. Vercel auto-detects FastAPI via `pyproject.toml` — zero config needed
3. Add the environment variables above in **Project Settings → Environment Variables**
4. Deploy → your app is live at `https://<project>.vercel.app`
5. Add that URL to your Google OAuth client's **Authorized JavaScript origins**

The first cold start creates all database tables automatically in Supabase.

---

## Testing

```bash
python verify_app.py
```

Runs the full multi-user suite — authentication, privacy isolation, chat, voice, analytics, and Google spoof-rejection — against whichever database `DATABASE_URL` points to.

---

## Credits

Built by **Team Alum**.

*Startup & Founder of Team Alum, Sudarshan & Soham • All Rights Reserved*
