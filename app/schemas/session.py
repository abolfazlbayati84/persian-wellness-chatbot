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


class SessionListItem(BaseModel):
    id: int
    started_at: datetime | None = None
    ended_at: datetime | None = None
    risk_tier: str | None = None
    preview: str | None = None
    domain_tag: str | None = None
    message_count: int = 0


class SessionMessagesOut(BaseModel):
    session: SessionRead
    total: int
    limit: int
    offset: int
    items: List[MessageRead] = Field(default_factory=list)