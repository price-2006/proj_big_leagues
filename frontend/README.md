# Frontend

React + TypeScript (Vite) + Tailwind CSS, consuming the Phase 8 backend API (`docs/ARCHITECTURE.md` §11). Covers Phase 9's scope: resume upload, JD paste/upload, and the score-breakdown match results view. `JobComparison`/`ResumeOptimization` are Phase 13; evidence citations and recommendations need Phase 12's LLM layer.

## Getting started

```bash
npm install
npm run dev          # http://localhost:5173, proxies /api/* to the backend on :8000
```

Start the backend first (`docker compose up -d` from the repo root, or run it locally — see the root `README.md`).

## Regenerating API types

`src/types/api.ts` is generated from the backend's live OpenAPI schema — never edit it by hand:

```bash
npm run generate:types   # backend must be running on :8000
```

## Tests

```bash
npm run test         # component tests (Vitest + React Testing Library)
```

Phase 9's roadmap test procedure ("component tests for the score-breakdown rendering logic given known feature inputs") is covered by `src/components/ScoreBreakdown/ScoreBreakdown.test.tsx`, using a real, verified match computed by the backend rather than invented numbers. A manual end-to-end walkthrough (Dashboard → upload → analyze → match results) was also driven with Playwright against the real backend before this phase was called done.

## Why localStorage for the Dashboard

There's no `GET /resumes` or `GET /jobs` list-all endpoint in the backend (no auth/user-scoping exists yet for one to filter by — see `docs/ARCHITECTURE.md` §10). `src/context/SessionContext.tsx` tracks what you've created in this browser instead: an honest, session-scoped substitute, not a persisted account history.
