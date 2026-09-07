from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import time

from app.database.session import get_db
from app.models.user import User
from app.models.profile import Profile
from app.models.session import Session as ChatSession
from app.models.message import Message

from app.schemas.user import UserCreate, UserRead
from app.schemas.profile import ProfileUpsert, ProfileRead
from app.schemas.session import SessionCreate, SessionRead, SessionMessagesOut
from app.schemas.chat import ChatTurnIn, ChatTurnOut, MessageRead
from app.schemas.auth import LoginIn, TokenOut

from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
)

from app.services.llm_client import generate_reply_with_context
from app.services.classifiers import classify_domain, classify_risk, max_risk
from app.services.safety_templates import CRISIS_FA

from app.services.classifiers import classify_domain, classify_risk, max_risk, is_blocked_output
from app.services.safety_templates import CRISIS_FA, MODERATE_FA, BLOCKED_OUTPUT_FA

router = APIRouter()
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if not creds or creds.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Not authenticated")

    payload = decode_access_token(creds.credentials)
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="Invalid token")

    try:
        user_id = int(sub)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid token subject")

    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


@router.post("/auth/login", response_model=TokenOut)
def login(payload: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not user.password_hash:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(subject=str(user.id))
    return TokenOut(access_token=token)


@router.get("/auth/me")
def auth_me(current_user: User = Depends(get_current_user)):
    return {"id": current_user.id, "email": current_user.email}

@router.post("/users", response_model=UserRead, status_code=201)
def create_user(payload: UserCreate, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already exists")

    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password) if payload.password else None,
        locale=payload.locale,
        status=payload.status,
    )
    db.add(user)

    try:
        db.commit()
        db.refresh(user)
        return user
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="IntegrityError")


@router.post("/onboarding/profile", response_model=ProfileRead)
def upsert_profile(
    payload: ProfileUpsert,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if payload.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    user = db.get(User, payload.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    profile = db.query(Profile).filter(Profile.user_id == payload.user_id).first()
    if not profile:
        profile = Profile(user_id=payload.user_id)
        db.add(profile)

    for k, v in payload.model_dump().items():
        if k != "user_id":
            setattr(profile, k, v)

    db.commit()
    db.refresh(profile)
    return profile


@router.post("/sessions", response_model=SessionRead)
def create_session(
    payload: SessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if payload.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    user = db.get(User, payload.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    s = ChatSession(user_id=payload.user_id)
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


@router.post("/chat/turn", response_model=ChatTurnOut)
def chat_turn(
    payload: ChatTurnIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    started = time.perf_counter()

    s = db.get(ChatSession, payload.session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    if s.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    domain_tag = classify_domain(payload.user_text)
    risk_tier = classify_risk(payload.user_text)

    # A2.1.1 domain carry-over
    if domain_tag == "other":
        last_domain_msg = (
            db.query(Message)
            .filter(
                Message.session_id == s.id,
                Message.domain_tag.isnot(None),
                Message.domain_tag != "other",
            )
            .order_by(Message.created_at.desc(), Message.id.desc())
            .first()
        )
        if last_domain_msg:
            domain_tag = last_domain_msg.domain_tag

    user_msg = Message(
        session_id=s.id,
        role="user",
        content=payload.user_text,
        domain_tag=domain_tag,
        risk_tier=risk_tier,
    )
    db.add(user_msg)
    db.flush()

    if risk_tier == "severe":
        assistant_text = CRISIS_FA
        fallback_used = True
    elif risk_tier == "moderate":
        profile = db.query(Profile).filter(Profile.user_id == s.user_id).first()
        profile_parts = []
        if profile:
            for field in ["age_range", "sleep_quality", "stress_level", "activity_level", "goal", "notes"]:
                if hasattr(profile, field):
                    val = getattr(profile, field)
                    if val not in (None, "", []):
                        profile_parts.append(f"{field}: {val}")
        profile_context = "\n".join(profile_parts) if profile_parts else None

        rows = (
            db.query(Message)
            .filter(
                Message.session_id == s.id,
                Message.id != user_msg.id,
                Message.role.in_(["user", "assistant"]),
            )
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(10)
            .all()
        )
        rows = list(reversed(rows))
        history = [{"role": m.role, "content": m.content} for m in rows]

        llm_text = generate_reply_with_context(
            user_text=payload.user_text,
            profile_context=profile_context,
            history=history,
        )
        assistant_text = f"{MODERATE_FA}\n\n{llm_text}"
        fallback_used = False
    else:
        profile = db.query(Profile).filter(Profile.user_id == s.user_id).first()
        profile_parts = []
        if profile:
            for field in ["age_range", "sleep_quality", "stress_level", "activity_level", "goal", "notes"]:
                if hasattr(profile, field):
                    val = getattr(profile, field)
                    if val not in (None, "", []):
                        profile_parts.append(f"{field}: {val}")
        profile_context = "\n".join(profile_parts) if profile_parts else None

        rows = (
            db.query(Message)
            .filter(
                Message.session_id == s.id,
                Message.id != user_msg.id,
                Message.role.in_(["user", "assistant"]),
            )
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(10)
            .all()
        )
        rows = list(reversed(rows))
        history = [{"role": m.role, "content": m.content} for m in rows]

        assistant_text = generate_reply_with_context(
            user_text=payload.user_text,
            profile_context=profile_context,
            history=history,
        )
        fallback_used = False

    # Post-generation output guardrail
    if is_blocked_output(assistant_text):
        assistant_text = BLOCKED_OUTPUT_FA

    assistant_msg = Message(
        session_id=s.id,
        role="assistant",
        content=assistant_text,
        domain_tag=domain_tag,
        risk_tier=risk_tier,
    )
    db.add(assistant_msg)

    # A2.1 roll-up
    s.risk_tier = max_risk(getattr(s, "risk_tier", None), risk_tier)

    db.commit()
    db.refresh(user_msg)
    db.refresh(assistant_msg)
    db.refresh(s)

    latency_ms = int((time.perf_counter() - started) * 1000)
    print(
        f"[CHAT_TURN] session_id={s.id} domain={domain_tag} "
        f"risk={risk_tier} session_risk={s.risk_tier} "
        f"fallback={fallback_used} latency_ms={latency_ms}"
    )

    return ChatTurnOut(
        user_message=MessageRead.model_validate(user_msg),
        assistant_message=MessageRead.model_validate(assistant_msg),
    )


@router.get("/sessions/{session_id}", response_model=SessionRead)
def get_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    s = db.get(ChatSession, session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    if s.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    return s


@router.get("/sessions/{session_id}/messages", response_model=SessionMessagesOut)
def get_session_messages(
    session_id: int,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    s = db.get(ChatSession, session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    if s.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    q = db.query(Message).filter(Message.session_id == session_id)
    total = q.count()

    rows = (
        q.order_by(Message.created_at.asc(), Message.id.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return SessionMessagesOut(
        session=SessionRead.model_validate(s),
        total=total,
        limit=limit,
        offset=offset,
        items=[MessageRead.model_validate(m) for m in rows],
    )