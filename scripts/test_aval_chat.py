from openai import OpenAI

from app.core.config import settings


def main():
    if not settings.aval_api_key:
        raise ValueError("AVAL_API_KEY is missing from your .env file.")

    if not settings.aval_base_url:
        raise ValueError("AVAL_BASE_URL is missing from your .env file.")

    if not settings.aval_model:
        raise ValueError("AVAL_MODEL is missing from your .env file.")

    client = OpenAI(
        api_key=settings.aval_api_key,
        base_url=settings.aval_base_url,
    )

    print(f"Testing Aval AI model: {settings.aval_model}\n")

    response = client.chat.completions.create(
        model=settings.aval_model,
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