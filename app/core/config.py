from pydantic import BaseModel
from dotenv import load_dotenv
import os

load_dotenv()


class Settings(BaseModel):
    app_name: str = os.getenv("APP_NAME", "Persian Mental Wellness Chatbot API")
    app_version: str = os.getenv("APP_VERSION", "0.1.0")

    # SECURITY: default must be False so a forgotten env var never opens /debug/*
    debug: bool = (os.getenv("DEBUG", "false") or "false").strip().lower() in (
        "1", "true", "yes", "on",
    )

    database_url: str | None = os.getenv("DATABASE_URL")

    llm_provider: str = os.getenv("LLM_PROVIDER", "openrouter")
    llm_api_key: str | None = os.getenv("LLM_API_KEY")
    llm_base_url: str = os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1")
    llm_model: str = os.getenv("LLM_MODEL", "google/gemma-4-31b-it:free")
    llm_fallback_model: str = os.getenv("LLM_FALLBACK_MODEL", "nvidia/nemotron-3-super-120b-a12b:free")
    llm_final_fallback_model: str = os.getenv("LLM_FINAL_FALLBACK_MODEL", "openrouter/free")

    # NOTE: security.py still reads these via os.getenv; migrate later if you want.
    secret_key: str | None = os.getenv("SECRET_KEY")
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    access_token_expire_minutes: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))


settings = Settings()