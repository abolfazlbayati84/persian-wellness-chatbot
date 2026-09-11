from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, Literal

ModelPath = Literal["primary", "fallback", "final_fallback", "none", "error", "unknown"]


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
    trace_id: Optional[str] = None  # populated only when DEBUG is on


class TraceItem(BaseModel):
    trace_id: Optional[str] = None
    session_id: int
    user_id: int
    user_text_preview: Optional[str] = None
    domain_tag: str
    risk_tier: str
    session_risk_tier: Optional[str] = None

    history_count: int
    used_memory_summary: bool
    memory_summary_preview: Optional[str] = None

    used_profile_context: bool
    profile_fields_used: list[str] = Field(default_factory=list)

    retrieved_chunk_ids: list[int] = Field(default_factory=list)

    primary_model: Optional[str] = None
    fallback_model: Optional[str] = None
    final_fallback_model: Optional[str] = None
    used_model_path: ModelPath = "none"
    used_model_name: Optional[str] = None

    fallback_used: bool = False
    output_blocked: bool = False
    latency_ms: int