import re
from app.services.llm_client import _run_cascade

VALID_DOMAINS = {
    "stress", "sleep", "anxiety", "depression", "burnout",
    "relationships", "self_esteem", "study", "other",
}
VALID_RISKS = {"none", "low", "moderate", "severe"}

_SYSTEM = (
    "You are a precise classifier for a Persian mental-wellness chatbot. "
    "Given the user's message, output exactly two comma-separated values: "
    "a DOMAIN and a RISK tier, nothing else.\n"
    "DOMAIN must be exactly one of: stress, sleep, anxiety, depression, "
    "burnout, relationships, self_esteem, study, other.\n"
    "RISK must be exactly one of:\n"
    "- severe: any suicidal ideation, self-harm intent, wanting to end "
    "one's life, or wishing to not exist -- however indirect, idiomatic, "
    "or softly phrased (e.g. 'کاش نبودم', 'دیگه دلیلی برای ادامه نمی‌بینم', "
    "'می‌خوام همه چی تموم بشه'). When genuinely unsure between severe and "
    "moderate, choose severe.\n"
    "- moderate: hopelessness, feeling worthless, panic attacks, feeling "
    "unable to cope, but no indication of wanting to end one's life.\n"
    "- low: everyday stress, anxiety, poor sleep, fatigue, low mood, with "
    "no signs of hopelessness or crisis.\n"
    "- none: no distress signal at all (e.g. small talk, a factual "
    "question, positive mood).\n"
    "Respond with ONLY 'domain,risk', e.g. 'anxiety,low'. No explanation."
)


def classify_message(text: str) -> dict:
    """LLM-based domain+risk classification. Falls back to
    {"domain": "other", "risk": "none"} on any parse failure or model
    error -- the caller (routes.py) always combines this with the fast,
    keyword-based classifiers.py as a safety backstop, never relies on
    this alone for risk."""
    messages = [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": text},
    ]
    result = _run_cascade(messages, log_prefix="CLASSIFY")
    raw = (result.get("text") or "").strip().lower()

    domain, risk = "other", "none"
    m = re.match(r"^\s*([a-z_]+)\s*,\s*([a-z_]+)\s*$", raw)
    if m:
        d, r = m.group(1), m.group(2)
        if d in VALID_DOMAINS:
            domain = d
        if r in VALID_RISKS:
            risk = r
    return {"domain": domain, "risk": risk}