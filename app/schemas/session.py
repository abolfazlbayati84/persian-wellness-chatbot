from datetime import datetime
from pydantic import BaseModel, Field
from typing import List

from app.schemas.chat import MessageRead


class SessionCreate(BaseModel):
    user_id: int


class SessionRead(BaseModel):
    id: int
    user_id: int
    started_at: datetime | None = None
    ended_at: datetime | None = None
    summary: str | None = None
    risk_tier: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SessionMessagesOut(BaseModel):
    session: SessionRead
    total: int
    limit: int
    offset: int
    items: List[MessageRead] = Field(default_factory=list)