"""Rate limiting (Phase 14, docs/ARCHITECTURE.md §12): slowapi, Redis-backed
so the limit is shared across however many backend processes run, not
counted separately per-process. Applied to document parsing (POST
/resumes, POST /jobs) and match creation (POST /matches) — this
section's own stated reasoning is that parsing and embedding are this
app's expensive operations; POST /resumes/{id}/recommendations is
limited too even though §12's text doesn't name it explicitly, since an
LLM call is more expensive than either (a real per-call cost, not just
CPU time) and the same reasoning applies at least as strongly.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import get_settings

limiter = Limiter(key_func=get_remote_address, storage_uri=get_settings().redis_url)
