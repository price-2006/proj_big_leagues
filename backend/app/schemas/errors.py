"""Consistent error shape for every endpoint (Phase 8, docs/ARCHITECTURE.md §10)."""
from pydantic import BaseModel


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail
