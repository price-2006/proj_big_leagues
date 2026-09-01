# Security hardening (Phase 14)

Audit and hardening pass against `docs/ARCHITECTURE.md` §12, per
`docs/ROADMAP.md`'s Phase 14. Each item below states what was found,
what changed (if anything), and how it's verified.

## Upload validation

**Found:** file-type routing was extension-only (`app/parsers/dispatch.py`),
with no size cap and no content-sniffing — a file named `resume.pdf`
containing anything at all reached `pymupdf.open()` directly.

**Changed:**
- `app/services/upload_validation.py`: a hard 5MB cap enforced during a
  chunked read (`read_upload_within_limit`), not a check after buffering
  an unbounded body; magic-byte signature checks (`verify_magic_bytes`)
  so a file's actual bytes have to match its claimed type.
- `app/parsers/docx_parser.py`: every XML/rels part inside a DOCX's zip
  is pre-scanned with `defusedxml` (`_reject_xxe_payloads`) before
  python-docx — which has no XXE hardening of its own — ever touches the
  bytes. A DOCTYPE declaration is rejected outright.
- `app/parsers/dispatch.py`: `parse_uploaded_document_with_timeout` runs
  parsing in a thread (`starlette.concurrency.run_in_threadpool`) under
  `asyncio.wait_for` (10s default) — bounds request latency and stops a
  slow parse from blocking every other concurrent request. This does
  **not** forcibly kill the underlying thread if the library call itself
  never returns (Python can't do that safely); a hard kill would need a
  separate process per parse, which isn't proportionate infrastructure
  here. Documented as a residual, known limitation, not silently ignored.
- Both `POST /resumes` and `POST /jobs` now read via the capped reader
  and call `verify_magic_bytes` before any parsing starts.

**Verified:** `tests/services/test_upload_validation.py`,
`tests/parsers/test_docx_parser.py::test_xxe_payload_docx_is_rejected_before_reaching_python_docx`,
`tests/parsers/test_dispatch_timeout.py`,
`tests/api/test_upload_security.py` (oversized/wrong-magic-byte/XXE
through the real endpoints).

## PII handling

**Found:** `explanation_service.py`'s prompt builder already excluded
`CandidateProfile.contact` (name/email/phone) from the LLM prompt by
construction (Phase 12) — true, but with no regression test. No
`DELETE /resumes/{id}` endpoint existed at all.

**Changed:**
- `tests/services/test_explanation_service.py` locks in the
  no-contact-info-in-prompt behavior with a real assertion.
- `DELETE /resumes/{id}` (`app/api/resumes.py`,
  `app/services/resume_deletion.py`): deletes the resume row, its
  `text_embeddings` rows (no FK exists for that polymorphic table, so
  this is explicit — same pattern already used by
  `text_embedding_store.py`), its `matches` rows (which cascade to
  `match_explanations` via the existing `ON DELETE CASCADE`), nulls out
  any referencing `training_labels.resume_id` rather than deleting real
  training data, and removes the uploaded file from disk.

**Verified:** `tests/api/test_resume_deletion.py`.

## Rate limiting

**Found:** nothing — no `slowapi`, no Redis service, no limiting of any
kind anywhere in the app.

**Changed:** `slowapi`, Redis-backed (`app/rate_limiter.py`), applied to
`POST /resumes`, `POST /jobs`, `POST /matches` (document parsing and
match embedding are this app's expensive operations, per this section's
own stated reasoning), and `POST /resumes/{id}/recommendations` (an LLM
call — not named explicitly in §12's text, but a real per-call cost, at
least as expensive as either of the above, so limited for the same
reason). A `redis` service was added to `docker-compose.yml`. A 429
response uses this app's existing `{"error": {"code","message"}}`
envelope (`app/main.py`'s `rate_limit_exceeded_handler`).

**Verified:** `tests/api/test_rate_limiting.py` — against a throwaway
endpoint using the real `Limiter` + real Redis backend (not a real
upload, so the test is fast and deterministic instead of needing 11 real
spaCy-parsed uploads to exhaust the real 10/minute limit; the mechanism
under test — Limiter, Redis storage, the 429 handler — is identical
either way). The full API test suite disables the limiter
(`tests/api/conftest.py`) since it's Redis-backed and shared across the
whole test run — without that, dozens of unrelated tests calling these
same endpoints in quick succession would trip the real per-minute limits.

## SQL injection

**Found:** already safe by construction. Only two `text()` (raw SQL)
call sites in the entire codebase, both fully static with zero
interpolation (`"SELECT 1"` in the health check, `"CREATE EXTENSION IF
NOT EXISTS vector"` in test setup); every other query goes through
SQLAlchemy Core/ORM parameterization. No code change was needed —
§12 explicitly calls for the test regardless ("tested explicitly"), so
this was proved end-to-end through the live API rather than left as an
assumption.

**Verified:** `tests/api/test_sql_injection.py` — classic
statement-terminator-plus-DROP payloads through job title/raw_text and a
resume filename, confirming they're stored/handled as inert literal
data and that the affected tables still work normally afterward.

## Secrets

**Found:** already compliant. A single `Settings` (pydantic-settings)
object is the only way config reaches the app; `.env.example` documents
every setting 1:1; `.env` and all upload directories are gitignored; no
hardcoded API keys or tokens anywhere in `app/`.

**Decision, not a defect:** `docker-compose.yml`'s Postgres service uses
`${POSTGRES_PASSWORD:-resume_matcher}` — a literal fallback baked into
the compose file for local-dev convenience (`docker compose up` works
with zero setup). This is a deliberate, common pattern for local
development, not a "secret exposed in application code" — kept as-is;
worth revisiting only if this project is ever deployed somewhere the
compose file's defaults would actually be reachable by someone else.

**Verified:** no code change; audited by reading `app/config.py`,
`.env.example`, and `docker-compose.yml` in full.

## Logging

Not one of §12's five bullets directly, but required by the PII bullet
("logging redacts resume/job raw text bodies") — and there was no
logging anywhere in the app to redact. `app/logging_config.py`
introduces stdlib `logging` with a `RedactingFilter` (masks known
sensitive dict keys — `raw_text`, `parsed_profile`, `chunk_text` — as
defense-in-depth) plus a starting convention: application code logs only
structured, whitelisted fields (ids, counts, error types), never a raw
resume/JD text body or a full profile dict. Logging calls were added at
the points this phase actually touches: upload rejections (magic-byte
mismatch, oversized, parse failure), resume deletion, rate-limit hits,
and LLM generation failures.
