# Alumni AI

**Alumni AI** is a full-stack AI workspace built by **Team Alum** — multi-mode intelligence, an interactive voice companion **May**, a 3D mascot **Pengu**, persistent chat sessions, and a 10-tier automatic AI fallback engine that keeps working even when individual providers fail.

- **Startup & Founder**: Sudarshan Hadmode — *Startup & Founder of Team Alum, Alumni AI Developer*

---

## Features

| | |
|---|---|
| **Three intelligence modes** | 🎓 Professional (scholarly rigor) · 📖 Basic (simple, friendly) · 😏 Sarcastic (senior-dev banter, accurate answers) |
| **10-tier auto-fallback AI engine** | Tries providers in order on every request — OpenCode Zen → OpenRouter → Qwen → Ollama → Google Gemini → Groq → Cerebras → Mistral → GitHub Models → built-in offline brain. Rate-limited or down? It moves on automatically. |
| **Voice assistant "May"** | Hindi, Hinglish & Indian English detection with Sarvam AI neural TTS — concise answers by default, silent on small talk, voice-controlled UI actions |
| **Sessions & chat history** | Email-bound accounts with strict per-user isolation — nobody can read another user's sessions. Powered by Supabase Postgres. |
| **Sign-in options** | Google Sign-In (server-verified OAuth credentials), username/password, and 1-click guest access |
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
│   ├── database.py          # Dual-mode DB layer: Supabase Postgres (prod) or SQLite (local fallback)
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
│       ├── ai_service.py    # 10-tier fallback orchestration
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

Edit `.env` — at minimum set `DATABASE_URL` (Supabase) or leave it empty to use local SQLite. All AI provider keys are optional: the fallback engine works its way down to the offline brain.

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
| `OPENCODE_API_KEY` | Tier 1 — OpenCode Zen | optional |
| `OPENROUTER_API_KEY` | Tier 2 — OpenRouter free models | optional |
| `GEMINI_API_KEY` | Tier 5 — Google Gemini | optional |
| `GROQ_API_KEY` / `CEREBRAS_API_KEY` / `MISTRAL_API_KEY` / `GITHUB_TOKEN` | Tiers 6–9 | optional |
| `SARVAM_API_KEY` | May's neural voice (Sarvam Bulbul TTS) | Voice |
| `ENABLE_OFFLINE_FALLBACK` | Tier 10 built-in brain (default `True`) | — |

> **Security:** secrets live only in `.env` — it is gitignored. Never hardcode keys in source.

---

## Deploy (Vercel)

1. Push this repo to GitHub and import it at [vercel.com/new](https://vercel.com/new)
2. Vercel auto-detects FastAPI via `pyproject.toml` — zero config needed
3. Add the environment variables above in **Project Settings → Environment Variables** (at least `DATABASE_URL` and your provider keys)
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
