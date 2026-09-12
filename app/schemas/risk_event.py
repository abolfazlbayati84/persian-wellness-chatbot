from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, Literal


class RiskEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    session_id: int
    message_id: Optional[int] = None
    risk_tier: str
    domain_tag: Optional[str] = None
    user_text_snapshot: str
    status: str
    reviewer_note: Optional[str] = None
    reviewed_by_user_id: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime


class RiskEventReviewIn(BaseModel):
    status: Literal["reviewed", "dismissed"]
    reviewer_note: Optional[str] = Field(default=None, max_length=2000)