from datetime import datetime
from pydantic import BaseModel, ConfigDict


class ChatTurnIn(BaseModel):
    session_id: int
    user_text: str


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int
    role: str
    content: str
    domain_tag: str | None
    risk_tier: str | None
    created_at: datetime


class ChatTurnOut(BaseModel):
    user_message: MessageRead
    assistant_message: MessageRead