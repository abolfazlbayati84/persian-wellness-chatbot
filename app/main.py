from fastapi import FastAPI

from app.core.config import settings
from app.api.routes import router

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
)

app.include_router(router)


@app.on_event("startup")
def _warm_up_embedding_model() -> None:
    """Load the embedding model into memory at server startup instead of on
    the first real chat request -- avoids surprising the first user with a
    ~1 minute wait while the ~1.1GB model loads from disk."""
    try:
        from app.services.embeddings import embed_query
        print("[STARTUP] warming up embedding model (one-time load)...")
        embed_query("warmup")
        print("[STARTUP] embedding model ready.")
    except Exception as e:
        print(f"[STARTUP WARNING] embedding warmup failed, will lazy-load on first request instead: {e!r}")