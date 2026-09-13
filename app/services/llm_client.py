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

SUMMARY_SYSTEM_PROMPT = (
    "You are a clinical documentation assistant. Given a transcript of a "
    "conversation between a user and a supportive Persian wellness chatbot, "
    "write a concise summary IN PERSIAN (under 150 words) covering exactly "
    "these four points, each as a short line:\n"
    "۱) دغدغه‌های اصلی که کاربر مطرح کرد\n"
    "۲) تکنیک‌ها یا پیشنهادهایی که به کاربر ارائه شد\n"
    "۳) اگر قدم عملی/تکلیف مشخصی توافق شد، چه بود\n"
    "۴) روند احساسی کاربر در طول گفتگو (بهتر شد، بدتر شد، بدون تغییر)\n"
    "Do not add commentary, disclaimers, or anything outside these four "
    "points. Do not include the assistant's exact wording, only facts."
)

_FORBIDDEN_SCRIPT_RE = re.compile(
    r"[\uAC00-\uD7A3\u3040-\u30FF\u4E00-\u9FFF\u0400-\u04FF]"
)

# Some models (notably Gemma 4's "thinking" mode, see
# github.com/google-gemini/cookbook/issues/1198) leak their internal
# reasoning/self-critique into the visible answer even when thinking is
# requested off. Treat any of these tell-tale English markers as a bad
# generation -- fail it like any other error so the cascade moves on to
# the next model instead of showing this to a real user.
_LEAKED_REASONING_MARKERS = re.compile(
    r"(self-correction|confidence score|constraint checklist|double checking rules?|"
    r"final response construction|final polish|wait,? i need to|revised plan:|"
    r"let me reconsider|draft response|language check:|tone check:|safety check:|"
    r"content check:|refined text construction)",
    re.IGNORECASE,
)


def _has_forbidden_script(text: str) -> bool:
    return bool(_FORBIDDEN_SCRIPT_RE.search(text))


def _has_leaked_reasoning(text: str) -> bool:
    return bool(_LEAKED_REASONING_MARKERS.search(text))


def _env():
    provider = (os.getenv("LLM_PROVIDER", "openrouter") or "openrouter").strip().lower()

    # OpenRouter / OpenAI-compatible config
    api_key = (os.getenv("LLM_API_KEY", "") or "").strip()
    base_url = (os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1") or "").strip().rstrip("/")
    model = (os.getenv("LLM_MODEL", "google/gemma-4-31b-it:free") or "").strip()
    fallback_model = (os.getenv("LLM_FALLBACK_MODEL", "nvidia/nemotron-3-super-120b-a12b:free") or "").strip()
    final_fallback_model = (os.getenv("LLM_FINAL_FALLBACK_MODEL", "openrouter/free") or "").strip()
    site_url = (os.getenv("LLM_SITE_URL", "") or "").strip()
    site_name = (os.getenv("LLM_SITE_NAME", "") or "").strip()

    # Google Generative Language API config (direct Gemma/Gemini access)
    google_api_key = (os.getenv("GOOGLE_API_KEY", "") or "").strip()
    google_model = (os.getenv("GOOGLE_MODEL", "gemma-4-26b-a4b-it") or "").strip()
    google_fallback_model = (os.getenv("GOOGLE_FALLBACK_MODEL", "gemma-3-27b-it") or "").strip()

    debug_mode = (os.getenv("DEBUG", "false") or "false").strip().lower() in ("1", "true", "yes", "on")
    total_budget_s = float((os.getenv("LLM_TOTAL_BUDGET_SECONDS", "45") or "45").strip())
    max_429_retries = int((os.getenv("LLM_MAX_429_RETRIES", "1") or "1").strip())

    return (
        provider, api_key, base_url, model, fallback_model, final_fallback_model,
        debug_mode, total_budget_s, max_429_retries, site_url, site_name,
        google_api_key, google_model, google_fallback_model,
    )


def _backoff_seconds(attempt: int, retry_after_header: str | None) -> float:
    if retry_after_header:
        try:
            return max(0.5, float(retry_after_header))
        except ValueError:
            pass
    base = 2 ** attempt
    return base + random.uniform(0, 0.5)


# ---------------------------------------------------------------------------
# OpenRouter / OpenAI-compatible path (unchanged from before)
# ---------------------------------------------------------------------------

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
    url = f"{base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if site_url:
        headers["HTTP-Referer"] = site_url
    if site_name:
        headers["X-Title"] = site_name

    payload = {"model": model, "messages": messages, "temperature": 0.7}

    attempt = 0
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 1.0:
            raise TimeoutError(f"global LLM budget exhausted before/while calling {model}")

        timeout = httpx.Timeout(
            connect=min(10.0, remaining), read=remaining,
            write=min(10.0, remaining), pool=min(10.0, remaining),
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

        content = content.strip()
        if _has_forbidden_script(content):
            raise ValueError(f"forbidden non-Persian script detected in output from model={model}")
        if _has_leaked_reasoning(content):
            raise ValueError(f"leaked chain-of-thought reasoning detected in output from model={model}")
        return content

# ---------------------------------------------------------------------------
# Google Generative Language API path
# ---------------------------------------------------------------------------

def _messages_to_google_format(messages: list[dict]) -> tuple[str | None, list[dict]]:
    """Google's API separates system instructions from the turn-by-turn
    'contents', and uses role 'model' where OpenAI-style APIs use
    'assistant'. This converts our internal OpenAI-style message list."""
    system_parts = []
    contents = []
    for m in messages:
        role = m.get("role")
        content = m.get("content", "")
        if role == "system":
            system_parts.append(content)
        elif role == "user":
            contents.append({"role": "user", "parts": [{"text": content}]})
        elif role == "assistant":
            contents.append({"role": "model", "parts": [{"text": content}]})
    system_text = "\n\n".join(system_parts) if system_parts else None
    return system_text, contents


def _google_generate_content(
    api_key: str,
    model: str,
    system_text: str | None,
    contents: list[dict],
    max_429_retries: int,
    debug_mode: bool,
    deadline: float,
) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload: dict = {"contents": contents, "generationConfig": {"temperature": 0.7}}
    if system_text:
        payload["systemInstruction"] = {"parts": [{"text": system_text}]}

    attempt = 0
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 1.0:
            raise TimeoutError(f"global LLM budget exhausted before/while calling {model}")

        timeout = httpx.Timeout(
            connect=min(10.0, remaining), read=remaining,
            write=min(10.0, remaining), pool=min(10.0, remaining),
        )

        try:
            with httpx.Client(timeout=timeout) as client:
                r = client.post(url, json=payload)
        except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ConnectError) as net_err:
            remaining = deadline - time.monotonic()
            if attempt == 0 and remaining > 3.0:
                if debug_mode:
                    print(f"[GOOGLE DEBUG] network error on {model}, retrying once: {net_err!r}")
                time.sleep(min(1.5, remaining - 1))
                attempt += 1
                continue
            raise

        if r.status_code == 429:
            remaining = deadline - time.monotonic()
            if attempt < max_429_retries and remaining > 3.0:
                wait = min(_backoff_seconds(attempt, r.headers.get("retry-after")), remaining - 1)
                if debug_mode:
                    print(f"[GOOGLE DEBUG] 429 on {model}, attempt={attempt + 1}, sleeping {wait:.1f}s")
                time.sleep(max(0.0, wait))
                attempt += 1
                continue
            r.raise_for_status()

        r.raise_for_status()
        data = r.json()

        try:
            candidate = data["candidates"][0]
            content = candidate["content"]["parts"][0]["text"]
        except (KeyError, IndexError):
            finish_reason = (data.get("candidates") or [{}])[0].get("finishReason", "UNKNOWN")
            raise ValueError(f"no usable content from model={model}, finishReason={finish_reason}")

        content = content.strip()
        if not content:
            raise ValueError(f"empty completion from model={model}")
        if _has_forbidden_script(content):
            raise ValueError(f"forbidden non-Persian script detected in output from model={model}")
        if _has_leaked_reasoning(content):
            raise ValueError(f"leaked chain-of-thought reasoning detected in output from model={model}")
        return content


def _result(text: str, model_path: str, model_name: str | None) -> dict:
    return {"text": text, "model_path": model_path, "model_name": model_name}


def _run_cascade(messages: list[dict], log_prefix: str = "LLM") -> dict:
    """Shared cascade with a hard total time budget. Branches early on
    provider: 'google' talks to Google's native API directly (Gemma/Gemini,
    dedicated per-key quota); anything else uses the OpenAI-compatible path
    (OpenRouter, Aval, etc.)."""
    (
        provider, api_key, base_url, model, fallback_model, final_fallback_model,
        debug_mode, total_budget_s, max_429_retries, site_url, site_name,
        google_api_key, google_model, google_fallback_model,
    ) = _env()

    if provider == "mock":
        return _result(f"Received: {messages[-1]['content']}", "none", None)

    deadline = time.monotonic() + total_budget_s

    if provider == "google":
        if not google_api_key:
            if debug_mode:
                print(f"[{log_prefix} DEBUG] missing GOOGLE_API_KEY")
            return _result("کلید API تنظیم نشده است.", "error", None)

        system_text, contents = _messages_to_google_format(messages)
        attempts = [("primary", google_model), ("fallback", google_fallback_model)]

        for path_name, model_name_ in attempts:
            if not model_name_:
                continue
            if time.monotonic() >= deadline - 1.0:
                print(f"[{log_prefix} DEBUG] skipping {path_name} ({model_name_}): global budget exhausted")
                break
            t0 = time.perf_counter()
            try:
                out = _google_generate_content(
                    google_api_key, model_name_, system_text, contents,
                    max_429_retries, debug_mode, deadline,
                )
                if debug_mode:
                    print(f"[{log_prefix} DEBUG] {path_name}_success model={model_name_} elapsed_s={time.perf_counter() - t0:.1f}")
                return _result(out, path_name, model_name_)
            except Exception as e:
                print(f"[{log_prefix} ERROR {path_name}] model={model_name_} elapsed_s={time.perf_counter() - t0:.1f} err={e!r}")

        return _result("متأسفم، در ارتباط با مدل مشکلی پیش آمد. لطفاً دوباره تلاش کن.", "error", None)

    # --- OpenAI-compatible path (OpenRouter, Aval, ...) ---
    if not api_key:
        if debug_mode:
            print(f"[{log_prefix} DEBUG] missing API key")
        return _result("کلید API تنظیم نشده است.", "error", None)

    attempts = [
        ("primary", model),
        ("fallback", fallback_model),
        ("final_fallback", final_fallback_model),
    ]

    for path_name, model_name_ in attempts:
        if not model_name_:
            continue
        if time.monotonic() >= deadline - 1.0:
            print(f"[{log_prefix} DEBUG] skipping {path_name} ({model_name_}): global budget exhausted")
            break
        t0 = time.perf_counter()
        try:
            out = _chat_completion(
                base_url, api_key, model_name_, messages,
                max_429_retries, debug_mode, site_url, site_name,
                deadline=deadline,
            )
            if debug_mode:
                print(f"[{log_prefix} DEBUG] {path_name}_success model={model_name_} elapsed_s={time.perf_counter() - t0:.1f}")
            return _result(out, path_name, model_name_)
        except Exception as e:
            print(f"[{log_prefix} ERROR {path_name}] model={model_name_} elapsed_s={time.perf_counter() - t0:.1f} err={e!r}")

    return _result("متأسفم، در ارتباط با مدل مشکلی پیش آمد. لطفاً دوباره تلاش کن.", "error", None)


def generate_reply(user_text: str) -> dict:
    return generate_reply_with_context(
        user_text=user_text, profile_context=None, history=[], memory_summary=None,
    )


def generate_reply_with_context(
    user_text: str,
    profile_context: str | None,
    history: list[dict],
    memory_summary: str | None = None,
    kb_context: str | None = None,
) -> dict:
    debug_mode = (os.getenv("DEBUG", "false") or "false").strip().lower() in ("1", "true", "yes", "on")

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
            f"kb_context={'yes' if bool(kb_context) else 'no'}"
        )

    return _run_cascade(messages, log_prefix="LLM")


def summarize_conversation(transcript_text: str) -> dict:
    messages = [
        {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
        {"role": "user", "content": transcript_text[:6000]},
    ]
    return _run_cascade(messages, log_prefix="SUMMARY")