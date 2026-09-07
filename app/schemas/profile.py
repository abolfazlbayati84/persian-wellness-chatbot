from datetime import datetime
from pydantic import BaseModel, ConfigDict


class ProfileUpsert(BaseModel):
    user_id: int
    age_range: str | None = None
    gender: str | None = None
    locale: str = "fa-IR"
    primary_concerns: str | None = None
    goals: str | None = None
    communication_preferences: str | None = None
    consent_privacy: bool = False
    consent_ai_support: bool = False
    consent_emergency: bool = False
    onboarding_completed: bool = False


class ProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    age_range: str | None
    gender: str | None
    locale: str
    primary_concerns: str | None
    goals: str | None
    communication_preferences: str | None
    consent_privacy: bool
    consent_ai_support: bool
    consent_emergency: bool
    onboarding_completed: bool
    created_at: datetime
    updated_at: datetime