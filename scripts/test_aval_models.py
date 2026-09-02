from openai import OpenAI

from app.core.config import settings


def main():
    if not settings.aval_api_key:
        raise ValueError("AVAL_API_KEY is missing from your .env file.")

    if not settings.aval_base_url:
        raise ValueError("AVAL_BASE_URL is missing from your .env file.")

    client = OpenAI(
        api_key=settings.aval_api_key,
        base_url=settings.aval_base_url,
    )

    print("Connecting to Aval AI...")
    print(f"Base URL: {settings.aval_base_url}")
    print("\nModels available to this API key:\n")

    models = client.models.list()

    for model in models.data:
        print(f"- {model.id}")


if __name__ == "__main__":
    main()