import time
import random
import httpx
from dotenv import load_dotenv
import os

load_dotenv()

SYSTEM_PROMPT = (
    "You are a supportive Persian wellness assistant. "
    "Respond in Persian. Be empathetic, practical, and concise. "
    "Do not provide dangerous instructions. "
    "Do not diagnose; suggest general wellbeing steps."
)


def _env():
    provider = (os.getenv("LLM_PROVIDER", "openrouter") or "openrouter").strip().lower()
    api_key = (os.getenv("LLM_API_KEY", "") or "").strip()
    base_url = (os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1") or "").strip().rstrip("/")
    model = (os.getenv("LLM_MODEL", "google/gemma-4-31b-it:free") or "").strip()
    fallback_model = (os.getenv("LLM_FALLBACK_MODEL", "nvidia/nemotron-3-super-120b-a12b:free") or "").strip()
    final_fallback_model = (os.getenv("LLM_FINAL_FALLBACK_MODEL", "openrouter/free") or "").strip()
    debug_mode = (os.getenv("DEBUG", "false") or "false").strip().lower() in ("1", "true", "yes", "on")
    timeout_s = float((os.getenv("LLM_TIMEOUT_SECONDS", "25") or "25").strip())
    max_429_retries = int((os.getenv("LLM_MAX_429_RETRIES", "2") or "2").strip())
    site_url = (os.getenv("LLM_SITE_URL", "") or "").strip()
    site_name = (os.getenv("LLM_SITE_NAME", "") or "").strip()
    return (
        provider, api_key, base_url, model, fallback_model, final_fallback_model,
        debug_mode, timeout_s, max_429_retries, site_url, site_name,
    )


def _backoff_seconds(attempt: int, retry_after_header: str | None) -> float:
    if retry_after_header:
        try:
            return max(0.5, float(retry_after_header))
        except ValueError:
            pass
    base = 2 ** attempt
    return base + random.uniform(0, 0.5)


def _chat_completion(
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict],
    timeout_s: float,
    max_429_retries: int,
    debug_mode: bool,
    site_url: str,
    site_name: str,
) -> str:
    url = f"{base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if site_url:
        headers["HTTP-Referer"] = site_url
    if site_name:
        headers["X-Title"] = site_name

    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.7,
    }
    timeout = httpx.Timeout(connect=10.0, read=timeout_s, write=10.0, pool=10.0)

    with httpx.Client(timeout=timeout) as client:
        attempt = 0
        while True:
            try:
                r = client.post(url, headers=headers, json=payload)
            except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ConnectError) as net_err:
                if attempt == 0:
                    if debug_mode:
                        print(f"[LLM DEBUG] network error on {model}, retrying once: {net_err!r}")
                    time.sleep(1.5)
                    attempt += 1
                    continue
                raise

            if r.status_code == 429:
                if attempt < max_429_retries:
                    wait = _backoff_seconds(attempt, r.headers.get("retry-after"))
                    if debug_mode:
                        print(f"[LLM DEBUG] 429 on {model}, attempt={attempt + 1}, sleeping {wait:.1f}s")
                    time.sleep(wait)
                    attempt += 1
                    continue
                r.raise_for_status()

            r.raise_for_status()
            data = r.json()

            choice = data["choices"][0]
            content = choice.get("message", {}).get("content")

            if not content or not content.strip():
                raise ValueError(f"empty completion from model={model}, raw={data}")

            return content.strip()


def _result(text: str, model_path: str, model_name: str | None) -> dict:
    return {"text": text, "model_path": model_path, "model_name": model_name}


def generate_reply(user_text: str) -> dict:
    return generate_reply_with_context(
        user_text=user_text,
        profile_context=None,
        history=[],
        memory_summary=None,
    )


def generate_reply_with_context(
    user_text: str,
    profile_context: str | None,
    history: list[dict],
    memory_summary: str | None = None,
) -> dict:
    (
        provider, api_key, base_url, model, fallback_model, final_fallback_model,
        debug_mode, timeout_s, max_429_retries, site_url, site_name,
    ) = _env()

    if provider == "mock":
        if debug_mode:
            print("[LLM DEBUG] provider=mock used")
        return _result(f"Received: {user_text}", "none", None)

    if not api_key:
        if debug_mode:
            print("[LLM DEBUG] missing API key")
        return _result("کلید API تنظیم نشده است.", "error", None)

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    if profile_context:
        messages.append({"role": "system", "content": f"User profile context:\n{profile_context}"})

    if memory_summary:
        messages.append({"role": "system", "content": memory_summary})

    messages.extend(history)
    messages.append({"role": "user", "content": user_text})

    if debug_mode:
        print(
            "[LLM DEBUG] "
            f"history_count={len(history)} "
            f"profile_context={'yes' if bool(profile_context) else 'no'} "
            f"memory_summary={'yes' if bool(memory_summary) else 'no'} "
            f"primary_model={model} fallback_model={fallback_model} "
            f"final_fallback_model={final_fallback_model} timeout_s={timeout_s}"
        )

    attempts = [
        ("primary", model),
        ("fallback", fallback_model),
        ("final_fallback", final_fallback_model),
    ]

    last_err = None
    for path_name, model_name in attempts:
        if not model_name:
            continue
        t0 = time.perf_counter()
        try:
            out = _chat_completion(
                base_url, api_key, model_name, messages, timeout_s,
                max_429_retries, debug_mode, site_url, site_name,
            )
            if debug_mode:
                print(f"[LLM DEBUG] {path_name}_success model={model_name} elapsed_s={time.perf_counter() - t0:.1f}")
            return _result(out, path_name, model_name)
        except Exception as e:
            last_err = e
            print(f"[LLM ERROR {path_name}] model={model_name} elapsed_s={time.perf_counter() - t0:.1f} err={e!r}")

    return _result(
        "متأسفم، در ارتباط با مدل مشکلی پیش آمد. لطفاً دوباره تلاش کن.",
        "error",
        None,
    )