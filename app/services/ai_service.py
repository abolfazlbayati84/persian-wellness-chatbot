from openai import OpenAI

from app.core.config import settings


SYSTEM_PROMPT_FA = (
    "تو یک دستیار سلامت روان فارسی‌زبان هستی. "
    "لحن تو باید همدلانه، محترمانه، و کوتاه باشد. "
    "تشخیص پزشکی قطعی نده. "
    "اگر کاربر نشانه خطر فوری داشت (مثل آسیب به خود/دیگران)، "
    "او را فوری به منابع اورژانسی و افراد قابل اعتماد ارجاع بده."
)


def build_client() -> OpenAI:
    if not settings.aval_api_key:
        raise ValueError("AVAL_API_KEY is missing.")
    if not settings.aval_base_url:
        raise ValueError("AVAL_BASE_URL is missing.")
    return OpenAI(
        api_key=settings.aval_api_key,
        base_url=settings.aval_base_url,
    )


def generate_reply(messages: list[dict[str, str]]) -> str:
    """
    messages: [{"role":"user|assistant|system", "content":"..."}]
    """
    if not settings.aval_model:
        raise ValueError("AVAL_MODEL is missing.")

    client = build_client()

    full_messages = [{"role": "system", "content": SYSTEM_PROMPT_FA}] + messages

    response = client.chat.completions.create(
        model=settings.aval_model,
        messages=full_messages,
        temperature=0.7,
        max_tokens=400,
    )

    content = response.choices[0].message.content
    return (content or "").strip()