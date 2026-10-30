import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

PORT = int(os.getenv("PORT", "8000"))
HOST = os.getenv("HOST", "127.0.0.1")
DEBUG = os.getenv("DEBUG", "True").lower() in ("true", "1", "yes")

# Supabase / Postgres connection (set this for production — enables Postgres mode)
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

# Database Path (used when DATABASE_URL is not set — local SQLite mode)
DB_PATH = BASE_DIR / os.getenv("DATABASE_PATH", "data/alumni_ai.db")
if not DATABASE_URL:
    try:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass  # read-only filesystem (e.g. serverless) — SQLite unavailable there

# Google OAuth Client Configuration
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "").strip()

# -------------------------------------------------------------
# ADMIN ACCESS CONTROL — single source of truth.
# Only these verified emails (plus the controlled @team.alum domain)
# ever receive admin/analytics access. NEVER trust client-supplied
# is_team_alum flags — only this allowlist (verified via Google OAuth
# or an existing password on the exact account).
# Restrict to exactly one address with:  ADMIN_EMAILS=teamalumorg@gmail.com
# -------------------------------------------------------------
ADMIN_EMAILS = {
    e.strip().lower()
    for e in os.getenv(
        "ADMIN_EMAILS",
        "teamalumorg@gmail.com,sudarshan.dev@gmail.com,sudarshan.deve@gmail.com"
    ).split(",")
    if e.strip()
}

def is_admin_email(email: Optional[str] = None) -> bool:
    e = (email or "").strip().lower()
    return bool(e) and (e in ADMIN_EMAILS or e.endswith("@team.alum"))


# -------------------------------------------------------------
# AI Provider Configuration
# Credentials and model identifiers are supplied through the
# environment only. Defaults below keep the service operational
# when a value is omitted.
# -------------------------------------------------------------
OPENCODE_API_KEY = os.getenv("OPENCODE_API_KEY", "").strip()
OPENCODE_ENDPOINT = os.getenv("OPENCODE_ENDPOINT", "https://opencode.ai/zen/v1/chat/completions").strip()
OPENCODE_MODEL = os.getenv("OPENCODE_MODEL", "space-bunny-free").strip()

OPENCODE_ATTACHMENT_KEY = os.getenv("OPENCODE_ATTACHMENT_KEY", "").strip()
OPENCODE_FALLBACK_KEY = os.getenv("OPENCODE_FALLBACK_KEY", "").strip()
OPENCODE_KEY_3 = os.getenv("OPENCODE_KEY_3", "").strip()

BIG_PICKLE_API_KEY = OPENCODE_API_KEY
BIG_PICKLE_ENDPOINT = OPENCODE_ENDPOINT
BIG_PICKLE_MODEL = os.getenv("BIG_PICKLE_MODEL", "big-pickle").strip()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "nvidia/nemotron-3-ultra-550b-a55b:free")

QWEN_API_KEY = os.getenv("QWEN_API_KEY", "").strip()
QWEN_ENDPOINT = os.getenv("QWEN_ENDPOINT", "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions").strip()
QWEN_MODEL = os.getenv("QWEN_MODEL", "qwen-turbo")

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").strip()
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:latest")
ENABLE_OLLAMA = os.getenv("ENABLE_OLLAMA", "True").lower() in ("true", "1", "yes")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")

CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY", "").strip()
CEREBRAS_MODEL = os.getenv("CEREBRAS_MODEL", "llama3.1-8b")

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "").strip()
MISTRAL_MODEL = os.getenv("MISTRAL_MODEL", "mistral-small-latest")

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
GITHUB_MODEL = os.getenv("GITHUB_MODEL", "gpt-4o-mini")

ENABLE_OFFLINE_FALLBACK = os.getenv("ENABLE_OFFLINE_FALLBACK", "True").lower() in ("true", "1", "yes")

# -------------------------------------------------------------
# Neural Voice Engine (May)
# -------------------------------------------------------------
SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "").strip()
SARVAM_TTS_ENDPOINT = os.getenv("SARVAM_TTS_ENDPOINT", "https://api.sarvam.ai/text-to-speech").strip()
SARVAM_SPEAKER = os.getenv("SARVAM_SPEAKER", "ishita").strip()
SARVAM_MODEL = os.getenv("SARVAM_MODEL", "bulbul:v3").strip()
SARVAM_LANG = os.getenv("SARVAM_LANG", "en-IN").strip()



