from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, ConfigDict


class UserCreate(BaseModel):
    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=6)
    locale: str = "fa-IR"
    status: str = "active"


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr | None
    locale: str
    status: str
    created_at: datetime
    updated_at: datetime