import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from app.database.session import SessionLocal
from app.services.embeddings import embed_query

TEST_QUERIES = [
    ("این روزا خیلی مضطربم و قلبم تند می‌زنه", None),
    ("اصلا انگیزه ندارم درسمو بخونم", None),
    ("نمی‌دونم چطور به دوستم بگم ناراحتم", "relationships_social"),
]


def search(db, query_text: str, domain: str | None, top_k: int = 3):
    vector = embed_query(query_text)
    vector_literal = "[" + ",".join(str(x) for x in vector) + "]"

    sql = """
        SELECT id, domain, title, chunk_text, (embedding <=> :qvec) AS distance
        FROM kb_documents
    """
    params = {"qvec": vector_literal}

    if domain:
        sql += " WHERE domain = :domain"
        params["domain"] = domain

    sql += " ORDER BY embedding <=> :qvec ASC LIMIT :k"
    params["k"] = top_k

    rows = db.execute(text(sql), params).fetchall()
    return rows


def main():
    db = SessionLocal()
    try:
        for query_text, domain in TEST_QUERIES:
            print("=" * 70)
            print(f"QUERY: {query_text}" + (f"  (domain filter: {domain})" if domain else ""))
            print("=" * 70)
            rows = search(db, query_text, domain)
            for r in rows:
                print(f"  [dist={r.distance:.4f}] ({r.domain}) {r.title}")
                print(f"      {r.chunk_text[:90]}...")
            print()
    finally:
        db.close()


if __name__ == "__main__":
    main()