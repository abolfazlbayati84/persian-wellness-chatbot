from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.chat import (
    ConversationGetOrCreateRequest,
    ConversationGetOrCreateResponse,
    ConversationRead,
    MessageCreate,
    MessageRead,
)
from app.services.chat_service import add_message, get_or_create_conversation, list_messages

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/conversations/get-or-create", response_model=ConversationGetOrCreateResponse)
def get_or_create_conversation_endpoint(
    payload: ConversationGetOrCreateRequest,
    db: Session = Depends(get_db),
) -> ConversationGetOrCreateResponse:
    conversation, created = get_or_create_conversation(db=db, payload=payload)
    return ConversationGetOrCreateResponse(
        created=created,
        conversation=ConversationRead.model_validate(conversation),
    )


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=MessageRead,
    status_code=status.HTTP_201_CREATED,
)
def add_message_endpoint(
    conversation_id: int,
    payload: MessageCreate,
    db: Session = Depends(get_db),
) -> MessageRead:
    try:
        message = add_message(db=db, conversation_id=conversation_id, payload=payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return MessageRead.model_validate(message)


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageRead])
def list_messages_endpoint(
    conversation_id: int,
    db: Session = Depends(get_db),
) -> list[MessageRead]:
    try:
        messages = list_messages(db=db, conversation_id=conversation_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return [MessageRead.model_validate(m) for m in messages]