from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserCreate(BaseModel):
    platform_user_id: str = Field(
        min_length=1,
        max_length=100,
        examples=["telegram_123456"],
    )
    name: str | None = Field(
        default=None,
        max_length=100,
        examples=["Sara"],
    )


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    platform_user_id: str
    name: str | None
    created_at: datetime
    updated_at: datetime

class UserGetOrCreateResponse(BaseModel):
    created: bool
    user: UserRead