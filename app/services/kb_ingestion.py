import json

from app.services.llm_client import _run_cascade

VALID_DOMAINS = {
    "stress_anxiety",
    "depression_motivation",
    "relationships_social",
    "time_management_study",
    "self_esteem",
}

ADAPT_SYSTEM_PROMPT = (
    "You are building a Persian-language psychoeducational knowledge base "
    "for a mental-wellness chatbot. The chatbot covers EXACTLY these five "
    "domains, identified by these exact codes:\n"
    "- stress_anxiety\n- depression_motivation\n- relationships_social\n"
    "- time_management_study\n- self_esteem\n\n"
    "You will be given a piece of raw source material (e.g. a real "
    "counselor's answer to a user's question, or an excerpt from a "
    "self-help resource). Your job:\n"
    "1. Identify any generalizable, reusable psychoeducational technique(s) "
    "or piece(s) of practical advice in the source that fit one of the five "
    "domains above. Ignore anything that is just a one-off personal "
    "narrative with no reusable technique, anything about a topic outside "
    "the five domains (e.g. addiction, grief, parenting, anger management, "
    "psychosis, trauma/PTSD, eating disorders), and anything that "
    "recommends medication, diagnosis, or specific dosages.\n"
    "2. For each such technique found (there may be zero, one, or a few in "
    "a single source), write a natural, fluent, standalone Persian "
    "explanation of it -- NOT a literal translation. Write it as general "
    "advice anyone could read, not addressed to the original asker. "
    "120-250 Persian words. Give it a short Persian title.\n"
    "3. Respond with ONLY valid JSON, no markdown code fences, no extra "
    "commentary, in exactly this shape:\n"
    '{"entries": [{"domain": "<one of the five codes>", "title": "...", '
    '"content": "..."}]}\n'
    'If nothing usable is found, respond with exactly: {"entries": []}'
)


def adapt_source_to_kb_entries(raw_source_text: str) -> list[dict]:
    """Given arbitrary raw source text (a counseling Q&A pair today; a book
    excerpt or anything else later), ask the LLM to extract zero or more
    reusable, domain-tagged Persian psychoeducational KB entries from it.
    This is deliberately source-agnostic so future loaders (books, other
    datasets) can reuse it unchanged."""
    messages = [
        {"role": "system", "content": ADAPT_SYSTEM_PROMPT},
        {"role": "user", "content": raw_source_text[:4000]},
    ]
    result = _run_cascade(messages, log_prefix="KB_ADAPT")

    text = (result.get("text") or "").strip()
    if not text or text.startswith("متأسفم"):
        return []

    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        print(f"[KB_ADAPT WARNING] could not parse JSON, skipping. raw={text[:200]!r}")
        return []

    entries = data.get("entries", [])
    valid = []
    for e in entries:
        domain = e.get("domain")
        title = (e.get("title") or "").strip()
        content = (e.get("content") or "").strip()
        if domain in VALID_DOMAINS and title and len(content) > 40:
            valid.append({"domain": domain, "title": title, "content": content})
    return valid