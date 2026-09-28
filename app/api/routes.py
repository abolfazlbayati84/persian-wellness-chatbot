import time
import uuid
from datetime import datetime

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
from app.models.risk_event import RiskEvent
from app.models.episodic_summary import EpisodicSummary
from app.models.tree_progress import TreeProgress

from app.schemas.user import UserCreate, UserRead
from app.schemas.profile import ProfileUpsert, ProfileRead
from app.schemas.session import SessionCreate, SessionRead, SessionMessagesOut, SessionListItem
from app.schemas.chat import ChatTurnIn, ChatTurnOut, MessageRead, TraceItem
from app.schemas.risk_event import RiskEventRead, RiskEventReviewIn
from app.schemas.auth import LoginIn, TokenOut

from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
)

from app.services.llm_client import (
    generate_reply_with_context,
    update_user_memory_summary,
    filter_relevant_past_messages,
)
from app.services.cross_session_memory import search_past_messages
from app.services.embeddings import embed_passage
from app.services.classifiers import classify_domain, classify_risk, max_risk, is_blocked_output
from app.services.llm_classifier import classify_message
from app.services.safety_templates import CRISIS_FA, MODERATE_FA, BLOCKED_OUTPUT_FA
from app.services.memory_service import build_memory_summary
from app.services.kb_retrieval import retrieve_relevant_chunks, CLASSIFIER_TO_KB_DOMAIN
from app.services.decision_tree import get_tree, get_node, classify_branch, run_tree_node
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

    if path not in ("primary", "fallback", "final_fallback", "none", "error", "unknown"):
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


@router.get("/sessions", response_model=list[SessionListItem])
def list_my_sessions(
    limit: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sessions = (
        db.query(ChatSession)
        .filter(ChatSession.user_id == current_user.id)
        .order_by(ChatSession.started_at.desc())
        .limit(limit)
        .all()
    )
    items = []
    for s in sessions:
        first_msg = (
            db.query(Message)
            .filter(Message.session_id == s.id, Message.role == "user")
            .order_by(Message.created_at.asc())
            .first()
        )
        count = db.query(Message).filter(Message.session_id == s.id).count()
        items.append(
            SessionListItem(
                id=s.id,
                started_at=s.started_at,
                ended_at=s.ended_at,
                risk_tier=s.risk_tier,
                preview=(first_msg.content[:60] if first_msg else None),
                domain_tag=(first_msg.domain_tag if first_msg else None),
                message_count=count,
            )
        )
    return items


@router.post("/sessions/{session_id}/end", response_model=SessionRead)
def end_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    s = db.get(ChatSession, session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    if s.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    if s.ended_at is not None:
        raise HTTPException(status_code=400, detail="Session already ended")

    rows = (
        db.query(Message)
        .filter(Message.session_id == s.id, Message.role.in_(["user", "assistant"]))
        .order_by(Message.created_at.asc(), Message.id.asc())
        .all()
    )

    if rows:
        transcript = "\n".join(f"{m.role}: {m.content}" for m in rows)
        existing = db.query(EpisodicSummary).filter(EpisodicSummary.user_id == current_user.id).first()

        result = update_user_memory_summary(
            existing.summary_text if existing else None,
            transcript,
        )
        summary_text = (result.get("text") or "").strip()

        if summary_text and not summary_text.startswith("متأسفم"):
            if existing:
                existing.summary_text = summary_text
                existing.session_id = s.id
            else:
                db.add(
                    EpisodicSummary(
                        user_id=current_user.id,
                        session_id=s.id,
                        summary_text=summary_text,
                    )
                )

    s.ended_at = datetime.utcnow()
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

    # Two independent classifiers, combined for safety:
    # - keyword-based (classifiers.py): fast, deterministic, no network
    #   dependency -- a safety backstop that always runs.
    # - LLM-based (llm_classifier.py): understands meaning/nuance/idiom,
    #   catches cases keyword matching misses.
    # Risk: take the HIGHER of the two (never let the LLM's judgment
    # lower a keyword-detected risk, and vice versa -- recall over
    # precision for safety, per design doc 9.2).
    # Domain: trust the LLM when it commits to a specific domain; fall
    # back to the keyword result only if the LLM said "other" (e.g. on
    # a parse failure or genuine ambiguity).
    kw_domain = classify_domain(payload.user_text)
    kw_risk = classify_risk(payload.user_text)
    llm_class = classify_message(payload.user_text)

    raw_domain_tag = llm_class["domain"] if llm_class["domain"] != "other" else kw_domain
    domain_tag = raw_domain_tag
    risk_tier = max_risk(kw_risk, llm_class["risk"])

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
        embedding=embed_passage(payload.user_text),
    )
    db.add(user_msg)
    db.flush()

    if risk_tier in ("moderate", "severe"):
        db.add(
            RiskEvent(
                user_id=current_user.id,
                session_id=s.id,
                message_id=user_msg.id,
                risk_tier=risk_tier,
                domain_tag=domain_tag,
                user_text_snapshot=payload.user_text,
            )
        )

    memory_summary = None
    history_count = 0
    profile_context = None
    profile_fields_used: list[str] = []
    fallback_used = False
    retrieved_chunk_ids: list[int] = []
    tree_node_used: str | None = None

    if risk_tier == "severe":
        assistant_text = CRISIS_FA
        used_model_path = "none"

        active_tree = (
            db.query(TreeProgress)
            .filter(TreeProgress.session_id == s.id, TreeProgress.status == "active")
            .first()
        )
        if active_tree:
            active_tree.status = "abandoned"

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
            {"role": m.role, "content": m.content, "risk_tier": m.risk_tier, "domain_tag": m.domain_tag}
            for m in rows
        ]
        memory_summary = build_memory_summary(memory_items)

        user_profile_summary = (
            db.query(EpisodicSummary).filter(EpisodicSummary.user_id == s.user_id).first()
        )
        if user_profile_summary:
            long_term_text = f"[شناخت کلی از این کاربر] {user_profile_summary.summary_text}"
            memory_summary = f"{long_term_text}\n\n{memory_summary}" if memory_summary else long_term_text

        tree_handled = False

        # Safety override: an active tree never survives into a moderate turn.
        if risk_tier == "moderate":
            active_tree = (
                db.query(TreeProgress)
                .filter(TreeProgress.session_id == s.id, TreeProgress.status == "active")
                .first()
            )
            if active_tree:
                active_tree.status = "abandoned"

        if risk_tier in ("none", "low"):
            active_tree = (
                db.query(TreeProgress)
                .filter(TreeProgress.session_id == s.id, TreeProgress.status == "active")
                .first()
            )

            tree_def = get_tree(active_tree.domain) if active_tree else None
            if active_tree and tree_def is None:
                active_tree.status = "abandoned"
                active_tree = None

            if not active_tree:
                mapped_tree_domain = CLASSIFIER_TO_KB_DOMAIN.get(raw_domain_tag)
                candidate_tree = get_tree(mapped_tree_domain) if mapped_tree_domain else None
                if candidate_tree:
                    active_tree = TreeProgress(
                        session_id=s.id,
                        user_id=s.user_id,
                        domain=mapped_tree_domain,
                        current_node_id=candidate_tree["root"],
                        status="active",
                        unclear_count=0,
                        visited_nodes=[],
                    )
                    db.add(active_tree)
                    db.flush()
                    tree_def = candidate_tree

                    raw_result, resting_node_id, technique_ids_used = run_tree_node(
                        active_tree.current_node_id, tree_def, db,
                        payload.user_text, profile_context, history, memory_summary,
                    )
                    llm_text, used_model_path, used_model_name = _normalize_llm_result(raw_result)
                    assistant_text = llm_text
                    active_tree.current_node_id = resting_node_id
                    tree_node_used = resting_node_id
                    retrieved_chunk_ids = technique_ids_used
                    if get_node(tree_def, resting_node_id)["type"] == "end":
                        active_tree.status = "completed"
                    tree_handled = True

            if active_tree and tree_def and not tree_handled:
                current_node = get_node(tree_def, active_tree.current_node_id)
                if current_node.get("type") == "question":
                    branch_keys = list(current_node["branches"].keys())
                    branch = classify_branch(current_node["prompt_to_user"], payload.user_text, branch_keys)

                    if branch == "unclear":
                        active_tree.unclear_count += 1
                        max_unclear = tree_def.get("max_unclear_before_abandon", 2)
                        if active_tree.unclear_count >= max_unclear:
                            active_tree.status = "abandoned"
                        else:
                            raw_result, resting_node_id, technique_ids_used = run_tree_node(
                                active_tree.current_node_id, tree_def, db,
                                payload.user_text, profile_context, history, memory_summary,
                                clarify=True,
                            )
                            llm_text, used_model_path, used_model_name = _normalize_llm_result(raw_result)
                            assistant_text = llm_text
                            tree_node_used = resting_node_id
                            retrieved_chunk_ids = technique_ids_used
                            tree_handled = True
                    else:
                        active_tree.unclear_count = 0
                        active_tree.visited_nodes = (active_tree.visited_nodes or []) + [
                            {"node": active_tree.current_node_id, "branch": branch}
                        ]
                        next_node_id = current_node["branches"][branch]
                        raw_result, resting_node_id, technique_ids_used = run_tree_node(
                            next_node_id, tree_def, db,
                            payload.user_text, profile_context, history, memory_summary,
                        )
                        llm_text, used_model_path, used_model_name = _normalize_llm_result(raw_result)
                        assistant_text = llm_text
                        active_tree.current_node_id = resting_node_id
                        tree_node_used = resting_node_id
                        retrieved_chunk_ids = technique_ids_used
                        if get_node(tree_def, resting_node_id)["type"] == "end":
                            active_tree.status = "completed"
                        tree_handled = True
                else:
                    active_tree.status = "abandoned"

        if not tree_handled:
            retrieved_chunks = retrieve_relevant_chunks(db, payload.user_text, raw_domain_tag)
            retrieved_chunk_ids = [c["id"] for c in retrieved_chunks]
            kb_context = (
                "\n\n".join(f"[{c['title']}] {c['chunk_text']}" for c in retrieved_chunks)
                if retrieved_chunks else None
            )

            candidate_past_messages = search_past_messages(
                db, s.user_id, s.id, payload.user_text, debug_mode=debug_mode,
            )
            relevant_past_messages = filter_relevant_past_messages(
                payload.user_text, candidate_past_messages,
            )
            if debug_mode and candidate_past_messages:
                kept_ids = {m["id"] for m in relevant_past_messages}
                print(
                    f"[CROSS_SESSION DEBUG] {len(candidate_past_messages)} candidate(s), "
                    f"LLM kept {len(relevant_past_messages)}: ids={sorted(kept_ids)}"
                )
            cross_session_context = (
                "\n".join(f"- {m['content']}" for m in relevant_past_messages)
                if relevant_past_messages else None
            )

            raw_result = generate_reply_with_context(
                user_text=payload.user_text,
                profile_context=profile_context,
                history=history,
                memory_summary=memory_summary,
                kb_context=kb_context,
                cross_session_context=cross_session_context,
            )
            llm_text, used_model_path, used_model_name = _normalize_llm_result(raw_result)
            fallback_used = used_model_path in ("fallback", "final_fallback")

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
                memory_summary if len(memory_summary) <= MEMORY_PREVIEW_CHARS
                else memory_summary[:MEMORY_PREVIEW_CHARS] + "..."
            )

        add_trace(
            {
                "trace_id": trace_id,
                "session_id": s.id,
                "user_id": current_user.id,
                "user_text_preview": payload.user_text[:120],
                "domain_tag": domain_tag,
                "risk_tier": risk_tier,
                "session_risk_tier": s.risk_tier,
                "history_count": history_count,
                "used_memory_summary": bool(memory_summary),
                "memory_summary_preview": ms_preview,
                "used_profile_context": bool(profile_context),
                "profile_fields_used": profile_fields_used,
                "retrieved_chunk_ids": retrieved_chunk_ids,
                "tree_node_used": tree_node_used,
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
            print(f"[MEMORY DEBUG] session_id={s.id} history_count={history_count} memory_summary={ms_preview}")

    print(
        f"[CHAT_TURN] trace_id={trace_id} session_id={s.id} domain={domain_tag} "
        f"risk={risk_tier} session_risk={s.risk_tier} model_path={used_model_path} "
        f"tree_node={tree_node_used} fallback={fallback_used} blocked={output_blocked} "
        f"latency_ms={latency_ms}"
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


def get_current_admin_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


@router.get("/admin/risk-events", response_model=list[RiskEventRead])
def list_risk_events(
    status: str | None = Query(None, description="Filter by status: pending | reviewed | dismissed"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    q = db.query(RiskEvent)
    if status:
        q = q.filter(RiskEvent.status == status)
    rows = (
        q.order_by(RiskEvent.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return rows


@router.patch("/admin/risk-events/{risk_event_id}", response_model=RiskEventRead)
def review_risk_event(
    risk_event_id: int,
    payload: RiskEventReviewIn,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    event = db.get(RiskEvent, risk_event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Risk event not found")

    event.status = payload.status
    event.reviewer_note = payload.reviewer_note
    event.reviewed_by_user_id = admin.id
    event.reviewed_at = datetime.utcnow()

    db.commit()
    db.refresh(event)
    return event