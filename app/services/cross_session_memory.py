from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.embeddings import embed_query

DEFAULT_TOP_K = 5
# Empirically found unreliable as a final filter: an unrelated message and
# a genuinely relevant one were observed only 0.01 apart (0.1607 vs 0.15).
# This is now just a first-pass net to bound candidates before an LLM-based
# relevance judgment (see llm_client.filter_relevant_past_messages) makes
# the real decision -- kept generous on purpose.
DEFAULT_MAX_DISTANCE = 0.35


def search_past_messages(
    db: Session,
    user_id: int,
    current_session_id: int,
    query_text: str,
    top_k: int = DEFAULT_TOP_K,
    max_distance: float = DEFAULT_MAX_DISTANCE,
    debug_mode: bool = False,
) -> list[dict]:
    """Semantic search over this user's OWN past messages, excluding the
    current session (already in working memory). Lets the assistant recall
    something relevant the user said in an earlier session, only when it's
    genuinely close in meaning to the current message."""
    vector = embed_query(query_text)
    vector_literal = "[" + ",".join(str(x) for x in vector) + "]"

    sql = """
        SELECT m.id, m.content, m.session_id, (m.embedding <=> :qvec) AS distance
        FROM messages m
        JOIN sessions s ON s.id = m.session_id
        WHERE s.user_id = :user_id
          AND m.session_id != :current_session_id
          AND m.role = 'user'
          AND m.embedding IS NOT NULL
        ORDER BY m.embedding <=> :qvec ASC
        LIMIT :k
    """
    rows = db.execute(
        text(sql),
        {
            "qvec": vector_literal,
            "user_id": user_id,
            "current_session_id": current_session_id,
            "k": top_k,
        },
    ).fetchall()

    if debug_mode and rows:
        dists = [round(float(r.distance), 4) for r in rows]
        print(f"[CROSS_SESSION DEBUG] query={query_text!r} distances={dists}")

    return [
        {"id": r.id, "content": r.content, "session_id": r.session_id, "distance": float(r.distance)}
        for r in rows
        if r.distance <= max_distance
    ]