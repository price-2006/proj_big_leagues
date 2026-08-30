"""Reads the active scoring_weights row (Phase 7). The rule-based scorer
itself stays DB-free (app/ml/rule_based_scorer.py takes a plain dict) —
this is the thin loading layer Phase 8's API wiring will call.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ml.rule_based_scorer import DEFAULT_WEIGHTS
from app.models.scoring_weights import ScoringWeights


async def load_active_weights(session: AsyncSession) -> tuple[str, dict[str, float]]:
    """Returns (version, weights). Falls back to DEFAULT_WEIGHTS/'v1' if
    no active row exists yet — e.g. a fresh DB before the seed migration
    has run, or every row was deliberately deactivated."""
    result = await session.execute(select(ScoringWeights).where(ScoringWeights.is_active.is_(True)))
    row = result.scalars().first()
    if row is None:
        return "v1", DEFAULT_WEIGHTS
    return row.version, row.weights
