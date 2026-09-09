import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from openai import OpenAI

from app.core.config import settings


def main():
    if not settings.llm_api_key:
        raise ValueError("LLM_API_KEY is missing from your .env file.")

    if not settings.llm_base_url:
        raise ValueError("LLM_BASE_URL is missing from your .env file.")

    if not settings.llm_model:
        raise ValueError("LLM_MODEL is missing from your .env file.")

    client = OpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
    )

    print(f"Testing model: {settings.llm_model}\n")

    response = client.chat.completions.create(
        model=settings.llm_model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a supportive Persian-language wellness assistant. "
                    "Reply warmly in Persian. Keep your answer brief."
                ),
            },
            {
                "role": "user",
                "content": "امروز کمی مضطرب هستم. یک پیشنهاد ساده برای آرام شدن بده.",
            },
        ],
        temperature=0.7,
        max_tokens=200,
    )

    answer = response.choices[0].message.content

    print("Model response:\n")
    print(answer)


if __name__ == "__main__":
    main()