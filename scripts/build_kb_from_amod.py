import sys
import time
import random
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database.session import SessionLocal
from app.models.kb_document import KBDocument
from app.services.embeddings import embed_passage
from app.services.kb_ingestion import adapt_source_to_kb_entries

SOURCE_LABEL = (
    "Adapted from Amod/mental_health_counseling_conversations (public, CC0). "
    "Machine-translated and rewritten by an LLM; NOT yet reviewed by a "
    "licensed clinician -- see review_status."
)

SAMPLE_SIZE = 250          # how many raw rows to process in this run
RANDOM_SEED = 42
SLEEP_BETWEEN_CALLS_S = 3.0  # be gentle with the free-tier rate limit


def load_raw_rows():
    from datasets import load_dataset
    ds = load_dataset("Amod/mental_health_counseling_conversations", split="train")
    rows = list(ds)
    random.Random(RANDOM_SEED).shuffle(rows)
    return rows[:SAMPLE_SIZE]


def main():
    print("Loading Amod/mental_health_counseling_conversations from Hugging Face...")
    rows = load_raw_rows()
    print(
        f"Processing {len(rows)} sampled rows (this will take a while; "
        f"~{SLEEP_BETWEEN_CALLS_S}s+ per row due to rate limiting).\n"
    )

    db = SessionLocal()
    inserted = 0
    skipped = 0
    errored = 0

    try:
        for i, row in enumerate(rows, start=1):
            context = (row.get("Context") or "").strip()
            response = (row.get("Response") or "").strip()
            if not context or not response:
                skipped += 1
                continue

            raw_text = f"Question: {context}\n\nCounselor's answer: {response}"

            try:
                entries = adapt_source_to_kb_entries(raw_text)
            except Exception as e:
                print(f"[{i}/{len(rows)}] ERROR: {e!r}")
                errored += 1
                time.sleep(SLEEP_BETWEEN_CALLS_S)
                continue

            if not entries:
                print(f"[{i}/{len(rows)}] skip (not usable / off-domain)")
                skipped += 1
            else:
                for e in entries:
                    vector = embed_passage(e["content"])
                    db.add(
                        KBDocument(
                            domain=e["domain"],
                            content_type="psychoeducation",
                            title=e["title"],
                            source=SOURCE_LABEL,
                            chunk_text=e["content"],
                            embedding=vector,
                            review_status="draft",
                        )
                    )
                    inserted += 1
                db.commit()
                titles = ", ".join(e["title"] for e in entries)
                print(f"[{i}/{len(rows)}] +{len(entries)} entr(y/ies): {titles}")

            time.sleep(SLEEP_BETWEEN_CALLS_S)

    finally:
        db.close()

    print(
        f"\nDone. inserted={inserted} kb_documents, "
        f"skipped={skipped} rows, errors={errored} rows "
        f"(out of {len(rows)} sampled)."
    )


if __name__ == "__main__":
    main()