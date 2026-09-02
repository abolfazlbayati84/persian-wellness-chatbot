from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ConversationGetOrCreateRequest(BaseModel):
    user_platform_id: str = Field(min_length=1, max_length=100, examples=["telegram_123456"])
    platform: str = Field(min_length=1, max_length=30, examples=["telegram"])
    external_conversation_id: str | None = Field(default=None, max_length=100, examples=["chat_999"])
    title: str | None = Field(default=None, max_length=200, examples=["Daily wellness chat"])


class ConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    platform: str
    external_conversation_id: str | None
    title: str | None
    created_at: datetime
    updated_at: datetime


class ConversationGetOrCreateResponse(BaseModel):
    created: bool
    conversation: ConversationRead


class MessageCreate(BaseModel):
    role: str = Field(min_length=1, max_length=20, examples=["user"])
    content: str = Field(min_length=1, examples=["I feel anxious today."])


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: int
    role: str
    content: str
    created_at: datetime

class ChatTurnRequest(BaseModel):
    user_platform_id: str = Field(min_length=1, max_length=100)
    platform: str = Field(min_length=1, max_length=30)
    external_conversation_id: str | None = Field(default=None, max_length=100)
    title: str | None = Field(default=None, max_length=200)
    user_message: str = Field(min_length=1)


class ChatTurnResponse(BaseModel):
    conversation_id: int
    user_message_id: int
    assistant_message_id: int
    assistant_reply: str