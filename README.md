# Persian Mental Wellness Chatbot (همیار آرام)

An intelligent, interactive Persian mental wellness assistant designed around Cognitive Behavioral Therapy (**CBT**), Acceptance and Commitment Therapy (**ACT**), and Dialectical Behavior Therapy (**DBT**) principles. The system integrates clinical knowledge retrieval (Domain-Filtered Dense RAG), structured multi-step decision trees, cross-session adaptive memory, and a multi-tier crisis safety triage engine.

---

## Key System Capabilities

### 1. Multi-Tier Risk Triage & Crisis Safety
- **Severe Crisis (Deterministic Bypass):** Any self-harm or suicidal disclosure immediately bypasses generative LLM inference and active decision trees. The system returns an immediate emergency intervention message providing official Iranian crisis hotlines:
  - **1480:** Voice of Counseling (صدای مشاور بهزیستی)
  - **123:** Social Emergency Services (اورژانس اجتماعی)
  - **115:** Medical Emergency (اورژانس پزشکی)
- **Moderate & Low Triage:** Automatically adapts tone, prioritizes somatic grounding, and provides supportive escalation guidance without triggering false-positive crisis blocks.
- **Harmful Output Guardrails:** Evaluates assistant output using regex patterns to block accidental mentions of suicide methods, lethal dosage, or self-harm instructions.

### 2. Structured Clinical Decision Trees
Includes 5 structured, multi-step conversation graphs (55 structured nodes) covering common psychological presentations:
- **Stress & Somatic Anxiety** (`stress_anxiety.json`)
- **Depression, Inertia & Motivation** (`depression_motivation.json`)
- **Relationships & Interpersonal Conflict** (`relationships_social.json`)
- **Time Management & Academic Procrastination** (`time_management_study.json`)
- **Self-Esteem & Inner Critic** (`self_esteem.json`)

**Features:**
- Step-by-step assessment questions.
- Dynamic branch classification via LLM (`classify_branch`).
- Graceful handling of ambiguous responses (`clarify=True` with abandonment fallback after repeated ambiguity).
- Intervention delivery via leaf nodes referencing structured therapeutic techniques.
- Post-intervention check-ins and alternative branch fallback.

### 3. Clinical Knowledge Base & Vector Retrieval (Domain-Filtered RAG)
- **Curated Knowledge Base:** 25 structured clinical technique documents (maintained in draft review status).
- **Offline Dense Embeddings:** Local embeddings powered by `intfloat/multilingual-e5-base` with appropriate `passage: ` and `query: ` prefixes for dense retrieval without external API rate limits.
- **Vector Storage:** PostgreSQL equipped with the `pgvector` extension.
- **Domain-Filtered Semantic Search:** Queries are mapped to their respective therapeutic domain to reduce cross-topic interference.

### 4. Cross-Session Memory & Adaptive Profile
- **Session Summaries:** Synchronous summarization of conversation history upon switching sessions or starting a new chat (gated by user privacy consent).
- **Rolling Clinical Profile:** Consolidates historical user themes, agreed action steps, and emotional trajectories into a compact, fixed-size (~150 words) Persian summary.
- **In-Context Continuity:** Seamlessly recalls relevant past discussions when returning to the chatbot.

### 5. Responsive, Clean Web Interface
- **Fixed Sidebar:** Chat history list and new conversation controls stay permanently pinned.
- **Isolated Scroll Viewport:** Messages scroll independently with an automatic floating "Scroll to bottom" helper button.
- **Privacy-First Display:** Timestamps and clock indicators removed from messages and conversation lists.
- **Wellness Toolkit Drawer:** Off-canvas slideout panel featuring mood logging and grounding affirmations.
- **RTL Support:** Full Persian typography using the Vazirmatn font.

---

## Project Architecture

```text
persian-wellness-chatbot/
├── app/
│   ├── api/                  # FastAPI REST routes and endpoint handlers
│   ├── core/                 # Configuration, JWT authentication, and password hashing
│   ├── database/             # SQLAlchemy engine and session factory
│   ├── decision_trees/       # 5 JSON clinical decision trees (55 nodes total)
│   ├── models/               # SQLAlchemy ORM models (User, Session, Message, KB, etc.)
│   ├── schemas/              # Pydantic v2 validation models
│   ├── services/             # Core engines (LLM cascade, RAG, classifier, tree executor)
│   ├── static/               # Single-page frontend application (HTML/CSS/JS)
│   └── main.py               # FastAPI application entrypoint and middleware
├── alembic/                  # Database migration scripts
├── scripts/                  # Diagnostic, ingestion, and evaluation scripts
├── Dockerfile                # Production container definition
├── docker-compose.yml        # Multi-container orchestration (App + PostgreSQL with pgvector)
├── docker-entrypoint.sh      # Automated startup script (DB wait, migrations, KB seeding)
├── .dockerignore             # Excluded files during container build
├── requirements.txt          # Python project dependencies (UTF-8)
├── .env.example              # Sample environment variable template
└── README.md                 # Complete system documentation
```

---

## Quickstart Guide

### Method A: Docker Compose (Recommended for Any Laptop / Server)

With Docker, you do not need to manually install Python, PostgreSQL, or `pgvector`. Everything runs in isolated containers with a single command.

#### 1. Clone the repository and configure environment:
```bash
cp .env.example .env
```
Open `.env` and set your LLM credentials:
```env
# Google Gemini Configuration
LLM_PROVIDER=google
GOOGLE_API_KEY=your_actual_google_api_key_here
GOOGLE_MODEL=gemini-flash-lite-latest
GOOGLE_FALLBACK_MODEL=gemini-2.5-flash

# JWT Secret Key
SECRET_KEY=your_super_secret_random_key_here
```

#### 2. Start the application:
```bash
docker compose up --build
```

**What happens automatically on startup:**
1. Spawns `wellness_db` (`pgvector/pgvector:pg16`) with persistent data volume `pgdata`.
2. Verifies database connectivity and confirms the `pgvector` extension.
3. Automatically runs all database migrations (`alembic upgrade head`).
4. Automatically checks and seeds the 25 clinical knowledge base documents and computes vector embeddings.
5. Caches the embedding model in a Docker volume (`hf_cache`) so it downloads only once.
6. Launches Uvicorn on port `8000`.

#### 3. Access the application:
- **Web Chat Application:** [http://localhost:8000/app/](http://localhost:8000/app/)
- **Interactive Swagger Documentation:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc API Documentation:** [http://localhost:8000/redoc](http://localhost:8000/redoc)

#### 4. Run evaluation suites inside the container:
```bash
# Evaluate Knowledge Base RAG Retrieval Routing (6 handcrafted test cases)
docker compose exec web python scripts/eval_kb_retrieval.py

# Evaluate Domain & Crisis Risk Classification (29 handcrafted test cases)
docker compose exec web python scripts/eval_classifiers.py
```

#### 5. Stop the application:
```bash
docker compose down
```
*(To stop and erase database volumes, use `docker compose down -v`)*

---

### Method B: Manual Local Setup (Without Docker)

#### 1. Prerequisites
- **Python 3.11+**
- **PostgreSQL 15+** with the **pgvector** extension installed.

#### 2. Virtual Environment Setup
```bash
# Create virtual environment
python -m venv .venv

# Activate on Windows
.\.venv\Scripts\activate

# Activate on Linux/macOS
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

#### 3. Environment Configuration
Create a `.env` file in the project root based on `.env.example`:
```env
DATABASE_URL=postgresql+psycopg://username:password@localhost:5432/wellness_db
DEBUG=false

# LLM Provider Configuration ('google' or 'openrouter')
LLM_PROVIDER=google
GOOGLE_API_KEY=your_gemini_api_key_here
GOOGLE_MODEL=gemini-flash-lite-latest
GOOGLE_FALLBACK_MODEL=gemini-2.5-flash

# JWT Security
SECRET_KEY=your_super_secret_random_key_here
ACCESS_TOKEN_EXPIRE_MINUTES=1440
```

#### 4. Database Migration & Knowledge Base Ingestion
```bash
# Run database schema migrations
alembic upgrade head

# Ingest clinical knowledge base documents and compute dense embeddings
python scripts/ingest_kb.py
```

#### 5. Running the Application Server
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## Evaluation & Diagnostic Scripts

The repository includes dedicated evaluation suites to verify system behavior:

```bash
# 1. Evaluate Knowledge Base RAG Retrieval Routing (6 handcrafted test cases)
python scripts/eval_kb_retrieval.py

# 2. Evaluate Domain & Crisis Risk Classification (29 handcrafted test cases)
python scripts/eval_classifiers.py

# 3. Multi-Tier Crisis Safety & Harmful Output Blocking (C-SSRS- & ToxiGen-inspired)
python scripts/bench_safety_probes.py

# 4. Persian Sentiment & Domain Routing Alignment (SentiPers- & ParsiNLU-style probes)
python scripts/bench_sentitpers_alignment.py

# 5. MTEB-Style Embedding Quality & Semantic Textual Similarity (multilingual-e5-base)
python scripts/bench_mteb_embedding.py

# 6. Test PostgreSQL Database Connectivity
python scripts/test_db.py

# 7. Verify Google Gemini API Integration and Persian Output
python scripts/test_google_chat.py
```

### Benchmark Evaluation Suites

The repository includes curated evaluation suites evaluated against handcrafted test probes:
- **Crisis Safety Triage (`bench_safety_probes.py`):** Evaluates severe risk recall (C-SSRS-inspired criteria), ERDE-5 single-turn proxy, and ToxiGen-style simulated output instruction blocking (`is_blocked_output`).
- **Domain & Sentiment Alignment (`bench_sentitpers_alignment.py`):** Evaluates negative-to-wellness routing against SentiPers-style sentiment probes and multi-domain classification against handcrafted ParsiNLU-style domain probes.
- **MTEB-Style Embedding Quality (`bench_mteb_embedding.py`):** Tests Semantic Textual Similarity (STS Spearman rho) and domain clustering separation on Persian clinical texts using `intfloat/multilingual-e5-base`.

---

## Ethical Principles & Clinical Disclaimers

1. **Non-Diagnostic:** This chatbot is an educational self-help companion rooted in established CBT, ACT, and DBT exercises. It does not provide medical diagnoses, psychiatric evaluations, or pharmaceutical prescriptions.
2. **Mandatory Crisis Escalation:** The platform is not an emergency response provider. Users presenting severe distress or self-harm intent are immediately escalated to accredited human emergency services (1480, 123, 115).
3. **Data Confidentiality:** User session histories and clinical summaries are partitioned per authenticated account (prototype storage, unencrypted at rest).
