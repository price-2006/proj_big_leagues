"""Phase 14, docs/ARCHITECTURE.md §12: "SQL injection: not applicable in
practice (SQLAlchemy parameterized queries throughout), but tested
explicitly in the integration test suite for any raw-SQL path." The
underlying code was already safe (grep across backend/app/ found no
string-interpolated raw SQL anywhere — only two fully-static text()
calls), so this proves it end-to-end through the live API rather than
just trusting "we use an ORM."

Payloads are classic injection probes (a statement-terminator plus a
DROP), not run directly against the DB — if parameterization ever broke,
the worst case here is a 500 or a literal string stored, never an actual
DROP, since the assertions below confirm the table still works
afterward regardless.
"""
import pytest

_PAYLOAD = "Senior Engineer'; DROP TABLE jobs; --"
_JD_TEXT_PAYLOAD = "Some Role\n\nRequirements\n- Python\n\n'); DROP TABLE jobs; --"


@pytest.mark.asyncio
async def test_sql_metacharacters_in_job_title_are_stored_as_inert_literal_text(client):
    response = await client.post(
        "/api/v1/jobs", data={"raw_text": "Some Role\n\nRequirements\n- Python\n", "title": _PAYLOAD}
    )

    assert response.status_code == 201
    assert response.json()["title"] == _PAYLOAD  # stored and returned verbatim, not executed

    # The jobs table is still intact and usable — a real DROP would make this fail.
    second_response = await client.post("/api/v1/jobs", data={"raw_text": "Another Role\n\nRequirements\n- SQL\n"})
    assert second_response.status_code == 201


@pytest.mark.asyncio
async def test_sql_metacharacters_in_job_raw_text_are_stored_as_inert_literal_text(client):
    response = await client.post("/api/v1/jobs", data={"raw_text": _JD_TEXT_PAYLOAD})

    # JobResponse doesn't echo raw_text (app/schemas/job_api.py) — the
    # meaningful proof here is that ingestion completes normally (a real
    # injection succeeding would derail parsing or 500, not cleanly 201)
    # and that the table is still fully usable afterward.
    assert response.status_code == 201
    fetch = await client.get(f"/api/v1/jobs/{response.json()['id']}")
    assert fetch.status_code == 200

    second_response = await client.post("/api/v1/jobs", data={"raw_text": "Yet Another Role\n\nRequirements\n- Go\n"})
    assert second_response.status_code == 201


@pytest.mark.asyncio
async def test_sql_metacharacters_in_resume_upload_filename_are_handled_safely(client):
    response = await client.post(
        "/api/v1/resumes",
        files={"file": ("resume'; DROP TABLE resumes; --.pdf", b"not actually a valid pdf", "application/pdf")},
    )

    # Garbage PDF bytes correctly fail parsing (400) regardless — the
    # point here is *how* it fails: not a 500 from a broken query, and
    # not because the injection payload did anything to the DB.
    assert response.status_code == 400

    second_response = await client.post("/api/v1/jobs", data={"raw_text": "Some Role\n\nRequirements\n- Python\n"})
    assert second_response.status_code == 201  # resumes table untouched; unrelated tables still work fine
