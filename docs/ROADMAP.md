# Development Roadmap

Each phase below produces something runnable and testable before the next phase starts — no phase depends on unbuilt code from a later phase. Phases map to the pipeline in `ARCHITECTURE.md` §2–§9. This is the plan; implementation happens incrementally in follow-up sessions, one phase (often one component within a phase) at a time, each with real code, a run procedure, and a test procedure — not delivered all at once.

## Phase 0 — Repository scaffold
**What**: create the directory structure from the brief (`backend/app/{api,models,schemas,services,ml,nlp,parsers}`, `frontend/`, `data/`, `models/`, `notebooks/`, `scripts/`, `evaluation/`, `docker/`), base `requirements.txt`, `.env.example`, `docker-compose.yml` skeleton, Postgres+pgvector container.
**Why**: everything else needs somewhere to live, and a project structure that doesn't accrete ad hoc as components get added.
**Test**: `docker compose up postgres` starts a Postgres instance with pgvector installed; `alembic upgrade head` runs against it with an empty schema.

## Phase 1 — Document parsing (PDF/DOCX → raw text)
**What**: `backend/app/parsers/pdf_parser.py`, `docx_parser.py` using PyMuPDF and python-docx, returning raw text plus layout metadata (font size/position for PDF, style for DOCX).
**Why**: the foundation every later NLP step reads from; must be correct and robust before section detection is built on top of it.
**Test**: unit tests against a small fixture set of real-world resumes (varied layouts, at least one single-column and one two-column PDF, one DOCX) asserting extracted text contains expected known strings; a malformed/corrupt file returns a clean error, not a crash.

## Phase 2 — Resume section detection
**What**: header-alias table + layout-heuristic segmenter (`backend/app/nlp/section_detector.py`) mapping resume text into labeled sections.
**Why**: information extraction needs to know *which* text is Skills vs Experience vs Education before it can extract meaningfully.
**Test**: run against the fixture resumes from Phase 1; assert each known section is correctly identified even where header wording varies (`"Technical Skills"` vs `"Core Competencies"`).

## Phase 3 — Resume information extraction → Candidate Profile
**What**: spaCy NER pipeline + regex extractors + bullet-level experience/project parsing, producing the `CandidateProfile` Pydantic model (matching the JSON shape in the brief §4).
**Why**: this is the structured data every downstream feature depends on.
**Test**: extraction accuracy against a small hand-labeled subset of fixture resumes (precision/recall per field: name, email, skills, degree, experience entries); schema validation passes on 100% of fixtures.

## Phase 4 — Job description parsing → Job Profile
**What**: mirrors Phase 2–3 for JDs: requirement section detection, required-vs-preferred classifier, `JobProfile` Pydantic model.
**Why**: symmetric structured input on the job side, with the required/preferred distinction the scoring model depends on.
**Test**: hand-labeled fixture JDs (a handful of real postings across seniority levels); assert required/preferred classification accuracy and schema validation.

## Phase 5 — Skill taxonomy and normalization service
**What**: `skills`/`skill_aliases`/`skill_disambiguation_rules` tables seeded from O*NET + ESCO + an internal curated set; the three-stage normalization pipeline from `ARCHITECTURE.md` §7.
**Why**: matching is meaningless without canonicalized skills, and this is the component most exposed to the false-positive-merge failure mode the brief warns about.
**Test**: a confusable-pairs test suite (`Java`/`JavaScript`, `React`/`React Native`, `PyTorch`/`TensorFlow`, and more collected during build) asserting these are never merged; an alias test suite asserting known variants do normalize correctly.

## Phase 6 — Embedding service
**What**: `EmbeddingService` interface + `SentenceTransformerEmbeddingService` implementation; embeddings computed and stored for resume experience/project bullets and JD responsibility lines (`text_embeddings` table).
**Why**: the semantic-similarity features (experience/project/responsibility similarity) depend on this, and it must be swappable per the brief's explicit requirement.
**Test**: known-similar sentence pairs score above a threshold, known-dissimilar pairs score below it; swapping the configured model name changes the embedding dimension/behavior without touching calling code.

## Phase 7 — Feature engineering + rule-based scorer v1
**What**: the 10-feature vector from `ARCHITECTURE.md` §8, and the transparent weighted rule-based scorer, with weights in a configurable `scoring_weights` table rather than hard-coded.
**Why**: this is the first point a real, explainable match score exists end-to-end without any LLM call.
**Test**: hand-constructed resume/JD pairs with obvious expected outcomes (strong match, weak match, missing-required-skill case) score in the expected direction and range; feature values are individually inspectable and match manual calculation.

## Phase 8 — Backend API wiring (FastAPI + DB, baseline pipeline end-to-end)
**What**: the endpoints from `ARCHITECTURE.md` §10 (`/resumes`, `/jobs`, `/matches`, `/resumes/{id}/matches`) wired to Phases 1–7, with SQLAlchemy models and Alembic migrations for the schema in §5.
**Why**: first point the system is a real, callable backend rather than a set of scripts.
**Test**: an integration test suite (`httpx` + a test DB) exercising upload → parse → match → fetch, asserting response schemas and non-trivial score output; OpenAPI docs render at `/docs`.

## Phase 9 — Frontend MVP (Dashboard, Upload, Job Analysis, Match Results)
**What**: React+TS app consuming the Phase 8 API — resume upload, JD paste/upload, and the score-breakdown match results view (progress bars, matching/missing/partial skill lists) from `ARCHITECTURE.md` §11.
**Why**: first demoable, end-to-end product surface, running entirely on the rule-based baseline — this is the point the project stops being "just a backend" and becomes the "polished web application" the brief asks for.
**Test**: manual walkthrough (upload a real resume, paste a real JD, see a plausible score and breakdown) plus component tests for the score-breakdown rendering logic given known feature inputs.

## Phase 10 — Dataset acquisition and weak-supervision pipeline
**What**: download scripts + `data/README.md` per `DATASET_STRATEGY.md`; preprocessing (dedup, run through the product's own parsers, grouped split); the weak-supervision label generator (occupation-family positive/negative sampling, rule-based-derived labels), all writing to `training_labels` with explicit `label_source`.
**Why**: nothing in Phase 11 can be honest without real, traceable training/eval data — and the brief is explicit that fabricated numbers are unacceptable.
**Test**: `scripts/build_dataset.py` run end-to-end reproducibly produces a `train`/`val`/`test` split with no resume or job text leaking across splits (an automated leakage-check assertion, not just a manual eyeball).

## Phase 11 — ML ranking model + `evaluate.py`
**What**: baseline Logistic Regression, then Random Forest/XGBoost/LightGBM, then an LTR objective, trained on the Phase 10 data; `evaluation/evaluate.py` reporting Precision/Recall/F1/ROC-AUC/NDCG@5/MRR for rule-based, embedding-cosine-baseline, and each trained model, broken out by label source (real gold set vs weak supervision) per `DATASET_STRATEGY.md` §3.
**Why**: this is the project's actual ML contribution — a documented, honestly-evaluated comparison, not an asserted "it works."
**Test**: `python evaluate.py` runs and produces real numbers from the stored held-out split; results are also logged to MLflow and the `experiments` table (Phase 0's schema).

## Phase 12 — LLM explanation and recommendation layer
**What**: `LLMService` abstraction + provider implementations, the evidence-constrained prompt/schema contract from `ARCHITECTURE.md` §9, and the post-generation evidence validator.
**Why**: this is where generative reasoning genuinely adds value (natural-language explanation, resume-improvement phrasing) without being allowed to touch the score or invent qualifications — the brief's central architectural requirement.
**Test**: adversarial test cases — a resume containing prompt-injection text, a request for an explanation where evidence is thin — assert the validator strips/rejects unfounded claims and the score is provably unaffected by LLM output (score computed and stored before the LLM call happens).

## Phase 13 — Multi-job ranking and Resume Optimization UI
**What**: `JobComparison.tsx` (ranked table, best-match/biggest-opportunity callouts) and `ResumeOptimization.tsx`, both from `ARCHITECTURE.md` §11, wired to Phase 11/12 outputs.
**Why**: this is called out in the brief as "a major part of the UI" — the multi-job comparison is what makes this feel like a real product rather than a single-score demo.
**Test**: manual walkthrough with 3+ real JDs against one resume; ranking order matches the stored scores; recommendations shown trace to evidence per Phase 12's validator.

## Phase 14 — Security hardening
**What**: upload validation (magic bytes, size caps, XXE-safe DOCX parsing), rate limiting, PII-aware logging, the delete endpoint, `.env`-based secret management audit.
**Why**: called out explicitly in the brief (§23) and non-negotiable given resumes contain real personal data.
**Test**: a security-focused test suite — oversized file rejected, wrong-magic-byte file rejected, XXE payload DOCX doesn't leak file contents, rate limiter returns 429 past threshold.

## Phase 15 — Deployment and polish
**What**: finalize `docker-compose.yml`, README with real setup instructions and real (not placeholder) evaluation numbers from Phase 11, a short architecture diagram export, optional CI (lint + test on push).
**Why**: the brief's stated end goal is a project demonstrable in an interview — this phase is what makes it easy for someone else to clone, run, and verify.
**Test**: a fresh `docker compose up` from a clean checkout brings up a working system end-to-end with no manual steps beyond `.env` setup.

---

**Working agreement for how we build each phase**: for every component, before moving to the next — explain what's being built and why, show the files being created/modified, provide complete (not placeholder) code, explain how to run it, give a concrete test procedure, and state the expected output. If something is intentionally stubbed early (e.g. auth), it's labeled as such rather than presented as finished.
