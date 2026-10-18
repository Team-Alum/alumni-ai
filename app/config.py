import os
from pathlib import Path
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
# Multi-Provider Auto Fallback Engine (Prioritizing Free Platforms)
# -------------------------------------------------------------
# Tier 1: OpenCode Zen (Free High-Performance Reasoning & Coding Brain - Key No. 1)
OPENCODE_API_KEY = os.getenv("OPENCODE_API_KEY", "").strip()
OPENCODE_ENDPOINT = os.getenv("OPENCODE_ENDPOINT", "https://opencode.ai/zen/v1/chat/completions").strip()
OPENCODE_MODEL = os.getenv("OPENCODE_MODEL", "space-bunny-free").strip()

# Key No. 3: OpenCode Zen Dedicated Attachment Observer, Code Analyzer & Fallback Brain
OPENCODE_ATTACHMENT_KEY = os.getenv("OPENCODE_ATTACHMENT_KEY", "").strip()
OPENCODE_FALLBACK_KEY = os.getenv("OPENCODE_FALLBACK_KEY", "").strip()

# Key No. 4: OpenCode Zen extra rotation key (Team Alum backup brain)
OPENCODE_KEY_3 = os.getenv("OPENCODE_KEY_3", "").strip()

# Big Pickle: cooldown fallback model — retried with every key when its primary
# model is cooling down / rate-limited, before moving to the next key
BIG_PICKLE_API_KEY = OPENCODE_API_KEY
BIG_PICKLE_ENDPOINT = OPENCODE_ENDPOINT
BIG_PICKLE_MODEL = os.getenv("BIG_PICKLE_MODEL", "big-pickle").strip()

# Tier 2: OpenRouter Free Models (qwen/qwen-2.5-72b-instruct:free, etc.)
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "nvidia/nemotron-3-ultra-550b-a55b:free")

# Tier 3: Qwen (Alibaba DashScope / OpenCode / HuggingFace)
QWEN_API_KEY = os.getenv("QWEN_API_KEY", "").strip()
QWEN_ENDPOINT = os.getenv("QWEN_ENDPOINT", "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions").strip()
QWEN_MODEL = os.getenv("QWEN_MODEL", "qwen-turbo")

# Tier 4: Ollama (100% Free Local or Nest-hosted Server: Qwen 2.5 / Llama)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").strip()
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:latest")
ENABLE_OLLAMA = os.getenv("ENABLE_OLLAMA", "True").lower() in ("true", "1", "yes")

# Tier 5: Google Gemini (Free Tier via Google AI Studio)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")

# Tier 6: Groq Cloud (Ultra-Fast Free Tier: Llama 3.3 70B / Llama 3.1 8B)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# Tier 7: Cerebras Cloud (Ultra-Fast Free Tier: Llama 3.1 8B)
CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY", "").strip()
CEREBRAS_MODEL = os.getenv("CEREBRAS_MODEL", "llama3.1-8b")

# Tier 8: Mistral AI (Free Tier: mistral-small / open-mistral-nemo)
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "").strip()
MISTRAL_MODEL = os.getenv("MISTRAL_MODEL", "mistral-small-latest")

# Tier 9: GitHub Models / Azure AI (Free Tier via Personal Access Token)
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "").strip()
GITHUB_MODEL = os.getenv("GITHUB_MODEL", "gpt-4o-mini")

# Tier 10: Alumni AI Built-in Neural Brain (Offline Heuristic Engine - 100% Uptime Always)
ENABLE_OFFLINE_FALLBACK = os.getenv("ENABLE_OFFLINE_FALLBACK", "True").lower() in ("true", "1", "yes")

# -------------------------------------------------------------
# Sarvam AI Studio Neural Voice Engine (Bulbul Model)
# -------------------------------------------------------------
SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "").strip()
SARVAM_TTS_ENDPOINT = os.getenv("SARVAM_TTS_ENDPOINT", "https://api.sarvam.ai/text-to-speech").strip()
SARVAM_SPEAKER = os.getenv("SARVAM_SPEAKER", "ishita").strip()
SARVAM_MODEL = os.getenv("SARVAM_MODEL", "bulbul:v3").strip()
SARVAM_LANG = os.getenv("SARVAM_LANG", "en-IN").strip()



