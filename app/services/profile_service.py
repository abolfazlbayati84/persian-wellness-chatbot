from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.profile import Profile
from app.models.user import User
from app.schemas.profile import ProfileCreate, ProfileUpdate


def create_or_replace_profile(db: Session, payload: ProfileCreate) -> Profile:
    user = db.get(User, payload.user_id)
    if user is None:
        raise ValueError("User not found.")

    profile = db.scalar(select(Profile).where(Profile.user_id == payload.user_id))

    if profile is None:
        profile = Profile(user_id=payload.user_id)
        db.add(profile)

    profile.age_range = payload.age_range
    profile.gender = payload.gender
    profile.locale = payload.locale
    profile.primary_concerns = payload.primary_concerns
    profile.goals = payload.goals
    profile.communication_preferences = payload.communication_preferences
    profile.consent_privacy = payload.consent_privacy
    profile.consent_ai_support = payload.consent_ai_support
    profile.consent_emergency = payload.consent_emergency
    profile.onboarding_completed = payload.onboarding_completed

    db.commit()
    db.refresh(profile)
    return profile


def get_profile_by_user_id(db: Session, user_id: int) -> Profile:
    profile = db.scalar(select(Profile).where(Profile.user_id == user_id))
    if profile is None:
        raise ValueError("Profile not found.")
    return profile


def patch_profile(db: Session, user_id: int, payload: ProfileUpdate) -> Profile:
    profile = db.scalar(select(Profile).where(Profile.user_id == user_id))
    if profile is None:
        raise ValueError("Profile not found.")

    data = payload.model_dump(exclude_unset=True)

    for field, value in data.items():
        setattr(profile, field, value)

    db.commit()
    db.refresh(profile)
    return profile