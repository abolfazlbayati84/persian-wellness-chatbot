from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.embeddings import embed_query
from app.models.kb_document import KBDocument

# Maps app/services/classifiers.py's DomainTag values to the domain labels
# used in kb_documents.domain (see scripts/kb_seed_data.py). These two
# taxonomies were built independently and don't share exact strings --
# this table is the single place that bridges them.
#
# "relationships_social" and "time_management_study" currently have no
# classify_domain() trigger at all, so messages about relationships or
# study/procrastination can't reach those KB domains via filtering yet --
# they still fall back to the unfiltered search below. Expanding
# classify_domain's keywords for those two topics is a good follow-up.
CLASSIFIER_TO_KB_DOMAIN = {
    "anxiety": "stress_anxiety",
    "stress": "stress_anxiety",
    "sleep": "stress_anxiety",   # closest existing KB domain for now
    "depression": "depression_motivation",
    "burnout": "depression_motivation",
    "relationships": "relationships_social",
    "self_esteem": "self_esteem",
    "study": "time_management_study",
    "other": None,
}
# TEMPORARY: "draft" is included only because the current seed KB
# (scripts/kb_seed_data.py) is placeholder content pending clinical
# review. Remove "draft" from this tuple before any real user sees
# production traffic -- see the design doc, section 7.4.
ALLOWED_REVIEW_STATUSES = ("draft", "clinician_approved")

DEFAULT_TOP_K = 3

# Real measured data (Sep 2026, 10-doc seed KB, multilingual-e5-base):
#   irrelevant query ("امروز هوا چطوره؟")      -> closest distance 0.2029
#   relevant query ("...به دوستم بگم ناراحتم") -> closest distance 0.1834
# These two ranges overlap almost completely, so distance alone cannot
# reliably separate "on topic" from "off topic" at this KB size. This
# cutoff is now intentionally strict: it's a safety net for near-duplicate
# phrasing only. The real classification work happens in classify_domain()
# -- expand its keyword lists (not this number) when a topic isn't being
# recognized.
DEFAULT_MAX_DISTANCE = 0.18

def _run_query(db: Session, vector_literal: str, domain: str | None, top_k: int, max_distance: float):
    status_placeholders = ", ".join(f":status_{i}" for i in range(len(ALLOWED_REVIEW_STATUSES)))
    params = {"qvec": vector_literal, "k": top_k, "max_dist": max_distance}
    for i, s in enumerate(ALLOWED_REVIEW_STATUSES):
        params[f"status_{i}"] = s

    sql = f"""
        SELECT id, domain, title, chunk_text, (embedding <=> :qvec) AS distance
        FROM kb_documents
        WHERE review_status IN ({status_placeholders})
          AND (embedding <=> :qvec) <= :max_dist
    """
    if domain:
        sql += " AND domain = :domain"
        params["domain"] = domain

    sql += " ORDER BY embedding <=> :qvec ASC LIMIT :k"

    return db.execute(text(sql), params).fetchall()


def retrieve_relevant_chunks(
    db: Session,
    query_text: str,
    classifier_domain: str | None,
    top_k: int = DEFAULT_TOP_K,
    max_distance: float = DEFAULT_MAX_DISTANCE,
) -> list[dict]:
    vector = embed_query(query_text)
    vector_literal = "[" + ",".join(str(x) for x in vector) + "]"

    kb_domain = CLASSIFIER_TO_KB_DOMAIN.get(classifier_domain or "other")

    rows = []
    if kb_domain:
        # Trust the domain classifier: once we know the topic, don't apply
        # the generic distance cutoff -- with a small, curated per-domain KB,
        # the closest chunk(s) in the right domain are worth surfacing even
        # if their raw cosine distance is a bit above our default threshold.
        # 2.0 is effectively "no cutoff" (cosine distance maxes out at 2.0).
        rows = _run_query(db, vector_literal, kb_domain, top_k, max_distance=2.0)

    if not rows:
        # No domain signal at all (classifier said "other"/unmapped) -- here
        # we DO apply the real distance cutoff, since an unfiltered
        # cross-domain search should only surface something if it's
        # genuinely close, not just "closest of whatever exists".
        rows = _run_query(db, vector_literal, None, top_k, max_distance)
        if rows:
            dists = [round(float(r.distance), 4) for r in rows]
            titles = [r.title for r in rows]
            print(
                f"[KB DEBUG] unfiltered-fallback match (classifier_domain={classifier_domain!r}, "
                f"query={query_text!r}): distances={dists} titles={titles}"
            )

    return [
        {
            "id": r.id,
            "domain": r.domain,
            "title": r.title,
            "chunk_text": r.chunk_text,
            "distance": float(r.distance),
        }
        for r in rows
    ]

def get_documents_by_ids(db: Session, ids: list[int]) -> list[dict]:
    """Fetch specific KB documents by id, in the given order -- used by the
    decision-tree engine to pull an exact, pre-approved technique instead
    of doing a semantic search."""
    if not ids:
        return []
    rows = db.query(KBDocument).filter(KBDocument.id.in_(ids)).all()
    by_id = {r.id: r for r in rows}
    ordered = [by_id[i] for i in ids if i in by_id]
    return [
        {"id": r.id, "domain": r.domain, "title": r.title, "chunk_text": r.chunk_text}
        for r in ordered
    ]