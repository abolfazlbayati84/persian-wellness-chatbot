from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.api.routes import router

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
)

# Dev-only: only needed if the frontend is opened from another origin
# (e.g. as a file). When served by this app itself it's same-origin.
# Tighten allow_origins before any real deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

# Frontend: served at /app/, with / redirecting there.
app.mount("/app", StaticFiles(directory=STATIC_DIR, html=True), name="frontend")


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/app/")


@app.on_event("startup")
def _warm_up_embedding_model() -> None:
    try:
        from app.services.embeddings import embed_query
        print("[STARTUP] warming up embedding model (one-time load)...")
        embed_query("warmup")
        print("[STARTUP] embedding model ready.")
    except Exception as e:
        print(f"[STARTUP WARNING] embedding warmup failed, will lazy-load on first request instead: {e!r}")