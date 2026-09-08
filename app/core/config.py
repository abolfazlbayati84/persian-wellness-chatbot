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

    aval_api_key: str | None = os.getenv("AVAL_API_KEY")
    aval_base_url: str = os.getenv("AVAL_BASE_URL", "https://api.avalai.ir/v1")
    aval_model: str = os.getenv("AVAL_MODEL", "gpt-5.4-mini")
    aval_fallback_model: str = os.getenv("AVAL_FALLBACK_MODEL", "gpt-4.1-mini")

    # NOTE: security.py still reads these via os.getenv; migrate later if you want.
    secret_key: str | None = os.getenv("SECRET_KEY")
    jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
    access_token_expire_minutes: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))


settings = Settings()