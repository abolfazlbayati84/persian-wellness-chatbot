from typing import List, Dict, Any


def build_memory_summary(messages: List[Dict[str, Any]], max_chars: int = 700) -> str:
    """
    messages: chronological list
    each item: {
      "role": "user"|"assistant",
      "content": "...",
      "risk_tier": "...",
      "domain_tag": "..."
    }
    """

    if not messages:
        return ""

    user_msgs = [m for m in messages if m.get("role") == "user"]

    # last non-other domain
    domain = "other"
    for m in reversed(user_msgs):
        d = (m.get("domain_tag") or "other").strip().lower()
        if d and d != "other":
            domain = d
            break

    # last risk
    risk = "normal"
    for m in reversed(user_msgs):
        r = (m.get("risk_tier") or "normal").strip().lower()
        if r:
            risk = r
            break

    # last 3 user points
    last_user_texts = [m.get("content", "").strip() for m in user_msgs if m.get("content")]
    last_user_texts = last_user_texts[-3:]

    lines = ["MEMORY SUMMARY", f"- dominant_domain: {domain}", f"- recent_risk: {risk}"]

    if last_user_texts:
        lines.append("- recent_user_points:")
        for t in last_user_texts:
            one_line = " ".join(t.split())
            if len(one_line) > 180:
                one_line = one_line[:180] + "..."
            lines.append(f"  - {one_line}")

    summary = "\n".join(lines)
    if len(summary) > max_chars:
        summary = summary[:max_chars] + "..."
    return summary