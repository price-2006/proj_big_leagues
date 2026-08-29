# Resume fixtures

Synthetically generated, not real resumes — see `generate_fixtures.py`. Used
by `backend/tests/parsers/` to test the Phase 1 document parsers against
layout diversity (single-column PDF, two-column PDF, DOCX) and against
malformed input, per the test procedure in `docs/ROADMAP.md` Phase 1.

Real, larger, more varied resume corpora arrive in Phase 10
(`docs/DATASET_STRATEGY.md`) for dataset-scale stress testing; these
fixtures are for fast, deterministic unit tests with known expected output.

Regenerate after changing the generator:

```bash
cd backend
python tests/fixtures/resumes/generate_fixtures.py
```
