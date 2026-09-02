from pydantic import BaseModel
from dotenv import load_dotenv
import os

load_dotenv()


class Settings(BaseModel):
    app_name: str = os.getenv("APP_NAME", "Persian Mental Wellness Chatbot API")
    app_version: str = os.getenv("APP_VERSION", "0.1.0")
    debug: bool = os.getenv("DEBUG", "true").lower() == "true"

    aval_api_key: str | None = os.getenv("AVAL_API_KEY")
    aval_base_url: str = os.getenv("AVAL_BASE_URL", "")
    aval_model: str = os.getenv("AVAL_MODEL", "")


settings = Settings()