from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.config import DEBUG
from app.database import init_db
from app.routes import auth, chat, sessions, voice, browser, analytics, research, files, youtube, memory

app = FastAPI(
    title="Alumni AI Backend",
    description="Advanced AI System with Multi-Mode Intelligence, Voice Assistant May, and Integrated Browser Powered by Chrome",
    version="2.0.0",
    docs_url="/docs" if DEBUG else None,
    redoc_url="/redoc" if DEBUG else None
)

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Keep HTML fresh, but let browsers reuse static artwork/fonts between visits.
_STATIC_CACHE_PREFIXES = (
    "/logo", "/icon-", "/apple-touch-icon", "/manifest", "/tailwind", "/vendor",
    "/robots.txt", "/sitemap.xml", "/llms",
)


@app.middleware("http")
async def add_cache_headers(request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-store")
    elif path in ("/", "/index.html"):
        response.headers["Cache-Control"] = "public, max-age=0, must-revalidate"
    elif path.startswith(_STATIC_CACHE_PREFIXES):
        response.headers["Cache-Control"] = "public, max-age=604800, stale-while-revalidate=86400"
    return response

# Initialize database tables on startup
@app.on_event("startup")
def on_startup():
    init_db()
    print("[Alumni AI] Database initialized successfully.")

# Include routers
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(sessions.router)
app.include_router(voice.router)
app.include_router(browser.router)
app.include_router(analytics.router)
app.include_router(research.router)
app.include_router(files.router)
app.include_router(youtube.router)
app.include_router(memory.router)


# SEO & LLM Manifest endpoints
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

@app.get("/robots.txt", include_in_schema=False)
async def get_robots_txt():
    robots_path = STATIC_DIR / "robots.txt"
    if robots_path.exists():
        return FileResponse(robots_path, media_type="text/plain; charset=utf-8")
    return FileResponse(STATIC_DIR / "index.html")

@app.get("/sitemap.xml", include_in_schema=False)
async def get_sitemap_xml():
    sitemap_path = STATIC_DIR / "sitemap.xml"
    if sitemap_path.exists():
        return FileResponse(sitemap_path, media_type="application/xml; charset=utf-8")
    return FileResponse(STATIC_DIR / "index.html")

@app.get("/llms.txt", include_in_schema=False)
async def get_llms_txt():
    llms_path = STATIC_DIR / "llms.txt"
    if llms_path.exists():
        return FileResponse(llms_path, media_type="text/plain; charset=utf-8")
    return FileResponse(STATIC_DIR / "index.html")

@app.get("/llms-full.txt", include_in_schema=False)
async def get_llms_full_txt():
    llms_full_path = STATIC_DIR / "llms-full.txt"
    if llms_full_path.exists():
        return FileResponse(llms_full_path, media_type="text/plain; charset=utf-8")
    return FileResponse(STATIC_DIR / "index.html")

# Mount static files
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    from app.config import HOST, PORT
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=DEBUG)
