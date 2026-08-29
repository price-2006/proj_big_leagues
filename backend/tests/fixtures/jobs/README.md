# Job description fixtures

Synthetically written, not real postings — same rationale as
`tests/fixtures/resumes/`: no real JD corpus is available yet (Phase 10
brings one in, per `docs/DATASET_STRATEGY.md`'s `arshkon/linkedin-job-postings`
source). Plain `.txt` files rather than generated PDFs/DOCX, since pasted
plain text is the primary JD input path (`POST /jobs`) and carries no
layout metadata to fabricate.

Written across seniority levels (junior/senior/staff/unspecified) with
varied header wording ("Minimum Qualifications" vs "Requirements", "Nice
to Have" vs "Preferred Qualifications") and one deliberate trap: two of
the fixtures mention "junior" engineers in their Responsibilities section
on a Senior/Staff-level posting, to prove seniority detection reads the
title, not the whole document body.
