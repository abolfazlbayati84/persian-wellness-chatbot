import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.embeddings import embed_passage
from scripts.kb_seed_data import KB_SEED_DOCS


def main():
    print(f"[INGEST] Embedding {len(KB_SEED_DOCS)} seed documents (DB connection not opened yet)...")
    prepared = []
    for i, doc in enumerate(KB_SEED_DOCS, start=1):
        vector = embed_passage(doc["chunk_text"])
        prepared.append((doc, vector))
        print(f"  [embed {i}/{len(KB_SEED_DOCS)}] {doc['domain']} :: {doc['title']}")

    # Only open the DB connection now, right before we actually need it.
    # Neon's free tier suspends idle compute after a few minutes of
    # inactivity ("scales to zero"), so a connection opened before a long
    # operation (like the one-time model download) can die before we ever
    # get to use it. Opening late + writing immediately avoids that.
    from app.database.session import SessionLocal
    from app.models.kb_document import KBDocument

    db = SessionLocal()
    try:
        existing = db.query(KBDocument).count()
        if existing > 0:
            print(f"[INGEST] Found {existing} existing kb_documents rows. Clearing them (dev reset)...")
            db.query(KBDocument).delete()
            db.commit()

        print(f"[INGEST] Inserting {len(prepared)} documents with fixed IDs...")
        for i, (doc, vector) in enumerate(prepared, start=1):
            row = KBDocument(
                id=doc["id"],
                domain=doc["domain"],
                content_type=doc["content_type"],
                title=doc["title"],
                source=doc.get("source"),
                chunk_text=doc["chunk_text"],
                embedding=vector,
                review_status="clinician_approved",
            )
            db.add(row)
            print(f"  [insert {i}/{len(prepared)}] (id={doc['id']}) {doc['domain']} :: {doc['title']}")

        db.commit()

        # Reset Postgres sequence so future auto-generated IDs start after max ID
        from sqlalchemy import text
        try:
            db.execute(text("SELECT setval(pg_get_serial_sequence('kb_documents', 'id'), coalesce((SELECT max(id) FROM kb_documents), 0) + 1, false);"))
            db.commit()
        except Exception as seq_err:
            print(f"  [sequence reset note] {seq_err!r}")

        print("[INGEST] Done.")
    finally:
        db.close()


if __name__ == "__main__":
    main()