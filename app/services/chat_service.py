from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User
from app.schemas.chat import ConversationGetOrCreateRequest, MessageCreate
from app.schemas.user import UserCreate
from app.services.user_service import get_or_create_user


def get_or_create_conversation(
    db: Session,
    payload: ConversationGetOrCreateRequest,
) -> tuple[Conversation, bool]:
    # Ensure user exists first
    user, _ = get_or_create_user(
        db=db,
        user_data=UserCreate(
            platform_user_id=payload.user_platform_id,
            name=None,
        ),
    )

    stmt = select(Conversation).where(
        Conversation.user_id == user.id,
        Conversation.platform == payload.platform,
        Conversation.external_conversation_id == payload.external_conversation_id,
    )
    conversation = db.scalar(stmt)

    if conversation is not None:
        # optional title fill/update
        if payload.title and conversation.title != payload.title:
            conversation.title = payload.title
            db.commit()
            db.refresh(conversation)
        return conversation, False

    conversation = Conversation(
        user_id=user.id,
        platform=payload.platform,
        external_conversation_id=payload.external_conversation_id,
        title=payload.title,
    )
    db.add(conversation)

    try:
        db.commit()
        db.refresh(conversation)
        return conversation, True
    except IntegrityError:
        db.rollback()
        # race-condition fallback
        conversation = db.scalar(stmt)
        if conversation is None:
            raise
        return conversation, False


def add_message(
    db: Session,
    conversation_id: int,
    payload: MessageCreate,
) -> Message:
    conversation = db.get(Conversation, conversation_id)
    if conversation is None:
        raise ValueError("Conversation not found.")

    message = Message(
        conversation_id=conversation_id,
        role=payload.role,
        content=payload.content,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def list_messages(
    db: Session,
    conversation_id: int,
) -> list[Message]:
    conversation = db.get(Conversation, conversation_id)
    if conversation is None:
        raise ValueError("Conversation not found.")

    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc(), Message.id.asc())
    )
    return list(db.scalars(stmt).all())