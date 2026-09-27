from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.routes import router

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
)

# Dev-only: allows the frontend (served from a different origin, e.g. the
# published artifact page) to call this API. Tighten allow_origins before
# any real deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.on_event("startup")
def _warm_up_embedding_model() -> None:
    try:
        from app.services.embeddings import embed_query
        print("[STARTUP] warming up embedding model (one-time load)...")
        embed_query("warmup")
        print("[STARTUP] embedding model ready.")
    except Exception as e:
        print(f"[STARTUP WARNING] embedding warmup failed, will lazy-load on first request instead: {e!r}")