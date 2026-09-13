import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database.session import SessionLocal
from app.services.kb_retrieval import retrieve_relevant_chunks
from app.services.classifiers import classify_domain

# (user_message, expected_kb_domain_or_None)
EVAL_CASES = [
    ("این روزا خیلی مضطربم و قلبم تند می‌زنه", "stress_anxiety"),
    ("اصلا انگیزه ندارم درسمو بخونم", "depression_motivation"),
    ("نمی‌دونم چطور به دوستم بگم ناراحتم", "relationships_social"),
    ("اصلا اعتماد به نفس ندارم", "self_esteem"),
    ("همش تعلل می‌کنم و درسمو نمی‌خونم", "time_management_study"),
    ("امروز هوا چطوره؟", None),
]


def main():
    db = SessionLocal()
    passed, failed = 0, []
    try:
        for text, expected_domain in EVAL_CASES:
            classifier_domain = classify_domain(text)
            chunks = retrieve_relevant_chunks(db, text, classifier_domain)
            retrieved_domains = {c["domain"] for c in chunks}

            if expected_domain is None:
                ok = len(chunks) == 0
                print(f"[{'PASS' if ok else 'FAIL'}] \"{text}\" -> expected NO retrieval, got {retrieved_domains or 'none'}")
            else:
                ok = retrieved_domains == {expected_domain}
                print(f"[{'PASS' if ok else 'FAIL'}] \"{text}\" -> expected only {expected_domain}, got {retrieved_domains or 'none'}")

            (passed := passed + 1) if ok else failed.append((text, expected_domain, retrieved_domains))
    finally:
        db.close()

    print(f"\n{passed}/{len(EVAL_CASES)} passed.")
    if failed:
        print("\n❌ Failures:")
        for text, expected, actual in failed:
            print(f"   - \"{text}\" -> expected {expected}, got {actual}")
    else:
        print("\n✅ ALL RETRIEVAL EVAL CASES PASSED")


if __name__ == "__main__":
    main()