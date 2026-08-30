// Typed fetch wrapper generated against the backend's OpenAPI schema
// (docs/ARCHITECTURE.md §11) — regenerate src/types/api.ts with
// `npm run generate:types` (backend must be running) after any backend
// schema change, so a drifted contract is a type error, not a runtime bug.
import createClient from 'openapi-fetch'

import type { paths } from '../types/api'

// Route keys in `paths` are the full backend paths (e.g. "/api/v1/resumes")
// since that's how FastAPI reports them — baseUrl stays empty so calls hit
// same-origin, where Vite's dev-server proxy (vite.config.ts) forwards
// `/api/*` to the backend.
export const apiClient = createClient<paths>({ baseUrl: '' })
