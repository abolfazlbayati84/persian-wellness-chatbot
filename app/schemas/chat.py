from datetime import datetime
from pydantic import BaseModel, ConfigDict
from typing import Optional, Literal


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


class TraceItem(BaseModel):
    session_id: int
    user_id: int
    domain_tag: str
    risk_tier: str
    session_risk_tier: Optional[str] = None
    history_count: int
    used_memory_summary: bool
    memory_summary_preview: Optional[str] = None
    used_profile_context: bool

    # renamed from model_primary/model_fallback/model_used
    primary_model: Optional[str] = None
    fallback_model: Optional[str] = None
    used_model_path: Optional[Literal["primary", "fallback", "none"]] = "none"

    fallback_used: bool = False
    latency_ms: int