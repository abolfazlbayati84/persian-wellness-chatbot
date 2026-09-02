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


def _call_model(client: OpenAI, model: str, messages: list[dict[str, str]]) -> str:
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.7,
        max_tokens=400,
    )
    content = response.choices[0].message.content
    return (content or "").strip()


def generate_reply(messages: list[dict[str, str]], extra_system_context: str | None = None) -> str:
    if not settings.aval_model:
        raise ValueError("AVAL_MODEL is missing.")

    client = build_client()
    system_prompt = _compose_system_prompt(extra_system_context)
    full_messages = [{"role": "system", "content": system_prompt}] + messages

    try:
        return _call_model(client, settings.aval_model, full_messages)
    except Exception:
        if settings.aval_fallback_model:
            return _call_model(client, settings.aval_fallback_model, full_messages)
        raise

def _compose_system_prompt(extra_context: str | None = None) -> str:
    if extra_context and extra_context.strip():
        return f"{SYSTEM_PROMPT_FA}\n\n{extra_context.strip()}"
    return SYSTEM_PROMPT_FA