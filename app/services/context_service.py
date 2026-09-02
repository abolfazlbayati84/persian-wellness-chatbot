from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.profile import Profile


def build_profile_context(db: Session, user_id: int) -> str:
    profile = db.scalar(select(Profile).where(Profile.user_id == user_id))
    if profile is None:
        return "پروفایل کاربر تکمیل نشده است."

    lines: list[str] = []
    lines.append("خلاصه پروفایل کاربر:")

    if profile.age_range:
        lines.append(f"- بازه سنی: {profile.age_range}")
    if profile.gender:
        lines.append(f"- جنسیت: {profile.gender}")
    if profile.locale:
        lines.append(f"- زبان/منطقه: {profile.locale}")
    if profile.primary_concerns:
        lines.append(f"- دغدغه‌های اصلی: {profile.primary_concerns}")
    if profile.goals:
        lines.append(f"- اهداف: {profile.goals}")
    if profile.communication_preferences:
        lines.append(f"- ترجیحات ارتباطی: {profile.communication_preferences}")

    lines.append(
        f"- رضایت‌ها: privacy={profile.consent_privacy}, ai_support={profile.consent_ai_support}, emergency={profile.consent_emergency}"
    )
    lines.append(f"- تکمیل آنبوردینگ: {profile.onboarding_completed}")

    return "\n".join(lines)