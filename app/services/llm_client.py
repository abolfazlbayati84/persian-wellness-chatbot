import os
import httpx
from dotenv import load_dotenv

load_dotenv()

SYSTEM_PROMPT = (
    "You are a supportive Persian wellness assistant. "
    "Respond in Persian. Be empathetic, practical, and concise. "
    "Do not provide dangerous instructions. "
    "Do not diagnose; suggest general wellbeing steps."
)


def _env():
    provider = (os.getenv("LLM_PROVIDER", "aval") or "aval").strip().lower()
    api_key = (os.getenv("AVAL_API_KEY", "") or "").strip()
    base_url = (os.getenv("AVAL_BASE_URL", "https://api.avalai.ir/v1") or "").strip().rstrip("/")
    model = (os.getenv("AVAL_MODEL", "gpt-5.4-mini") or "gpt-5.4-mini").strip()
    fallback_model = (os.getenv("AVAL_FALLBACK_MODEL", "gpt-4.1-mini") or "gpt-4.1-mini").strip()
    debug_mode = (os.getenv("DEBUG", "false") or "false").strip().lower() in ("1", "true", "yes", "on")
    return provider, api_key, base_url, model, fallback_model, debug_mode


def _chat_completion(base_url: str, api_key: str, model: str, messages: list[dict]) -> str:
    url = f"{base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.7,
    }

    with httpx.Client(timeout=45) as client:
        r = client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    return data["choices"][0]["message"]["content"].strip()


def generate_reply(user_text: str) -> str:
    return generate_reply_with_context(
        user_text=user_text,
        profile_context=None,
        history=[],
        memory_summary=None,
    )


def generate_reply_with_context(
    user_text: str,
    profile_context: str | None,
    history: list[dict],  # [{"role":"user|assistant","content":"..."}]
    memory_summary: str | None = None,
) -> str:
    provider, api_key, base_url, model, fallback_model, debug_mode = _env()

    if provider == "mock":
        if debug_mode:
            print("[LLM DEBUG] provider=mock used")
        return f"Received: {user_text}"

    if not api_key:
        if debug_mode:
            print("[LLM DEBUG] missing API key")
        return "کلید API تنظیم نشده است."

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    if profile_context:
        messages.append(
            {
                "role": "system",
                "content": f"User profile context:\n{profile_context}",
            }
        )

    if memory_summary:
        messages.append(
            {
                "role": "system",
                "content": memory_summary,
            }
        )

    messages.extend(history)
    messages.append({"role": "user", "content": user_text})

    if debug_mode:
        print(
            "[LLM DEBUG] "
            f"history_count={len(history)} "
            f"profile_context={'yes' if bool(profile_context) else 'no'} "
            f"memory_summary={'yes' if bool(memory_summary) else 'no'} "
            f"primary_model={model} fallback_model={fallback_model}"
        )

    try:
        out = _chat_completion(base_url, api_key, model, messages)
        if debug_mode:
            print(f"[LLM DEBUG] primary_success model={model}")
        return out
    except Exception as e1:
        print("[LLM ERROR primary]", repr(e1))
        try:
            out = _chat_completion(base_url, api_key, fallback_model, messages)
            if debug_mode:
                print(f"[LLM DEBUG] fallback_success model={fallback_model}")
            return out
        except Exception as e2:
            print("[LLM ERROR fallback]", repr(e2))
            return "متأسفم، در ارتباط با مدل مشکلی پیش آمد. لطفاً دوباره تلاش کن."