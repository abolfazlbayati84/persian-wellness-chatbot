from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.chat import (
    ConversationGetOrCreateRequest,
    ConversationGetOrCreateResponse,
    ConversationRead,
    MessageCreate,
    MessageRead,
    ChatTurnRequest,
    ChatTurnResponse,
)
from app.services.chat_service import add_message, get_or_create_conversation, list_messages, run_chat_turn

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
        raise HTTPException(status_code=400, detail=str(exc))
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

@router.post("/turn", response_model=ChatTurnResponse, status_code=status.HTTP_201_CREATED)
def chat_turn_endpoint(
    payload: ChatTurnRequest,
    db: Session = Depends(get_db),
) -> ChatTurnResponse:
    try:
        conversation_id, user_msg, assistant_msg = run_chat_turn(db=db, payload=payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        raise HTTPException(status_code=500, detail="AI request failed.")

    return ChatTurnResponse(
        conversation_id=conversation_id,
        user_message_id=user_msg.id,
        assistant_message_id=assistant_msg.id,
        assistant_reply=assistant_msg.content,
    )