# app/services/classifiers.py
from __future__ import annotations

import re
from typing import Literal

DomainTag = Literal["stress", "sleep", "anxiety", "depression", "burnout", "other"]
RiskTier = Literal["none", "low", "moderate", "severe"]


def _contains_any(text: str, keywords: list[str]) -> bool:
    t = (text or "").lower()
    return any(k in t for k in keywords)


def _any_pattern(text: str, patterns: list[str]) -> bool:
    t = (text or "").strip()
    return any(re.search(p, t, flags=re.IGNORECASE) for p in patterns)


def classify_domain(text: str) -> DomainTag:
    t = (text or "").lower()

    sleep_kw = [
        "خواب", "بیخوابی", "بی‌خوابی", "بدخوابی", "دیر میخوابم", "دیر می‌خوابم",
        "زود بیدار", "بیدار میشم", "بیدار می‌شم", "کابوس",
        "sleep", "insomnia", "sleepy", "tired", "fatigue", "circadian",
        "تمرکز ندارم", "بی تمرکز", "بی‌تمرکز", "خسته‌ام", "خستم", "خستگی روزانه",
    ]
    stress_kw = [
        "استرس", "تنش", "فشار", "overwhelmed", "stress", "under pressure",
    ]
    anxiety_kw = [
        "اضطراب", "نگرانی", "دلشوره", "دل‌شوره", "وحشت", "پنیک",
        "anxiety", "panic", "panic attack", "restless",
    ]
    depression_kw = [
        "افسرده", "افسردگی", "غمگین", "بی انگیزه", "بی‌انگیزه", "ناامید",
        "depress", "depression", "hopeless", "worthless",
    ]
    burnout_kw = [
        "فرسودگی", "فرسوده", "فرسودم", "خسته از کار", "بی‌رمق", "تحلیل رفتم",
        "burnout", "burned out", "work exhaustion",
    ]

    # priority order to reduce false-other
    if _contains_any(t, sleep_kw):
        return "sleep"
    if _contains_any(t, anxiety_kw):
        return "anxiety"
    if _contains_any(t, depression_kw):
        return "depression"
    if _contains_any(t, burnout_kw):
        return "burnout"
    if _contains_any(t, stress_kw):
        return "stress"

    return "other"


SEVERE_PATTERNS = [
    r"خودکشی",
    r"می.?خوام خودمو بکشم",
    r"می.?خوام به زندگیم پایان بدم",
    r"به زندگیم پایان بدم",
    r"دیگه نمی.?خوام زنده باشم",
    r"می.?خوام خودمو نابود کنم",
    r"suicide",
    r"kill myself",
    r"end my life",
    r"self[- ]?harm",
]

MODERATE_PATTERNS = [
    r"ناامید",
    r"بی.?ارزش",
    r"هیچ راهی ندارم",
    r"وحشت.?زد[ه]",
    r"حمله پنیک",
    r"panic attack",
    r"نمی.?تونم ادامه بدم",
]

LOW_PATTERNS = [
    r"استرس",
    r"اضطراب",
    r"نگران",
    r"بی.?خواب",
    r"خسته",
    r"تمرکز ندارم",
    r"دلشوره",
]


def classify_risk(text: str) -> RiskTier:
    if _any_pattern(text, SEVERE_PATTERNS):
        return "severe"
    if _any_pattern(text, MODERATE_PATTERNS):
        return "moderate"
    if _any_pattern(text, LOW_PATTERNS):
        return "low"
    return "none"


def max_risk(a: RiskTier | None, b: RiskTier | None) -> RiskTier:
    rank = {"none": 0, "low": 1, "moderate": 2, "severe": 3}
    aa = a if a in rank else "none"
    bb = b if b in rank else "none"
    return aa if rank[aa] >= rank[bb] else bb


BLOCKED_OUTPUT_PATTERNS = [
    r"how to kill myself",
    r"بهترین روش خودکشی",
    r"چطور خودمو بکشم",
    r"دوز\s*دارو",
    r"overdose",
    r"\bOD\b",          # now actually reachable (IGNORECASE, no .lower())
    r"راهنمای آسیب به خود",
]


def is_blocked_output(text: str) -> bool:
    return _any_pattern(text, BLOCKED_OUTPUT_PATTERNS)