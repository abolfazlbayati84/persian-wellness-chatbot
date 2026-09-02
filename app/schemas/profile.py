from datetime import datetime

from pydantic import BaseModel, Field, ConfigDict


class ProfileBase(BaseModel):
    age_range: str | None = Field(default=None, max_length=30)
    gender: str | None = Field(default=None, max_length=30)
    locale: str = Field(default="fa-IR", max_length=10)

    primary_concerns: str | None = None
    goals: str | None = None
    communication_preferences: str | None = None

    consent_privacy: bool = False
    consent_ai_support: bool = False
    consent_emergency: bool = False

    onboarding_completed: bool = False


class ProfileCreate(ProfileBase):
    user_id: int


class ProfileUpdate(BaseModel):
    age_range: str | None = Field(default=None, max_length=30)
    gender: str | None = Field(default=None, max_length=30)
    locale: str | None = Field(default=None, max_length=10)

    primary_concerns: str | None = None
    goals: str | None = None
    communication_preferences: str | None = None

    consent_privacy: bool | None = None
    consent_ai_support: bool | None = None
    consent_emergency: bool | None = None

    onboarding_completed: bool | None = None


class ProfileRead(ProfileBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime