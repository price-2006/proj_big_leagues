"""Shared FastAPI dependencies (Phase 8)."""
from fastapi import Request

from app.services.skill_normalization_service import SkillTaxonomy


def get_taxonomy(request: Request) -> SkillTaxonomy:
    return request.app.state.taxonomy
