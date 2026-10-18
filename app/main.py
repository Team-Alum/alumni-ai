from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.config import DEBUG
from app.database import init_db
from app.routes import auth, chat, sessions, voice, browser, analytics, research, files, youtube

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


# Mount static files
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
if STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    from app.config import HOST, PORT
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=DEBUG)
