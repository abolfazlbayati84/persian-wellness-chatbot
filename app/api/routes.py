import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.database.session import get_db
from app.models.user import User
from app.models.profile import Profile
from app.models.session import Session as ChatSession
from app.models.message import Message

from app.schemas.user import UserCreate, UserRead
from app.schemas.profile import ProfileUpsert, ProfileRead
from app.schemas.session import SessionCreate, SessionRead, SessionMessagesOut
from app.schemas.chat import ChatTurnIn, ChatTurnOut, MessageRead, TraceItem
from app.schemas.auth import LoginIn, TokenOut

from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
)

from app.services.llm_client import generate_reply_with_context
from app.services.classifiers import classify_domain, classify_risk, max_risk, is_blocked_output
from app.services.safety_templates import CRISIS_FA, MODERATE_FA, BLOCKED_OUTPUT_FA
from app.services.memory_service import build_memory_summary
from app.services.trace_store import add_trace, list_traces, clear_traces

router = APIRouter()
bearer_scheme = HTTPBearer(auto_error=False)

# single source of truth for which profile fields may enter the prompt
PROFILE_FIELDS = [
    "age_range",
    "gender",
    "primary_concerns",
    "goals",
    "communication_preferences",
]

HISTORY_LIMIT = 12
MEMORY_PREVIEW_CHARS = 260

# legacy fallback: only used if llm_client does not report its own metadata
LLM_ERROR_MARKER = "در ارتباط با مدل مشکلی پیش آمد"


def _normalize_llm_result(raw) -> tuple[str, str, str | None]:
    """
    Accepts a plain str (current llm_client) or a dict / object exposing
    .text / .model_path / .model_name (future llm_client). Returns
    (text, model_path, model_name).
    """
    if isinstance(raw, str):
        text, path, name = raw, None, None
    elif isinstance(raw, dict):
        text = raw.get("text") or ""
        path = raw.get("model_path")
        name = raw.get("model_name")
    else:
        text = getattr(raw, "text", "") or ""
        path = getattr(raw, "model_path", None)
        name = getattr(raw, "model_name", None)

    if path not in ("primary", "fallback", "none", "error", "unknown"):
        # llm_client did not tell us; do NOT guess "primary"/"fallback" from prose.
        path = "error" if LLM_ERROR_MARKER in text else "unknown"

    return text, path, name


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
    debug_mode = settings.debug
    trace_id = str(uuid.uuid4())

    primary_model = settings.llm_model
    fallback_model = settings.llm_fallback_model
    final_fallback_model = settings.llm_final_fallback_model
    used_model_path = "none"
    used_model_name: str | None = None

    s = db.get(ChatSession, payload.session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    if s.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    domain_tag = classify_domain(payload.user_text)
    risk_tier = classify_risk(payload.user_text)

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

    memory_summary = None
    history_count = 0
    profile_context = None
    profile_fields_used: list[str] = []
    fallback_used = False

    if risk_tier == "severe":
        # Crisis path: never call the LLM, always the fixed safety template.
        assistant_text = CRISIS_FA
        used_model_path = "none"
    else:
        profile = db.query(Profile).filter(Profile.user_id == s.user_id).first()
        profile_parts = []
        if profile:
            for field in PROFILE_FIELDS:
                val = getattr(profile, field, None)
                if val not in (None, "", []):
                    profile_parts.append(f"{field}: {val}")
                    profile_fields_used.append(field)
        profile_context = "\n".join(profile_parts) if profile_parts else None

        rows = (
            db.query(Message)
            .filter(
                Message.session_id == s.id,
                Message.id != user_msg.id,
                Message.role.in_(["user", "assistant"]),
            )
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(HISTORY_LIMIT)
            .all()
        )
        rows = list(reversed(rows))
        history = [{"role": m.role, "content": m.content} for m in rows]
        history_count = len(history)

        memory_items = [
            {
                "role": m.role,
                "content": m.content,
                "risk_tier": m.risk_tier,
                "domain_tag": m.domain_tag,
            }
            for m in rows
        ]
        memory_summary = build_memory_summary(memory_items)

        raw_result = generate_reply_with_context(
            user_text=payload.user_text,
            profile_context=profile_context,
            history=history,
            memory_summary=memory_summary,
        )
        llm_text, used_model_path, used_model_name = _normalize_llm_result(raw_result)
        fallback_used = used_model_path == "fallback"

        if risk_tier == "moderate":
            assistant_text = f"{MODERATE_FA}\n\n{llm_text}"
        else:
            assistant_text = llm_text

    output_blocked = is_blocked_output(assistant_text)
    if output_blocked:
        assistant_text = BLOCKED_OUTPUT_FA

    assistant_msg = Message(
        session_id=s.id,
        role="assistant",
        content=assistant_text,
        domain_tag=domain_tag,
        risk_tier=risk_tier,
    )
    db.add(assistant_msg)

    s.risk_tier = max_risk(getattr(s, "risk_tier", None), risk_tier)

    db.commit()
    db.refresh(user_msg)
    db.refresh(assistant_msg)
    db.refresh(s)

    latency_ms = int((time.perf_counter() - started) * 1000)

    if debug_mode:
        ms_preview = None
        if memory_summary:
            ms_preview = (
                memory_summary
                if len(memory_summary) <= MEMORY_PREVIEW_CHARS
                else memory_summary[:MEMORY_PREVIEW_CHARS] + "..."
            )

        add_trace(
            {
                "trace_id": trace_id,
                "session_id": s.id,
                "user_id": current_user.id,
                "domain_tag": domain_tag,
                "risk_tier": risk_tier,
                "session_risk_tier": s.risk_tier,
                "history_count": history_count,
                "used_memory_summary": bool(memory_summary),
                "memory_summary_preview": ms_preview,
                "used_profile_context": bool(profile_context),
                "profile_fields_used": profile_fields_used,
                "retrieved_chunk_ids": [],  # filled in A6
                "primary_model": primary_model,
                "fallback_model": fallback_model,
                "final_fallback_model": final_fallback_model,
                "used_model_path": used_model_path,
                "used_model_name": used_model_name,
                "fallback_used": fallback_used,
                "output_blocked": output_blocked,
                "latency_ms": latency_ms,
            }
        )

        if memory_summary:
            print(
                f"[MEMORY DEBUG] session_id={s.id} history_count={history_count} "
                f"memory_summary={ms_preview}"
            )

    print(
        f"[CHAT_TURN] trace_id={trace_id} session_id={s.id} domain={domain_tag} "
        f"risk={risk_tier} session_risk={s.risk_tier} model_path={used_model_path} "
        f"fallback={fallback_used} blocked={output_blocked} latency_ms={latency_ms}"
    )

    return ChatTurnOut(
        user_message=MessageRead.model_validate(user_msg),
        assistant_message=MessageRead.model_validate(assistant_msg),
        trace_id=trace_id if debug_mode else None,
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


@router.get("/debug/traces", response_model=list[TraceItem])
def get_debug_traces(
    limit: int = Query(20, ge=1, le=200),
    current_user: User = Depends(get_current_user),
):
    if not settings.debug:
        raise HTTPException(status_code=404, detail="Not found")
    return list_traces(limit=limit, user_id=current_user.id)


@router.delete("/debug/traces")
def delete_debug_traces(current_user: User = Depends(get_current_user)):
    """Clears in-memory debug traces for the current user. Chat messages in
    PostgreSQL are NOT affected."""
    if not settings.debug:
        raise HTTPException(status_code=404, detail="Not found")
    clear_traces(user_id=current_user.id)
    return {"ok": True}