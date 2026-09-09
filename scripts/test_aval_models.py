import sys
from pathlib import Path

# Make sure the project root (one level up from scripts/) is importable,
# regardless of the working directory this script is launched from.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from openai import OpenAI

from app.core.config import settings


def main():
    if not settings.llm_api_key:
        raise ValueError("LLM_API_KEY is missing from your .env file.")

    if not settings.llm_base_url:
        raise ValueError("LLM_BASE_URL is missing from your .env file.")

    client = OpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
    )

    print("Connecting to OpenRouter...")
    print(f"Base URL: {settings.llm_base_url}")
    print("\nModels available to this API key:\n")

    models = client.models.list()

    for model in models.data:
        print(f"- {model.id}")


if __name__ == "__main__":
    main()