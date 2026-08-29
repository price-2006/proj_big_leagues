# AI Resume–Job Matching & Optimization System

An end-to-end system that parses resumes and job descriptions, extracts structured candidate/job profiles, uses transformer-based embeddings for semantic matching, combines those signals with engineered features into a transparent match score, and trains a ranking model to compare it against. An evidence-constrained LLM layer explains results and suggests resume improvements — it never invents a score, a skill, or an achievement.

**Status: architecture and roadmap phase.** No application code exists yet. See `docs/` for the full design; implementation proceeds phase by phase per `docs/ROADMAP.md`.

## Why this exists

This is explicitly *not* `resume → LLM → "your score is 82%"`. The match score is produced by a hybrid pipeline — NLP extraction, skill taxonomy normalization, embedding-based semantic similarity, engineered features, and a rule-based baseline compared against a trained ML ranking model. The LLM is confined to the explanation/recommendation layer, reading only what the deterministic pipeline already computed, with every claim it makes validated against actual extracted evidence before being shown to a user. Full rationale in `docs/ARCHITECTURE.md` §1.

## Documentation

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — component diagram, technology choices and why, database schema, NLP pipeline, feature engineering and scoring design, LLM integration and hallucination control, API design, frontend architecture, security architecture, evaluation design.
- [`docs/DATASET_STRATEGY.md`](docs/DATASET_STRATEGY.md) — which real datasets were researched (Hugging Face `resume-job-description-fit`, Kaggle resume/NER/LinkedIn-postings datasets, O*NET, ESCO), their actual limitations and licensing, and the weak-supervision strategy for where real relevance labels don't exist.
- [`docs/ROADMAP.md`](docs/ROADMAP.md) — the phased build plan; each phase is independently testable before the next begins.

## Planned repository structure

```
ai-resume-matcher/
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI routers
│   │   ├── models/       # SQLAlchemy models
│   │   ├── schemas/      # Pydantic request/response + domain schemas
│   │   ├── services/     # EmbeddingService, LLMService, scoring orchestration
│   │   ├── ml/           # feature engineering, rule-based scorer, ranking models
│   │   ├── nlp/          # section detection, information extraction, skill normalization
│   │   ├── parsers/      # PDF/DOCX text + layout extraction
│   │   └── main.py
│   ├── tests/
│   └── requirements.txt
├── frontend/
│   ├── src/
│   └── package.json
├── data/                 # download scripts + data/README.md documenting source/license; no raw data committed
├── models/                # trained model artifacts
├── notebooks/              # exploration, not production code
├── scripts/                 # dataset build, one-off tooling
├── evaluation/                # evaluate.py and evaluation fixtures
├── docker/
├── .env.example
├── docker-compose.yml
└── README.md
```

## Tech stack (see `docs/ARCHITECTURE.md` §4 for full justification)

Backend: Python, FastAPI, Pydantic, SQLAlchemy. ML/NLP: PyTorch, Sentence-Transformers, spaCy, scikit-learn, XGBoost/LightGBM. Documents: PyMuPDF, python-docx. Database: PostgreSQL + pgvector. Frontend: React + TypeScript, Tailwind. Deployment: Docker Compose.

## Getting started (Phase 0)

Phase 0 gives you a running Postgres+pgvector container and a FastAPI app with a single `/health` endpoint that proves the app can reach the database. No product functionality exists yet — that starts in Phase 1.

```bash
cp .env.example .env

# Start Postgres (pgvector extension enabled via docker/postgres/init.sql)
docker compose up -d postgres

# Backend: local dev loop (not the container) is fastest while iterating
cd backend
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt

# Apply migrations (creates the vector extension; schema is otherwise empty until Phase 8)
alembic upgrade head

# Run the app
uvicorn app.main:app --reload

# In another terminal:
curl http://localhost:8000/health
# -> {"status":"ok","environment":"development"}

pytest
```

Or run the backend itself in Docker instead of locally: `docker compose up -d` (both services), then `curl http://localhost:8000/health`.

**Phase 0 is done when**: `docker compose up -d postgres` starts cleanly, `alembic upgrade head` applies migration `0001` with no errors, `/health` returns `{"status": "ok", ...}`, and `pytest` passes.

## Next step

Phase 1 of `docs/ROADMAP.md` — PDF/DOCX document parsing.
