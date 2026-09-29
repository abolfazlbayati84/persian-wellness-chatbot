#!/usr/bin/env bash
set -e

echo "=== Persian Wellness Chatbot Container Startup ==="

# 1. Wait for PostgreSQL to be ready
echo "[1/4] Waiting for database connection..."
python - << 'EOF'
import time, os, sys
from sqlalchemy import create_engine, text

url = os.getenv("DATABASE_URL")
if not url:
    print("DATABASE_URL not set! Exiting.")
    sys.exit(1)

for attempt in range(1, 31):
    try:
        engine = create_engine(url, connect_args={"connect_timeout": 3})
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("  Database is reachable and ready.")
        sys.exit(0)
    except Exception as e:
        print(f"  Attempt {attempt}/30: waiting for DB... ({e!r})")
        time.sleep(2)

print("Database connection timed out after 60s!")
sys.exit(1)
EOF

# 2. Ensure pgvector extension exists
echo "[2/4] Ensuring pgvector extension exists..."
python - << 'EOF'
import os
from sqlalchemy import create_engine, text

url = os.getenv("DATABASE_URL")
engine = create_engine(url)
with engine.connect() as conn:
    conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
    conn.commit()
print("  pgvector extension confirmed.")
EOF

# 3. Run database migrations
echo "[3/4] Running Alembic migrations..."
alembic upgrade head

# 4. Ingest KB documents if not already seeded
echo "[4/4] Checking clinical knowledge base..."
set +e
python - << 'EOF'
import sys
from app.database.session import SessionLocal
from app.models.kb_document import KBDocument

db = SessionLocal()
try:
    count = db.query(KBDocument).count()
    if count >= 25:
        print(f"  Knowledge base already populated with {count} documents. Skipping ingestion.")
        sys.exit(0)
    else:
        print(f"  Knowledge base has only {count} documents. Triggering ingestion...")
        sys.exit(1)
finally:
    db.close()
EOF
KB_STATUS=$?
set -e

if [ $KB_STATUS -ne 0 ]; then
    python scripts/ingest_kb.py
fi

echo "=== Application initialized. Starting Uvicorn on port 8000 ==="
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
