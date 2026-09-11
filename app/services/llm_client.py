import re
import time
import random
import httpx
from dotenv import load_dotenv
import os

load_dotenv()

SYSTEM_PROMPT = (
    "You are a supportive Persian (Farsi) wellness assistant.\n"
    "STRICT LANGUAGE RULE: write your ENTIRE reply in fluent, natural Persian only. "
    "Never switch to English, Korean, Chinese, or any other language, not even for "
    "single words, unless the user's own message was written in that language. "
    "Never mix languages within the same sentence.\n"
    "Be empathetic, practical, and concise. "
    "Do not provide dangerous instructions. "
    "Do not diagnose; suggest general wellbeing steps."
)

_FORBIDDEN_SCRIPT_RE = re.compile(
    r"[\uAC00-\uD7A3\u3040-\u30FF\u4E00-\u9FFF\u0400-\u04FF]"
)


def _has_forbidden_script(text: str) -> bool:
    return bool(_FORBIDDEN_SCRIPT_RE.search(text))


def _env():
    provider = (os.getenv("LLM_PROVIDER", "openrouter") or "openrouter").strip().lower()
    api_key = (os.getenv("LLM_API_KEY", "") or "").strip()
    base_url = (os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1") or "").strip().rstrip("/")
    model = (os.getenv("LLM_MODEL", "google/gemma-4-31b-it:free") or "").strip()
    fallback_model = (os.getenv("LLM_FALLBACK_MODEL", "nvidia/nemotron-3-super-120b-a12b:free") or "").strip()
    final_fallback_model = (os.getenv("LLM_FINAL_FALLBACK_MODEL", "openrouter/free") or "").strip()
    debug_mode = (os.getenv("DEBUG", "false") or "false").strip().lower() in ("1", "true", "yes", "on")
    timeout_s = float((os.getenv("LLM_TIMEOUT_SECONDS", "20") or "20").strip())
    total_budget_s = float((os.getenv("LLM_TOTAL_BUDGET_SECONDS", "45") or "45").strip())
    max_429_retries = int((os.getenv("LLM_MAX_429_RETRIES", "1") or "1").strip())
    site_url = (os.getenv("LLM_SITE_URL", "") or "").strip()
    site_name = (os.getenv("LLM_SITE_NAME", "") or "").strip()
    return (
        provider, api_key, base_url, model, fallback_model, final_fallback_model,
        debug_mode, timeout_s, total_budget_s, max_429_retries, site_url, site_name,
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
    max_429_retries: int,
    debug_mode: bool,
    site_url: str,
    site_name: str,
    deadline: float,
) -> str:
    """deadline is an absolute time.monotonic() value: this call (including
    all internal retries/backoffs) will never run past it."""
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

    attempt = 0
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 1.0:
            raise TimeoutError(f"global LLM budget exhausted before/while calling {model}")

        # never let a single HTTP call's read-timeout outlive the remaining budget
        timeout = httpx.Timeout(
            connect=min(10.0, remaining),
            read=remaining,
            write=min(10.0, remaining),
            pool=min(10.0, remaining),
        )

        try:
            with httpx.Client(timeout=timeout) as client:
                r = client.post(url, headers=headers, json=payload)
        except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ConnectError) as net_err:
            remaining = deadline - time.monotonic()
            if attempt == 0 and remaining > 3.0:
                if debug_mode:
                    print(f"[LLM DEBUG] network error on {model}, retrying once: {net_err!r}")
                time.sleep(min(1.5, remaining - 1))
                attempt += 1
                continue
            raise

        if r.status_code == 429:
            remaining = deadline - time.monotonic()
            if attempt < max_429_retries and remaining > 3.0:
                wait = min(_backoff_seconds(attempt, r.headers.get("retry-after")), remaining - 1)
                if debug_mode:
                    print(f"[LLM DEBUG] 429 on {model}, attempt={attempt + 1}, sleeping {wait:.1f}s")
                time.sleep(max(0.0, wait))
                attempt += 1
                continue
            r.raise_for_status()

        r.raise_for_status()
        data = r.json()

        choice = data["choices"][0]
        content = choice.get("message", {}).get("content")

        if not content or not content.strip():
            raise ValueError(f"empty completion from model={model}, raw={data}")

        content = content.strip()

        if _has_forbidden_script(content):
            raise ValueError(f"forbidden non-Persian script detected in output from model={model}")

        return content


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
    kb_context: str | None = None,
) -> dict:
    (
        provider, api_key, base_url, model, fallback_model, final_fallback_model,
        debug_mode, timeout_s, total_budget_s, max_429_retries, site_url, site_name,
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

    if kb_context:
        messages.append(
            {
                "role": "system",
                "content": (
                        "Relevant reference material (validated psychoeducational content). "
                        "Draw on this when it fits the user's message; put it in your own "
                        "natural, empathetic Persian words, don't copy it verbatim, and don't "
                        "mention that you're using 'reference material':\n" + kb_context
                ),
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
            f"primary_model={model} fallback_model={fallback_model} "
            f"final_fallback_model={final_fallback_model} "
            f"total_budget_s={total_budget_s}"
        )

    deadline = time.monotonic() + total_budget_s

    attempts = [
        ("primary", model),
        ("fallback", fallback_model),
        ("final_fallback", final_fallback_model),
    ]

    for path_name, model_name in attempts:
        if not model_name:
            continue

        if time.monotonic() >= deadline - 1.0:
            print(f"[LLM DEBUG] skipping {path_name} ({model_name}): global budget exhausted")
            break

        t0 = time.perf_counter()
        try:
            out = _chat_completion(
                base_url, api_key, model_name, messages,
                max_429_retries, debug_mode, site_url, site_name,
                deadline=deadline,
            )
            if debug_mode:
                print(f"[LLM DEBUG] {path_name}_success model={model_name} elapsed_s={time.perf_counter() - t0:.1f}")
            return _result(out, path_name, model_name)
        except Exception as e:
            print(f"[LLM ERROR {path_name}] model={model_name} elapsed_s={time.perf_counter() - t0:.1f} err={e!r}")

    return _result(
        "متأسفم، در ارتباط با مدل مشکلی پیش آمد. لطفاً دوباره تلاش کن.",
        "error",
        None,
    )